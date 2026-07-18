import { Boxes, TrendingUp, Wallet } from 'lucide-react'

export function ProductMockup() {
  return (
    <div className="mockup-wrap">
      <div className="mockup-card">
        <div className="mockup-titlebar">
          <span className="mockup-dot" style={{ background: '#ff5f57' }} />
          <span className="mockup-dot" style={{ background: '#febc2e' }} />
          <span className="mockup-dot" style={{ background: '#28c840' }} />
          <span className="mockup-url">acc.cubita.ir</span>
        </div>
        <div className="mockup-body">
          <div className="mockup-sidebar">
            <span className="mockup-side-item active" />
            <span className="mockup-side-item" />
            <span className="mockup-side-item" />
            <span className="mockup-side-item" />
            <span className="mockup-side-item" />
          </div>
          <div className="mockup-main">
            <div className="mockup-stat-row">
              <div className="mockup-stat">
                <span className="mockup-stat-label">فروش امروز</span>
                <span className="mockup-stat-value">۴۸,۲۰۰,۰۰۰</span>
              </div>
              <div className="mockup-stat">
                <span className="mockup-stat-label">مانده صندوق</span>
                <span className="mockup-stat-value">۱۲۲,۰۰۰,۰۰۰</span>
              </div>
            </div>
            <div className="mockup-chart">
              <span style={{ height: '40%' }} />
              <span style={{ height: '65%' }} />
              <span style={{ height: '50%' }} />
              <span style={{ height: '85%' }} />
              <span style={{ height: '60%' }} />
              <span style={{ height: '95%' }} />
              <span style={{ height: '70%' }} />
            </div>
            <div className="mockup-rows">
              <span className="mockup-row" />
              <span className="mockup-row" />
              <span className="mockup-row short" />
            </div>
          </div>
        </div>
      </div>

      <div className="floating-chip chip-1">
        <span className="floating-chip-icon">
          <Boxes size={16} />
        </span>
        <div>
          <b>۱۲+</b>
          <span>ماژول حسابداری</span>
        </div>
      </div>
      <div className="floating-chip chip-2">
        <span className="floating-chip-icon accent-2">
          <Wallet size={16} />
        </span>
        <div>
          <b>۱۰۰٪</b>
          <span>قابل‌کار آفلاین</span>
        </div>
      </div>
      <div className="floating-chip chip-3">
        <span className="floating-chip-icon">
          <TrendingUp size={16} />
        </span>
        <div>
          <b>زنده</b>
          <span>گزارش‌های مالی</span>
        </div>
      </div>
    </div>
  )
}
