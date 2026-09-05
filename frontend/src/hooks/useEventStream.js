import { useCallback, useEffect, useRef, useState } from "react"

/**
 * Subscribes to one of the backend's SSE endpoints.
 *
 * Two things about EventSource drive the shape of this hook:
 *
 * 1. It cannot send request headers, so a bearer token is impossible — the session cookie is
 *    the only way to authenticate a stream. Cookies are withheld cross-origin unless
 *    `withCredentials` is set, and the frontend (5173) and API (8000) are different origins,
 *    so without it every stream will 401 the moment the trip routes require auth.
 * 2. It reconnects by itself whenever the connection ends — including the clean end after a
 *    run finishes. Left alone it would reopen the stream and replay the run, so terminal
 *    events have to close it explicitly via `closeOn`.
 *
 * Frames are `{ event_type, data }`; heartbeat comments never reach onmessage.
 */
export function useEventStream(url, { enabled = true, onEvent, closeOn = [] } = {}) {
  const [events, setEvents] = useState([])
  const [status, setStatus] = useState("idle")
  const [error, setError] = useState(null)

  const sourceRef = useRef(null)
  const onEventRef = useRef(onEvent)
  const closeOnRef = useRef(closeOn)
  onEventRef.current = onEvent
  closeOnRef.current = closeOn

  const close = useCallback(() => {
    sourceRef.current?.close()
    sourceRef.current = null
    setStatus("closed")
  }, [])

  useEffect(() => {
    if (!enabled || !url) return undefined

    setEvents([])
    setError(null)
    setStatus("connecting")

    const source = new EventSource(url, { withCredentials: true })
    sourceRef.current = source

    source.onopen = () => setStatus("open")

    source.onmessage = (message) => {
      let frame
      try {
        frame = JSON.parse(message.data)
      } catch {
        return // not a frame we understand; ignore rather than tear the stream down
      }

      setEvents((previous) => [...previous, frame])
      onEventRef.current?.(frame)

      if (closeOnRef.current.includes(frame.event_type)) {
        source.close()
        sourceRef.current = null
        setStatus("closed")
      }
    }

    source.onerror = () => {
      // EventSource retries transient drops on its own; only CLOSED is terminal.
      if (source.readyState === EventSource.CLOSED) {
        setStatus("error")
        setError(new Error("Lost connection to the planning stream."))
      }
    }

    return () => {
      source.close()
      sourceRef.current = null
    }
  }, [url, enabled])

  return { events, status, error, close }
}
