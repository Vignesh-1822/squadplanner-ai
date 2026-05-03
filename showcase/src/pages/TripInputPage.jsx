import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { CalendarDays, Loader2, Plus, Send, Trash2, Users } from "lucide-react";
import { createTrip } from "../api.js";
import { createBlankMember, demoTrip, PREFERENCE_KEYS } from "../demoTrip.js";
import { currency, titleize } from "../utils/format.js";

export function TripInputPage() {
  const [form, setForm] = useState(demoTrip);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const navigate = useNavigate();

  const averageBudget = useMemo(() => {
    const total = form.members.reduce((sum, member) => sum + Number(member.budget_usd || 0), 0);
    return total / Math.max(form.members.length, 1);
  }, [form.members]);

  function updateTrip(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updateMember(index, patch) {
    setForm((current) => ({
      ...current,
      members: current.members.map((member, memberIndex) =>
        memberIndex === index ? { ...member, ...patch } : member,
      ),
    }));
  }

  function updatePreference(index, key, value) {
    setForm((current) => ({
      ...current,
      members: current.members.map((member, memberIndex) =>
        memberIndex === index
          ? {
              ...member,
              preference_vector: {
                ...member.preference_vector,
                [key]: Number(value),
              },
            }
          : member,
      ),
    }));
  }

  function setLeader(index) {
    setForm((current) => ({
      ...current,
      members: current.members.map((member, memberIndex) => ({
        ...member,
        is_leader: memberIndex === index,
      })),
    }));
  }

  function addMember() {
    setForm((current) => ({
      ...current,
      members: [...current.members, createBlankMember(current.members.length)],
    }));
  }

  function removeMember(index) {
    setForm((current) => {
      const members = current.members.filter((_, memberIndex) => memberIndex !== index);
      if (!members.some((member) => member.is_leader) && members[0]) members[0].is_leader = true;
      return { ...current, members };
    });
  }

  async function handleSubmit(event) {
    event.preventDefault();
    setSubmitting(true);
    setError("");

    try {
      const payload = normalizePayload(form);
      const created = await createTrip(payload);
      navigate(`/planning/${created.trip_id}`);
    } catch (err) {
      setError(err.message || "Unable to create trip.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="input-grid" onSubmit={handleSubmit}>
      <section className="panel intro-panel">
        <div>
          <p className="eyebrow">Live AI trip planning</p>
          <h1>Plan a group trip from everyone's preferences.</h1>
          <p className="intro-copy">
            SquadPlanner collects each traveler's constraints, streams live planning progress,
            asks for destination approval, and builds a day-by-day itinerary with maps.
          </p>
        </div>
        <div className="summary-row">
          <SummaryItem icon={<Users size={18} />} label="Travelers" value={form.members.length} />
          <SummaryItem icon={<CalendarDays size={18} />} label="Dates" value={`${form.start_date} to ${form.end_date}`} />
          <SummaryItem label="Avg budget" value={currency(averageBudget)} />
        </div>
      </section>

      <section className="panel trip-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Trip setup</p>
            <h2>Group details</h2>
          </div>
        </div>
        <div className="field-grid two">
          <label>
            <span>Start date</span>
            <input
              type="date"
              value={form.start_date}
              onChange={(event) => updateTrip("start_date", event.target.value)}
              required
            />
          </label>
          <label>
            <span>End date</span>
            <input
              type="date"
              value={form.end_date}
              onChange={(event) => updateTrip("end_date", event.target.value)}
              required
            />
          </label>
        </div>
        <label>
          <span>Group notes</span>
          <textarea
            value={form.group_notes}
            onChange={(event) => updateTrip("group_notes", event.target.value)}
            rows={4}
          />
        </label>
      </section>

      <section className="panel travelers-panel">
        <div className="section-heading">
          <div>
            <p className="eyebrow">Inputs</p>
            <h2>Travelers</h2>
          </div>
          <button className="icon-text-button" type="button" onClick={addMember}>
            <Plus size={18} />
            Add person
          </button>
        </div>

        <div className="traveler-list">
          {form.members.map((member, index) => (
            <article className="traveler-card" key={`${member.member_id}-${index}`}>
              <div className="traveler-header">
                <button
                  className={member.is_leader ? "leader active" : "leader"}
                  type="button"
                  onClick={() => setLeader(index)}
                >
                  {member.is_leader ? "Leader" : "Make leader"}
                </button>
                <button
                  className="icon-button danger"
                  type="button"
                  onClick={() => removeMember(index)}
                  disabled={form.members.length === 1}
                  aria-label={`Remove ${member.name}`}
                >
                  <Trash2 size={17} />
                </button>
              </div>

              <div className="field-grid three">
                <label>
                  <span>Name</span>
                  <input
                    value={member.name}
                    onChange={(event) => updateMember(index, { name: event.target.value })}
                    required
                  />
                </label>
                <label>
                  <span>Origin airport</span>
                  <input
                    value={member.origin_city}
                    onChange={(event) =>
                      updateMember(index, { origin_city: event.target.value.toUpperCase() })
                    }
                    maxLength={3}
                    required
                  />
                </label>
                <label>
                  <span>Budget</span>
                  <input
                    type="number"
                    min="0"
                    step="50"
                    value={member.budget_usd}
                    onChange={(event) => updateMember(index, { budget_usd: Number(event.target.value) })}
                    required
                  />
                </label>
              </div>

              <label>
                <span>Food restrictions</span>
                <input
                  value={member.food_restrictions.join(", ")}
                  onChange={(event) =>
                    updateMember(index, {
                      food_restrictions: event.target.value
                        .split(",")
                        .map((item) => item.trim())
                        .filter(Boolean),
                    })
                  }
                  placeholder="vegetarian, gluten_free, halal"
                />
              </label>

              <label>
                <span>Preference notes</span>
                <textarea
                  value={member.preference_notes}
                  onChange={(event) => updateMember(index, { preference_notes: event.target.value })}
                  rows={3}
                />
              </label>

              <div className="slider-grid">
                {PREFERENCE_KEYS.map((key) => (
                  <label className="slider-field" key={key}>
                    <span>
                      {titleize(key)}
                      <strong>{Math.round((member.preference_vector[key] || 0) * 100)}</strong>
                    </span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.1"
                      value={member.preference_vector[key] ?? 0}
                      onChange={(event) => updatePreference(index, key, event.target.value)}
                    />
                  </label>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>

      {error ? <div className="error-banner">{error}</div> : null}

      <div className="submit-bar">
        <button className="primary-button" type="submit" disabled={submitting}>
          {submitting ? <Loader2 className="spin" size={18} /> : <Send size={18} />}
          {submitting ? "Creating trip" : "Start planning trip"}
        </button>
      </div>
    </form>
  );
}

function SummaryItem({ icon, label, value }) {
  return (
    <div className="summary-item">
      {icon}
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function normalizePayload(form) {
  const members = form.members.map((member, index) => ({
    ...member,
    member_id: member.member_id || member.name.toLowerCase().replace(/\W+/g, "_") || `traveler_${index + 1}`,
    origin_city: member.origin_city.trim().toUpperCase(),
    budget_usd: Number(member.budget_usd || 0),
    is_leader: member.is_leader,
    preference_vector: Object.fromEntries(
      PREFERENCE_KEYS.map((key) => [key, Number(member.preference_vector[key] || 0)]),
    ),
  }));

  if (!members.some((member) => member.is_leader) && members[0]) members[0].is_leader = true;

  return {
    group_notes: form.group_notes,
    start_date: form.start_date,
    end_date: form.end_date,
    members,
  };
}
