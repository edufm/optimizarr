export function ProgressBar({ pct }: { pct: number }) {
  const clamped = Math.min(100, Math.max(0, pct))
  return (
    <div className="inline-progress">
      <div className="meter meter-compact">
        <div className="meter-fill" style={{ width: `${clamped.toFixed(0)}%` }} />
      </div>
      <span className="meter-label">{clamped.toFixed(0)}%</span>
    </div>
  )
}
