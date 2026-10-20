"""Record/replay wrapper for every chat-model call."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any, Iterator
from uuid import uuid4

from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict
from langchain_core.outputs import ChatGeneration, LLMResult

from evals.modes import EvalMode, llm_mode
from evals.replay.store import ReplayStore

_STORE = ReplayStore("llm")
_LABEL: ContextVar[str | None] = ContextVar("evals_llm_label", default=None)


def _node_name() -> str:
    explicit = _LABEL.get()
    if explicit:
        return explicit
    try:
        from langgraph.config import get_config

        config = get_config()
        return str(config.get("metadata", {}).get("langgraph_node") or "unattributed")
    except RuntimeError:
        return "unattributed"


def _normalise_input(value: Any) -> Any:
    if hasattr(value, "to_messages"):
        value = value.to_messages()
    if isinstance(value, BaseMessage):
        return message_to_dict(value)
    if isinstance(value, (list, tuple)):
        return [_normalise_input(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalise_input(item) for key, item in value.items()}
    return value


def _tool_schema(tool: Any) -> Any:
    if hasattr(tool, "model_json_schema"):
        return tool.model_json_schema()
    if hasattr(tool, "args_schema") and tool.args_schema:
        return tool.args_schema.model_json_schema()
    return getattr(tool, "name", getattr(tool, "__name__", str(tool)))


def _serialise_response(response: Any) -> dict[str, Any]:
    if not isinstance(response, BaseMessage):
        raise TypeError(f"ReplayLLM only records BaseMessage responses, got {type(response)!r}")
    return message_to_dict(response)


def _deserialise_response(response: dict[str, Any]) -> BaseMessage:
    return messages_from_dict([response])[0]


def _notify_replayed(response: BaseMessage, config: Any = None) -> None:
    if config is None:
        try:
            from langgraph.config import get_config

            config = get_config()
        except RuntimeError:
            return
    run_id = uuid4()
    metadata = dict(config.get("metadata", {}))
    metadata.setdefault("langgraph_node", _node_name())
    result = LLMResult(generations=[[ChatGeneration(message=response)]])
    configured = config.get("callbacks", [])
    callbacks = getattr(configured, "handlers", configured)
    for callback in callbacks:
        # Only notify the local usage callback. Sending replayed traffic to a
        # remote tracer would make the offline gate depend on the network.
        if callback.__class__.__name__ != "UsageTracker":
            continue
        callback.on_chat_model_start({}, [], run_id=run_id, metadata=metadata)
        callback.on_llm_end(result, run_id=run_id, metadata=metadata)


@contextmanager
def llm_call_label(label: str) -> Iterator[None]:
    token = _LABEL.set(label)
    try:
        yield
    finally:
        _LABEL.reset(token)


class ReplayLLM:
    """Transparent chat-model facade with exact prompt-hash replay."""

    def __init__(self, target: Any, tools: list[Any] | None = None, bind_kwargs: dict | None = None) -> None:
        self._target = target
        self._tools = list(tools or [])
        self._bind_kwargs = dict(bind_kwargs or {})

    def bind_tools(self, tools: list[Any], **kwargs: Any) -> "ReplayLLM":
        return ReplayLLM(self._target, tools=tools, bind_kwargs=kwargs)

    def _request(self, value: Any, kwargs: dict[str, Any]) -> dict[str, Any]:
        request = {
            "node": _node_name(),
            "prompt": _normalise_input(value),
            "tools": [_tool_schema(tool) for tool in self._tools],
            "invoke_kwargs": _normalise_input(kwargs),
        }
        if self._bind_kwargs:
            request["bind_kwargs"] = _normalise_input(self._bind_kwargs)
        return request

    def _bound_target(self) -> Any:
        if not self._tools:
            return self._target
        return self._target.bind_tools(self._tools, **self._bind_kwargs)

    def invoke(self, value: Any, config: Any = None, **kwargs: Any) -> BaseMessage:
        request = self._request(value, kwargs)
        if llm_mode() is EvalMode.REPLAY:
            response = _deserialise_response(_STORE.load("invoke", request))
            _notify_replayed(response, config)
            return response
        if llm_mode() is EvalMode.RECORD:
            existing = _STORE.load_if_present("invoke", request)
            if existing is not None:
                response = _deserialise_response(existing)
                _notify_replayed(response, config)
                return response
        response = self._bound_target().invoke(value, config=config, **kwargs)
        if llm_mode() is EvalMode.RECORD:
            _STORE.save("invoke", request, _serialise_response(response))
        return response

    async def ainvoke(self, value: Any, config: Any = None, **kwargs: Any) -> BaseMessage:
        request = self._request(value, kwargs)
        if llm_mode() is EvalMode.REPLAY:
            response = _deserialise_response(_STORE.load("invoke", request))
            _notify_replayed(response, config)
            return response
        if llm_mode() is EvalMode.RECORD:
            existing = _STORE.load_if_present("invoke", request)
            if existing is not None:
                response = _deserialise_response(existing)
                _notify_replayed(response, config)
                return response
        response = await self._bound_target().ainvoke(value, config=config, **kwargs)
        if llm_mode() is EvalMode.RECORD:
            _STORE.save("invoke", request, _serialise_response(response))
        return response
