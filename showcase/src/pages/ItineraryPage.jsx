import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { BedDouble, CheckCircle2, Clock, DollarSign, Loader2, MapPin, Plane, Send, Utensils, Users } from "lucide-react";
import { getTrip, refineTrip, refinementStreamUrl } from "../api.js";
import { ItineraryMap } from "../ui/ItineraryMap.jsx";
import { loadTripPayload, saveTripPayload } from "../storage.js";
import { currency, percent, shortDate, titleize } from "../utils/format.js";

export function ItineraryPage() {
  const { tripId } = useParams();
  const refinementSourceRef = useRef(null);
  const [payload, setPayload] = useState(() => loadTripPayload(tripId));
  const [selectedDay, setSelectedDay] = useState(0);
  const [loading, setLoading] = useState(!payload);
  const [error, setError] = useState("");
  const [refinementText, setRefinementText] = useState("");
  const [refinementStatus, setRefinementStatus] = useState("idle");
  const [refinementError, setRefinementError] = useState("");
  const [refinementEvents, setRefinementEvents] = useState([]);

  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const trip = await getTrip(tripId);
        if (!active) return;
        const normalized = normalizeTripDocument(trip);
        if (normalized) {
          setPayload(normalized);
          saveTripPayload(tripId, normalized);
        } else {
          setError("This trip has not completed yet.");
        }
      } catch (err) {
        if (!payload) setError(err.message || "Unable to load trip.");
      } finally {
        if (active) setLoading(false);
      }
    }
    load();
    return () => {
      active = false;
    };
  }, [payload, tripId]);

  useEffect(() => {
    return () => refinementSourceRef.current?.close();
  }, []);

  const itinerary = payload?.itinerary || {};
  const days = itinerary.days || [];
  const day = days[selectedDay] || days[0];
  const dayAgenda = buildAgenda(day, itinerary.hotel);
  const tripPitch = payload?.trip_pitch || "";

  const totals = useMemo(() => {
    const dayCosts = days.reduce((sum, item) => sum + Number(item.estimated_day_cost_usd || 0), 0);
    const travelMinutes = days.reduce((sum, item) => sum + Number(item.total_travel_minutes || 0), 0);
    return { dayCosts, travelMinutes };
  }, [days]);

  async function submitRefinement(event) {
    event.preventDefault();
    const message = refinementText.trim();
    if (!message || refinementStatus === "streaming" || refinementStatus === "queued") return;

    refinementSourceRef.current?.close();
    setRefinementStatus("queued");
    setRefinementError("");
    setRefinementEvents([]);

    try {
      const queued = await refineTrip(tripId, message);
      setRefinementStatus("streaming");
      const source = new EventSource(refinementStreamUrl(tripId, queued.refinement_id));
      refinementSourceRef.current = source;

      source.onerror = () => {
        setRefinementStatus("error");
        setRefinementError("The refinement stream disconnected.");
        source.close();
      };

      source.onmessage = (streamMessage) => {
        const eventPayload = JSON.parse(streamMessage.data);
        const eventType = eventPayload.event_type;
        const data = eventPayload.data || {};

        if (eventType === "REFINEMENT_STARTED") {
          setRefinementStatus("streaming");
        }

        if (eventType === "REFINEMENT_PARSED") {
          setRefinementEvents((current) => [
            ...current,
            { node: "parse_refinement", message: data.parsed?.message || message },
          ]);
        }

        if (eventType === "NODE_PROGRESS") {
          setRefinementEvents((current) => [...current, data]);
        }

        if (eventType === "REFINEMENT_COMPLETE") {
          setRefinementStatus("complete");
          setPayload(data);
          saveTripPayload(tripId, data);
          setRefinementText("");
          setSelectedDay((current) => Math.min(current, Math.max((data.itinerary?.days || []).length - 1, 0)));
          source.close();
        }

        if (eventType === "ERROR") {
          setRefinementStatus("error");
          setRefinementError(data.message || "The refinement failed.");
          source.close();
        }
      };
    } catch (err) {
      setRefinementStatus("error");
      const detail = err.message || "Unable to start refinement.";
      setRefinementError(detail);
    }
  }

  if (loading) {
    return <div className="panel loading-panel">Loading itinerary...</div>;
  }

  if (error && !payload) {
    return (
      <section className="panel">
        <p className="eyebrow">Trip {tripId}</p>
        <h1>{error}</h1>
        <div className="button-row">
          <Link className="primary-button compact" to={`/planning/${tripId}`}>
            Return to planning
          </Link>
          <Link className="secondary-button compact" to="/">
            New trip
          </Link>
        </div>
      </section>
    );
  }

  return (
    <div className="itinerary-layout">
      <section className="panel itinerary-hero">
        <p className="eyebrow">Completed trip</p>
        <h1>{itinerary.selected_destination || "Generated itinerary"}</h1>
        <div className="trip-pitch">
          {formatTripPitch(tripPitch).map((paragraph, index) =>
            index === 0 ? <h2 key={paragraph}>{paragraph}</h2> : <p key={paragraph}>{paragraph}</p>,
          )}
        </div>
        <div className="summary-row">
          <Metric icon={<Users size={18} />} label="Travelers" value={(itinerary.members || []).length} />
          <Metric icon={<DollarSign size={18} />} label="Day costs" value={currency(totals.dayCosts)} />
          <Metric icon={<Clock size={18} />} label="Travel time" value={`${totals.travelMinutes} min`} />
          <Metric icon={<CheckCircle2 size={18} />} label="Fairness" value={itinerary.fairness_passed ? "Passed" : "Review"} />
        </div>
      </section>

      <section className="trip-facts">
        <InfoCard icon={<Users size={18} />} title="Members">
          <div className="chip-list">
            {(itinerary.members || []).map((member) => (
              <span className="chip" key={member.member_id}>
                {member.name} - {member.origin_city} - {currency(member.budget_usd)}
              </span>
            ))}
          </div>
        </InfoCard>
        <InfoCard icon={<Plane size={18} />} title="Flights">
          <div className="compact-list">
            {(itinerary.flights || []).slice(0, 4).map((flight) => (
              <span key={`${flight.member_id}-${flight.origin}`}>
                {flight.origin} to {flight.destination}: {currency(flight.price_usd)} - {flight.airline}
              </span>
            ))}
          </div>
        </InfoCard>
        <InfoCard icon={<BedDouble size={18} />} title="Hotel">
          {itinerary.hotel ? (
            <p>
              <strong>{itinerary.hotel.name}</strong>
              <br />
              {itinerary.hotel.address}
              <br />
              {currency(itinerary.hotel.total_price_usd)} total
            </p>
          ) : (
            <p>No hotel returned.</p>
          )}
        </InfoCard>
      </section>

      <section className="panel refinement-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Refinement</p>
            <h2>Ask for a change</h2>
          </div>
          {refinementStatus === "streaming" || refinementStatus === "queued" ? <Loader2 className="spin" size={18} /> : null}
        </div>
        <form className="refinement-form" onSubmit={submitRefinement}>
          <textarea
            aria-label="Refinement request"
            rows={2}
            value={refinementText}
            onChange={(event) => setRefinementText(event.target.value)}
            placeholder="Make Day 2 cheaper, or swap the museum for something outdoors"
            disabled={refinementStatus === "streaming" || refinementStatus === "queued"}
          />
          <button
            className="primary-button compact"
            type="submit"
            disabled={!refinementText.trim() || refinementStatus === "streaming" || refinementStatus === "queued"}
          >
            {refinementStatus === "streaming" || refinementStatus === "queued" ? <Loader2 className="spin" size={16} /> : <Send size={16} />}
            Refine
          </button>
        </form>
        {refinementError ? <div className="error-banner refinement-error">{refinementError}</div> : null}
        {refinementEvents.length ? (
          <div className="refinement-events">
            {refinementEvents.slice(-5).map((item, index) => (
              <span key={`${item.node}-${index}`}>
                <CheckCircle2 size={14} />
                {item.message || item.node}
              </span>
            ))}
          </div>
        ) : null}
      </section>

      <section className="panel constraints-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Planning checks</p>
            <h2>Constraints and scores</h2>
          </div>
        </div>
        <div className="score-grid">
          {Object.entries(itinerary.fairness_scores || {}).map(([key, value]) => (
            <span key={key}>
              {titleize(key)} <strong>{percent(value)}</strong>
            </span>
          ))}
          {Object.entries(itinerary.compatibility_scores || {}).map(([key, value]) => (
            <span key={key}>
              {titleize(key)} <strong>{percent(value)}</strong>
            </span>
          ))}
          {Object.keys(itinerary.fairness_scores || {}).length === 0 ? <span>Scores will appear after completion.</span> : null}
        </div>
      </section>

      <section className="panel day-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Itinerary map</p>
            <h2>Day by day</h2>
          </div>
          <div className="day-tabs">
            {days.map((item, index) => (
              <button
                className={index === selectedDay ? "active" : ""}
                type="button"
                key={item.day_number || index}
                onClick={() => setSelectedDay(index)}
              >
                Day {item.day_number || index + 1}
              </button>
            ))}
          </div>
        </div>

        {day ? (
          <div className="day-split">
            <div className="day-details">
              <p className="eyebrow">{shortDate(day.date)} - {day.neighborhood}</p>
              <h3>Day {day.day_number}</h3>
              <p>{day.rationale}</p>
              <div className="agenda-list">
                {dayAgenda.map((item, index) => (
                  <article className={`agenda-item ${item.type}`} key={`${item.time}-${item.label}-${index}`}>
                    <span className="agenda-order">{index + 1}</span>
                    <span className="agenda-time">{item.time}</span>
                    <div>
                      <strong>
                        {item.type === "hotel" ? (
                          <BedDouble size={15} />
                        ) : item.type === "meal" ? (
                          <Utensils size={15} />
                        ) : (
                          <MapPin size={15} />
                        )}
                        {item.label}
                      </strong>
                      <small>{item.notes}</small>
                    </div>
                  </article>
                ))}
              </div>
              <DayConstraints notes={day.constraint_notes || []} />
            </div>
            <ItineraryMap
              day={day}
              destination={itinerary.selected_destination_coords}
            />
          </div>
        ) : (
          <p>No itinerary days were returned.</p>
        )}
      </section>
    </div>
  );
}

function Metric({ icon, label, value }) {
  return (
    <div className="summary-item">
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function InfoCard({ icon, title, children }) {
  return (
    <article className="info-card">
      <div className="info-title">
        {icon}
        <h3>{title}</h3>
      </div>
      {children}
    </article>
  );
}

function DayConstraints({ notes }) {
  if (!notes.length) return null;
  return (
    <div className="day-constraints">
      <div>
        <p className="eyebrow">Day fit</p>
        <strong>Constraints handled</strong>
      </div>
      <ul>
        {notes.map((note) => (
          <li key={note}>
            <CheckCircle2 size={15} />
            <span>{note}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function normalizeTripDocument(trip) {
  if (trip?.itinerary) {
    return {
      trip_id: trip.trip_id,
      trip_pitch: trip.trip_pitch || trip.final_state?.trip_pitch || "",
      itinerary: trip.itinerary,
      preference_constraints: trip.preference_constraints || {},
      constraint_satisfaction: trip.constraint_satisfaction || {},
      decision_log: trip.decision_log || [],
      refinement_history: trip.refinement_history || [],
    };
  }

  if (trip?.final_state?.trip_pitch) {
    const state = trip.final_state;
    return {
      trip_id: trip.trip_id,
      trip_pitch: state.trip_pitch || "",
      itinerary: {
        trip_id: trip.trip_id,
        selected_destination: state.selected_destination,
        selected_destination_coords: state.selected_destination_coords,
        start_date: state.start_date,
        end_date: state.end_date,
        members: state.members || [],
        flights: state.flights || [],
        hotel: state.hotel,
        days: state.days || [],
        weather: state.weather,
        budget_status: state.budget_status,
        fairness_scores: state.fairness_scores || {},
        compatibility_scores: state.compatibility_scores || {},
        fairness_passed: state.fairness_passed,
        preference_constraints: state.preference_constraints || {},
        constraint_satisfaction: state.constraint_satisfaction || {},
      },
      preference_constraints: state.preference_constraints || {},
      constraint_satisfaction: state.constraint_satisfaction || {},
      decision_log: state.decision_log || [],
      refinement_history: state.refinement_history || [],
    };
  }

  return null;
}

function formatTripPitch(markdown) {
  const paragraphs = String(markdown || "")
    .split(/\n{2,}/)
    .map((paragraph) => paragraph.replace(/^#+\s+/, "").trim())
    .filter(Boolean);
  return paragraphs.length ? paragraphs : ["The backend returned a completed itinerary."];
}

function buildAgenda(day, hotel) {
  if (Array.isArray(day?.route_stops) && day.route_stops.length) {
    return [...day.route_stops]
      .sort((a, b) => Number(a.order || 0) - Number(b.order || 0))
      .map((stop) => ({
        time: stop.time || (stop.type === "hotel" ? "Base" : "--:--"),
        type: stop.type === "restaurant" ? "meal" : stop.type || "activity",
        label: stop.label || "Stop",
        notes: stop.address || stop.notes || titleize(stop.type || "stop"),
      }));
  }

  const hotelAgenda = hotel
    ? [
        {
          time: "Base",
          type: "hotel",
          label: hotel.name || "Hotel",
          notes: hotel.address || "Hotel base",
        },
      ]
    : [];

  if (Array.isArray(day?.schedule) && day.schedule.length) {
    return [
      ...hotelAgenda,
      ...[...day.schedule]
      .map((item) => ({
        time: item.time || "--:--",
        type: item.type || "activity",
        label: item.label || item.name || "Scheduled item",
        notes: item.notes || titleize(item.type || "activity"),
      }))
      .sort((a, b) => timeToMinutes(a.time) - timeToMinutes(b.time)),
    ];
  }

  const fallback = [...hotelAgenda];
  (day?.activities || []).forEach((activity, index) => {
    fallback.push({
      time: `${String(10 + index * 2).padStart(2, "0")}:00`,
      type: "activity",
      label: activity.name,
      notes: `${titleize(activity.category)} - ${activity.address}${activity.rating ? ` - ${activity.rating} stars` : ""}`,
    });
  });
  (day?.meals || []).forEach((meal, index) => {
    fallback.push({
      time: ["08:30", "12:30", "18:30"][index] || "19:30",
      type: "meal",
      label: meal,
      notes: "Meal stop",
    });
  });
  return fallback.sort((a, b) => timeToMinutes(a.time) - timeToMinutes(b.time));
}

function timeToMinutes(value) {
  if (String(value || "").toLowerCase() === "base") return 0;
  const match = String(value || "").match(/^(\d{1,2}):(\d{2})/);
  if (!match) return Number.MAX_SAFE_INTEGER;
  return Number(match[1]) * 60 + Number(match[2]);
}
