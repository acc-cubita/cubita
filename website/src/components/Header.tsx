export function Header() {
  const demoUrl = import.meta.env.VITE_DEMO_URL ?? 'https://demo.cubita.ir'

  return (
    <header className="site-header">
      <div className="container">
        <a href="/" className="brand">
          <span className="brand-mark">C</span>
          کوبیتا
        </a>
        <nav className="site-nav">
          <a href="#features">امکانات</a>
          <a href="#pricing">پلن‌ها</a>
          <a href="#demo">دمو</a>
        </nav>
        <a href={demoUrl} target="_blank" rel="noreferrer" className="btn btn-outline">
          مشاهده دمو
        </a>
      </div>
    </header>
  )
}
