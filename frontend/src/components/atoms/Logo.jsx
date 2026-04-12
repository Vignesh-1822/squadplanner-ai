const Logo = ({ collapsed = false }) => (
  <div className="flex items-center gap-2">
    <div className="w-8 h-8 rounded-md bg-primary flex items-center justify-center flex-shrink-0">
      <span className="text-black font-black text-sm leading-none">S</span>
    </div>
    {!collapsed && (
      <span className="font-black text-base tracking-tight text-black">
        SquadPlanner
      </span>
    )}
  </div>
)

export default Logo
