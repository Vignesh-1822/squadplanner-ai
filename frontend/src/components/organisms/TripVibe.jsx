import { Activity } from "lucide-react"
import { groupPreferenceVector } from "@/lib/itinerary"

const CENTRE = 50
const MAX_RADIUS = 40
const RINGS = [1, 0.66, 0.33]

function getPoint(index, total, scale) {
  const angle = (Math.PI * 2 * index) / total - Math.PI / 2
  return {
    x: CENTRE + Math.cos(angle) * MAX_RADIUS * scale,
    y: CENTRE + Math.sin(angle) * MAX_RADIUS * scale,
  }
}

const BAR_COLORS = ["bg-primary", "bg-[#ff71cf]", "bg-slate-900"]

/**
 * Stitch Trip Vibe widget:
 * Glass card (lg:col-span-2), authentic SVG radar chart with concentric circles and volt polygon
 * on the left, ranked preference bars with Stitch colors and quote bubble on the right.
 */
const TripVibe = ({ members = [] }) => {
  const dimensions = groupPreferenceVector(members)
  if (!dimensions.length) return null

  const axes = [...dimensions].sort((a, b) => a.key.localeCompare(b.key))
  const total = axes.length
  const shapePoints = axes.map((dim, i) =>
    getPoint(i, total, Math.max(dim.value || 0.1, 0.15)),
  )

  const VIBE_PHRASES = {
    food: "incredible food",
    nightlife: "the nightlife and drinks",
    outdoor: "outdoor adventures",
    urban: "city walks and exploration",
    shopping: "shopping and local spots",
  }

  const EMOJIS = {
    food: "🍜",
    nightlife: "🍸",
    outdoor: "🌲",
    urban: "🏙️",
    shopping: "🛍️",
  }

  const topDimensions = dimensions.slice(0, 3)
  const topKey1 = dimensions[0]?.key
  const topKey2 = dimensions[1]?.key
  const phrase1 = VIBE_PHRASES[topKey1] || dimensions[0]?.label?.toLowerCase() || "fun adventures"
  const phrase2 = VIBE_PHRASES[topKey2] || dimensions[1]?.label?.toLowerCase() || "good vibes"
  const emoji = EMOJIS[topKey1] || "✨"

  const quoteText = `"Looks like we're mostly here for ${phrase1} and ${phrase2}!" ${emoji}✨`

  return (
    <section className="bg-white/60 backdrop-blur-xl rounded-3xl border border-white/70 shadow-sm p-6 lg:col-span-2 flex flex-col justify-between">
      <div>
        <header className="flex items-center justify-between gap-3 mb-6">
          <h2 className="flex items-center gap-2.5 text-xl font-black text-slate-900 tracking-tight">
            <Activity size={22} className="text-[#ff71cf]" />
            Trip Vibe
          </h2>
          <p className="text-xs font-bold text-slate-400 italic">
            Based on group preferences
          </p>
        </header>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 items-center">
          {/* Left: SVG Radar Chart (Extra Large with full label clearances) */}
          <div className="relative flex items-center justify-center p-2 min-h-[290px]">
            <svg
              viewBox="-22 -14 144 128"
              className="w-full max-w-[340px] h-auto overflow-visible"
              role="img"
              aria-label="Squad preference radar chart"
            >
              {/* Concentric Circles */}
              {RINGS.map((scale) => (
                <circle
                  key={scale}
                  cx={CENTRE}
                  cy={CENTRE}
                  r={MAX_RADIUS * scale}
                  fill="none"
                  stroke="rgba(15, 23, 42, 0.09)"
                  strokeWidth="0.8"
                />
              ))}

              {/* Radial Axis Lines */}
              {axes.map((dim, i) => {
                const endpoint = getPoint(i, total, 1)
                return (
                  <line
                    key={dim.key}
                    x1={CENTRE}
                    y1={CENTRE}
                    x2={endpoint.x}
                    y2={endpoint.y}
                    stroke="rgba(15, 23, 42, 0.09)"
                    strokeWidth="0.8"
                  />
                )
              })}

              {/* The Volt "Vibe" Shape */}
              <polygon
                points={shapePoints.map((p) => `${p.x},${p.y}`).join(" ")}
                fill="rgba(209, 249, 77, 0.45)"
                stroke="#d1f94d"
                strokeWidth="2.5"
                strokeLinejoin="round"
                className="filter drop-shadow-sm"
              />

              {/* Axis Label Tags with clean clearance */}
              {axes.map((dim, i) => {
                const p = getPoint(i, total, 1.15)
                const isLeft = p.x < CENTRE - 4
                const isRight = p.x > CENTRE + 4
                const anchor = isRight ? "start" : isLeft ? "end" : "middle"

                return (
                  <text
                    key={dim.key}
                    x={p.x}
                    y={p.y}
                    textAnchor={anchor}
                    dominantBaseline="middle"
                    className="fill-slate-600 font-extrabold uppercase select-none"
                    style={{ fontSize: "5.2px", letterSpacing: "0.04em" }}
                  >
                    {dim.key}
                  </text>
                )
              })}
            </svg>
          </div>

          {/* Right: Preference Bars & Quote Bubble */}
          <div className="space-y-4">
            <div className="space-y-3.5">
              {topDimensions.map((dim, i) => {
                const percent = Math.round((dim.value || 0) * 100)
                const barColor = BAR_COLORS[i % BAR_COLORS.length]
                return (
                  <div key={dim.key} className="space-y-1.5">
                    <div className="flex justify-between text-[11px] font-black uppercase tracking-tight text-slate-800">
                      <span>{dim.label}</span>
                      <span>{percent}%</span>
                    </div>
                    <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-700 ${barColor}`}
                        style={{ width: `${Math.max(percent, 4)}%` }}
                      />
                    </div>
                  </div>
                )
              })}
            </div>

            {/* Playful Stitch Quote Bubble */}
            <div className="pt-3.5 p-4 rounded-2xl bg-white/70 border border-white/60 shadow-sm italic text-xs md:text-sm text-slate-700 leading-relaxed">
              {quoteText}
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}

export default TripVibe
