const STATS = [
  { value: '۱۲+', label: 'ماژول کامل حسابداری' },
  { value: '۱۰۰٪', label: 'کار بدون اینترنت' },
  { value: '۲', label: 'پلتفرم: دسکتاپ و وب' },
  { value: '۵', label: 'نقش کاربری با دسترسی مجزا' },
]

export function StatsBar() {
  return (
    <div className="stats-bar">
      <div className="container stats-bar-inner">
        {STATS.map((s) => (
          <div className="stat-chip" key={s.label}>
            <span className="stat-chip-value">{s.value}</span>
            <span className="stat-chip-label">{s.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
