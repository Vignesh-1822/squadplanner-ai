import { NavLink } from "react-router-dom"
import { LayoutDashboard, Map, Compass, Users, HelpCircle, Settings, PlusCircle } from "lucide-react"
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
} from "@/components/ui/sidebar"
import Logo from "@/atoms/Logo"

const navItems = [
  { label: "Home",         icon: LayoutDashboard, to: "/" },
  { label: "My Trips",     icon: Map,             to: "/trips" },
  { label: "Explore",      icon: Compass,         to: "/explore" },
  { label: "Shared Trips", icon: Users,           to: "/shared" },
  { label: "Help",         icon: HelpCircle,      to: "/help" },
]

const SideMenu = () => (
  <Sidebar collapsible="icon" className="border-r border-outline-variant bg-secondary">
    <SidebarHeader className="p-4 border-b border-white/10">
      <Logo />
    </SidebarHeader>

    <SidebarContent className="py-2">
      {/* User profile card */}
      <div className="mx-3 my-3 p-3 glass-card bg-white/10 border-white/10">
        <div className="flex items-center gap-3 mb-3">
          <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center font-black text-black text-sm flex-shrink-0">
            V
          </div>
          <div className="overflow-hidden">
            <p className="text-sm font-bold text-surface-bright truncate">Vignesh</p>
            <p className="text-[11px] text-white/50 truncate">@vignesh</p>
          </div>
        </div>
        <div className="flex justify-around border-t border-white/10 pt-3">
          <div className="w-px bg-white/10" />
        </div>
      </div>

      <SidebarGroup>
        <SidebarGroupContent>
          <SidebarMenu>
            {navItems.map(({ label, icon: Icon, to }) => (
              <SidebarMenuItem key={to}>
                <SidebarMenuButton asChild>
                  <NavLink
                    to={to}
                    end={to === "/"}
                    className={({ isActive }) =>
                      `flex items-center gap-3 px-3 py-2 rounded-xl text-sm font-medium transition-colors ${
                        isActive
                          ? "bg-primary text-black font-bold"
                          : "text-white/70 hover:text-surface-bright hover:bg-white/10"
                      }`
                    }
                  >
                    <Icon size={16} />
                    <span>{label}</span>
                  </NavLink>
                </SidebarMenuButton>
              </SidebarMenuItem>
            ))}
          </SidebarMenu>
        </SidebarGroupContent>
      </SidebarGroup>
    </SidebarContent>

    <SidebarFooter className="p-3 border-t border-white/10">
      <NavLink
        to="/trips/new"
        className="flex items-center justify-center gap-2 w-full py-2.5 rounded-xl bg-primary text-black text-sm font-bold hover:bg-primary-dim transition-colors volt-glow"
      >
        <PlusCircle size={15} />
        Plan a Trip
      </NavLink>
      <NavLink
        to="/settings"
        className="flex items-center gap-2 mt-2 px-3 py-2 rounded-xl text-white/50 hover:text-surface-bright hover:bg-white/10 text-sm transition-colors"
      >
        <Settings size={15} />
        <span>Settings</span>
      </NavLink>
    </SidebarFooter>
  </Sidebar>
)

export default SideMenu
