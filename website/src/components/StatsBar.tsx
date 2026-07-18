const STATS = [
  { value: '۶', label: 'ماژول اصلی حسابداری' },
  { value: '۱۰۰٪', label: 'قابلیت کار آفلاین' },
  { value: '۵', label: 'نقش کاربری مجزا' },
  { value: '۲۴/۷', label: 'دسترسی به نسخه‌ی وب' },
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
