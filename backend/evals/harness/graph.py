"""Database-free graph compilation for evaluation runs."""

from langgraph.checkpoint.memory import InMemorySaver

from agent.graph import compile_eval_graph


def build_eval_graph():
    return compile_eval_graph(InMemorySaver())
