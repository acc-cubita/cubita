import { useEffect, useRef } from 'react'

/**
 * heroِ بصریِ سبک — جایگزینِ صحنه‌ی WebGL. کارت‌های حسابداریِ شناور که فقط با CSS/SVG
 * ساخته شده‌اند: بدونِ three.js، بدونِ کانواس، بدونِ بارِ GPU. عمق از لایه‌بندی +
 * پارالاکسِ ماوس + انیمیشنِ شناوری می‌آید. هر لایه یک wrapperِ پارالاکس دارد و یک
 * فرزندِ float (تا transformِ این دو با هم تداخل نکنند).
 */

const bars = [0.42, 0.66, 0.5, 0.86, 0.62, 1]

export default function HeroVisual() {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
    let raf = 0
    const onMove = (e: PointerEvent) => {
      cancelAnimationFrame(raf)
      raf = requestAnimationFrame(() => {
        const px = e.clientX / window.innerWidth - 0.5
        const py = e.clientY / window.innerHeight - 0.5
        el.style.setProperty('--px', px.toFixed(3))
        el.style.setProperty('--py', py.toFixed(3))
      })
    }
    window.addEventListener('pointermove', onMove, { passive: true })
    return () => {
      window.removeEventListener('pointermove', onMove)
      cancelAnimationFrame(raf)
    }
  }, [])

  return (
    <div className="cc-visual" ref={ref} aria-hidden="true">
      <div className="cc-visual-glow" />

      {/* کارتِ داشبورد (اصلی) */}
      <div className="cc-layer cc-l-dash" style={{ ['--d' as string]: 1 }}>
        <div className="cc-fl" style={{ ['--dur' as string]: '7s' }}>
          <div className="cc-panel cc-dash">
            <div className="cc-dash-top">
              <div>
                <span className="cc-dash-label">درآمدِ این ماه</span>
                <span className="cc-dash-num">۱۲۴٬۸۰۰٬۰۰۰</span>
              </div>
              <span className="cc-dash-badge">▲ ۱۸٪</span>
            </div>
            <div className="cc-bars">
              {bars.map((h, i) => (
                <span key={i} className="cc-bar" style={{ ['--h' as string]: `${h * 100}%`, ['--gd' as string]: `${0.25 + i * 0.09}s` }} />
              ))}
            </div>
            <div className="cc-dash-foot">
              <span className="cc-dot cc-dot-teal" /> فروش
              <span className="cc-dot cc-dot-blue" /> هزینه
              <span className="cc-dash-foot-sp" /> ۶ ماهِ اخیر
            </div>
          </div>
        </div>
      </div>

      {/* استکِ سکه */}
      <div className="cc-layer cc-l-coins" style={{ ['--d' as string]: 1.9 }}>
        <div className="cc-fl" style={{ ['--dur' as string]: '5.5s', ['--dl' as string]: '-1.5s' }}>
          <div className="cc-coins">
            <span className="cc-coin" style={{ ['--i' as string]: 3 }} />
            <span className="cc-coin" style={{ ['--i' as string]: 2 }} />
            <span className="cc-coin" style={{ ['--i' as string]: 1 }} />
            <span className="cc-coin cc-coin-top" style={{ ['--i' as string]: 0 }} />
          </div>
        </div>
      </div>

      {/* کارتِ بانکی */}
      <div className="cc-layer cc-l-card" style={{ ['--d' as string]: 1.5 }}>
        <div className="cc-fl" style={{ ['--dur' as string]: '6.5s', ['--dl' as string]: '-0.8s' }}>
          <div className="cc-bankcard">
            <span className="cc-chip" />
            <span className="cc-brand" />
            <div className="cc-cardnum">
              <i /><i /><i /><i />
            </div>
          </div>
        </div>
      </div>

      {/* چیپِ سود */}
      <div className="cc-layer cc-l-chip" style={{ ['--d' as string]: 2.4 }}>
        <div className="cc-fl" style={{ ['--dur' as string]: '5s', ['--dl' as string]: '-2.2s' }}>
          <div className="cc-statchip">
            <span className="cc-statchip-ico">▲</span>
            <div>
              <b>سودِ خالص</b>
              <span>+۲۳٪ نسبت به پارسال</span>
            </div>
          </div>
        </div>
      </div>

      {/* فاکتورِ کوچک */}
      <div className="cc-layer cc-l-inv" style={{ ['--d' as string]: 1.3 }}>
        <div className="cc-fl" style={{ ['--dur' as string]: '7.5s', ['--dl' as string]: '-3s' }}>
          <div className="cc-panel cc-invoice">
            <div className="cc-invoice-head">
              <span className="cc-invoice-title">فاکتورِ فروش</span>
              <span className="cc-invoice-no">#۱۴۰۳۲۷</span>
            </div>
            <span className="cc-invoice-line" style={{ width: '82%' }} />
            <span className="cc-invoice-line" style={{ width: '58%' }} />
            <span className="cc-invoice-line" style={{ width: '70%' }} />
            <div className="cc-invoice-total">جمعِ کل ۴٬۹۵۰٬۰۰۰</div>
          </div>
        </div>
      </div>
    </div>
  )
}
