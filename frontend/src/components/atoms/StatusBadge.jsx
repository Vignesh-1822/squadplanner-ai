const variants = {
  active:   "bg-primary/20 text-on-surface",
  pending:  "bg-tertiary/20 text-tertiary",
  confirmed:"bg-green-100 text-green-800",
  draft:    "bg-surface-highest text-on-surface-variant",
}

const StatusBadge = ({ label, variant = "draft" }) => (
  <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-[11px] font-bold uppercase tracking-widest ${variants[variant] ?? variants.draft}`}>
    {label}
  </span>
)

export default StatusBadge
