import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { CheckCircle2, Loader2, MapPin, RefreshCw, Send, TriangleAlert } from "lucide-react";
import { confirmCity, getCandidateCoords, streamUrl } from "../api.js";
import { saveTripPayload } from "../storage.js";

const EXPECTED_STEPS = [
  "parse_input",
  "extract_preference_constraints",
  "select_destination",
  "dynamic_tool_selection",
  "parallel_data_fetch",
  "budget_analysis",
  "search_hotel",
  "run_itinerary_node",
  "cluster_by_neighborhood",
  "build_itinerary",
  "align_flight_times",
  "plan_routes",
  "validation_gate",
  "compute_fairness",
  "assemble_output",
];

export function PlanningPage() {
  const { tripId } = useParams();
  const navigate = useNavigate();
  const sourceRef = useRef(null);
  const [events, setEvents] = useState([]);
  const [candidates, setCandidates] = useState([]);
  const [status, setStatus] = useState("connecting");
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState("");

  useEffect(() => {
    setStatus("connecting");
    setError("");
    const source = new EventSource(streamUrl(tripId));
    sourceRef.current = source;

    source.onopen = () => setStatus("streaming");
    source.onerror = () => {
      setError("The live planning stream disconnected. Check that the backend is running and reachable.");
      setStatus("error");
      source.close();
    };
    source.onmessage = (message) => {
      const payload = JSON.parse(message.data);
      const eventType = payload.event_type;
      const data = payload.data || {};

      if (eventType === "NODE_PROGRESS") {
        setStatus("streaming");
        setEvents((current) => [...current, data]);
      }

      if (eventType === "HITL_REQUIRED") {
        setStatus("waiting");
        setCandidates(data.candidate_destinations || []);
      }

      if (eventType === "TRIP_COMPLETE") {
        setStatus("complete");
        saveTripPayload(tripId, payload.data);
        source.close();
        navigate(`/trip/${tripId}`);
      }

      if (eventType === "ERROR") {
        setStatus("error");
        setError(data.message || "The backend returned an error.");
        source.close();
      }
    };

    return () => source.close();
  }, [navigate, tripId]);

  const seenSteps = useMemo(() => new Set(events.map((event) => event.node)), [events]);

  async function chooseDestination(candidate) {
    setConfirming(candidate.name || candidate.destination);
    setError("");
    try {
      await confirmCity(tripId, candidate);
      setStatus("streaming");
      setCandidates([]);
    } catch (err) {
      setError(err.message || "Unable to confirm destination.");
    } finally {
      setConfirming("");
    }
  }

  return (
    <div className="planning-layout">
      <section className="panel planning-hero">
        <p className="eyebrow">Trip {tripId}</p>
        <h1>{status === "waiting" ? "Choose the destination." : "The planning graph is running."}</h1>
        <p className="intro-copy">
          The backend is streaming LangGraph progress in real time. Once the graph finishes, the final
          itinerary will open automatically.
        </p>
        <div className={`status-banner ${status}`}>
          {status === "error" ? <TriangleAlert size={18} /> : <Loader2 className="spin" size={18} />}
          <span>{statusText(status)}</span>
        </div>
        {error ? (
          <div className="error-banner">
            {error}
            <Link to="/" className="inline-link">
              Back to input
            </Link>
          </div>
        ) : null}
      </section>

      {candidates.length ? (
        <section className="panel">
          <div className="section-heading">
            <div>
              <p className="eyebrow">Human review</p>
              <h2>Candidate destinations</h2>
            </div>
          </div>
          <div className="candidate-grid">
            {candidates.map((candidate) => {
              const coords = getCandidateCoords(candidate);
              const name = candidate.name || candidate.destination || candidate.id;
              return (
                <article className="candidate-card" key={name}>
                  <div className="candidate-title">
                    <MapPin size={18} />
                    <h3>{name}</h3>
                  </div>
                  <p>{candidate.llm_reasoning || candidate.reasoning || candidate.rationale || "Strong group fit."}</p>
                  <div className="candidate-meta">
                    <span>{coords.lat.toFixed(3)}, {coords.lng.toFixed(3)}</span>
                    {candidate.score ? <span>Score {Number(candidate.score).toFixed(2)}</span> : null}
                  </div>
                  <button
                    className="primary-button compact"
                    type="button"
                    onClick={() => chooseDestination(candidate)}
                    disabled={Boolean(confirming)}
                  >
                    {confirming === name ? <Loader2 className="spin" size={16} /> : <Send size={16} />}
                    Choose destination
                  </button>
                </article>
              );
            })}
          </div>
        </section>
      ) : null}

      <section className="panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">LLM progress</p>
            <h2>Workflow states</h2>
          </div>
          <RefreshCw size={18} />
        </div>
        <div className="timeline">
          {EXPECTED_STEPS.map((step) => {
            const event = events.find((item) => item.node === step);
            const done = seenSteps.has(step);
            return (
              <div className={done ? "timeline-item done" : "timeline-item"} key={step}>
                <span className="timeline-dot">
                  {done ? <CheckCircle2 size={16} /> : null}
                </span>
                <div>
                  <strong>{event?.message || labelForStep(step)}</strong>
                  <small>{step}</small>
                </div>
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function statusText(status) {
  if (status === "connecting") return "Connecting to backend stream";
  if (status === "waiting") return "Waiting for destination approval";
  if (status === "complete") return "Trip complete";
  if (status === "error") return "Stream error";
  return "Generating itinerary";
}

function labelForStep(step) {
  return step
    .replace(/_/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}
