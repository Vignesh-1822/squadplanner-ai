import { NavLink } from "react-router-dom"
import { LayoutDashboard, CalendarDays, Plane, Hotel, Wallet } from "lucide-react"

// Flights, Lodging and Budget are drawn but inert — the design has five tabs and hiding them
// would misrepresent the shape of the page. They light up when those tabs are built.
const TABS = [
  { to: "overview", label: "Overview", icon: LayoutDashboard, ready: true },
  { to: "itinerary", label: "Itinerary", icon: CalendarDays, ready: true },
  { to: "flights", label: "Flights", icon: Plane, ready: false },
  { to: "lodging", label: "Lodging", icon: Hotel, ready: false },
  { to: "budget", label: "Budget", icon: Wallet, ready: false },
]

const TripTabs = () => (
  <nav className="flex items-center gap-1 overflow-x-auto border-b border-slate-200/80">
    {TABS.map(({ to, label, icon: Icon, ready }) =>
      ready ? (
        <NavLink
          key={to}
          to={to}
          className={({ isActive }) =>
            `flex items-center gap-2 px-4 py-3 text-sm font-bold whitespace-nowrap border-b-2 -mb-px transition-colors ${
              isActive
                ? "border-primary text-slate-900"
                : "border-transparent text-slate-500 hover:text-slate-900"
            }`
          }
        >
          <Icon size={16} />
          {label}
        </NavLink>
      ) : (
        <span
          key={to}
          title="Coming soon"
          className="flex items-center gap-2 px-4 py-3 text-sm font-bold whitespace-nowrap border-b-2 border-transparent text-slate-300 cursor-not-allowed"
        >
          <Icon size={16} />
          {label}
        </span>
      ),
    )}
  </nav>
)

export default TripTabs
