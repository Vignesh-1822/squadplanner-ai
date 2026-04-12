import { NavLink, Link } from "react-router-dom"
import { Search, Settings, PlusCircle } from "lucide-react"
import Logo from "@/atoms/Logo"

const tabs = [
  { label: "Home",         to: "/",        end: true },
  { label: "My Trips",     to: "/trips" },
  { label: "Explore",      to: "/explore" },
  { label: "Shared Trips", to: "/shared" },
  { label: "Stats",        to: "/stats" },
]

const HomeHeader = () => (
  <header className="flex items-center justify-between px-8 pt-5 pb-3">
    {/* Logo — no background */}
    <Logo />

    {/* Nav tabs — glass pill only around these */}
    <nav className="flex items-center gap-0.5 bg-white/40 backdrop-blur-md rounded-2xl px-2 py-1.5 border border-white/60 shadow-sm">
      {tabs.map(({ label, to, end }) => (
        <NavLink
          key={to}
          to={to}
          end={end}
          className={({ isActive }) =>
            `px-4 py-1.5 text-sm transition-colors ${
              isActive
                ? "text-black font-bold"
                : "text-gray-500 hover:text-black font-medium"
            }`
          }
        >
          {label}
        </NavLink>
      ))}
    </nav>

    {/* Actions — no background */}
    <div className="flex items-center gap-1.5">
      <button className="w-8 h-8 flex items-center justify-center rounded-xl text-gray-500 hover:bg-black/5 transition-colors">
        <Search size={16} />
      </button>
      <button className="w-8 h-8 flex items-center justify-center rounded-xl text-gray-500 hover:bg-black/5 transition-colors">
        <Settings size={16} />
      </button>
      <Link
        to="/trips/new"
        className="flex items-center gap-1.5 px-4 py-2 rounded-full bg-primary text-black text-sm font-bold hover:bg-primary-dim transition-colors volt-glow ml-1"
      >
        <PlusCircle size={14} />
        Plan a new trip
      </Link>
    </div>
  </header>
)

export default HomeHeader
