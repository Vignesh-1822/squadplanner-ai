/** Small labelled figure used across the hub sidebars and stat rows. */
const StatTile = ({ icon: Icon, label, value, tone = "light" }) => {
  const dark = tone === "dark"
  return (
    <div
      className={`rounded-xl p-3.5 ${
        dark ? "bg-white/10 border border-white/10" : "bg-white/60 border border-slate-100"
      }`}
    >
      <p
        className={`flex items-center gap-1.5 text-[10px] font-black uppercase tracking-widest mb-1 ${
          dark ? "text-white/50" : "text-slate-400"
        }`}
      >
        {Icon && <Icon size={11} className="text-primary" />}
        {label}
      </p>
      <p className={`text-lg font-black leading-none ${dark ? "text-white" : "text-slate-900"}`}>
        {value}
      </p>
    </div>
  )
}

export default StatTile
