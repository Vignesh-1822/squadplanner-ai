const colors = ["bg-primary", "bg-tertiary-container", "bg-secondary-container", "bg-surface-dim"]

const AvatarStack = ({ names = [], max = 4 }) => {
  const visible = names.slice(0, max)
  const overflow = names.length - max

  return (
    <div className="flex -space-x-2">
      {visible.map((name, i) => (
        <div
          key={i}
          className={`w-7 h-7 rounded-full border-2 border-surface-bright flex items-center justify-center text-[10px] font-bold text-on-surface ${colors[i % colors.length]}`}
          title={name}
        >
          {name[0].toUpperCase()}
        </div>
      ))}
      {overflow > 0 && (
        <div className="w-7 h-7 rounded-full border-2 border-surface-bright bg-surface-highest flex items-center justify-center text-[10px] font-bold text-on-surface-variant">
          +{overflow}
        </div>
      )}
    </div>
  )
}

export default AvatarStack
