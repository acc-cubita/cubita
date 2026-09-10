import { useEffect, useState } from 'react'
import { AlertTriangle, BookMarked, CheckCircle2, FileText, Info, Layers, Settings2 } from 'lucide-react'
import {
  fetchChequeControl,
  fetchTafsiliMode,
  setChequeControl,
  setTafsiliMode,
  type ChequeControl,
  type ChequeControlOption,
  type TafsiliMode,
  type TafsiliModeOption,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'

/**
 * شخصی‌سازی — رفتارهایی که هر کسب‌وکار خودش انتخاب می‌کند.
 *
 * این صفحه جای تنظیماتی است که **یک جوابِ درستِ واحد ندارند**. مثلِ سطحِ اجبارِ
 * تفصیلی: سخت‌گیری گزارشِ کامل‌تری می‌دهد ولی می‌تواند ثبتِ فاکتور را متوقف کند، و
 * اینکه کدام‌یک برای یک کسب‌وکارِ خاص بهتر است را فقط خودش می‌داند.
 *
 * قاعده‌ی این صفحه: **هر گزینه باید بگوید چه اتفاقی می‌افتد، نه فقط نامش را.**
 * انتخابی که پیامدش را نگویی، انتخاب نیست — حدس است. به همین دلیل متنِ پیامدها از
 * سرور می‌آید نه از این‌جا: اگر قاعده‌ای عوض شود، همین‌جا هم عوض می‌شود و رابط
 * چیزی نمی‌گوید که دیگر درست نیست.
 */
export function PersonalizationPage({ token }: { token: string }) {
  const [msg, setMsg] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)

  return (
    <div className="page panels">
      <PageHeader
        icon={Settings2}
        title="شخصی‌سازی"
        description="رفتارهایی که یک جوابِ درستِ واحد ندارند و هر کسب‌وکار خودش انتخاب می‌کند. زیرِ هر گزینه نوشته شده که انتخابش چه چیزی را عوض می‌کند."
      />

      {msg && (
        <div className={`fy-note ${msg.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
          {msg.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <div>{msg.text}</div>
        </div>
      )}

      <TafsiliModeCard token={token} onMessage={setMsg} />
      <ChequeControlCard token={token} onMessage={setMsg} />
    </div>
  )
}

// ── سطحِ اجبارِ تفصیلی ─────────────────────────────────────────────────────────

/** یک ردیفِ «چه اتفاقی می‌افتد» — آیکون، عنوان، و متنی که از سرور آمده. */
function Effect({ icon: Icon, title, text }: { icon: typeof FileText; title?: string; text: string }) {
  return (
    <div className="pz-effect">
      <Icon size={14} />
      <div>
        {/* عنوان اختیاری است: بعضی پیامدها خودشان یک جمله‌ی کاملند و سرتیتر
            نمی‌خواهند — عنوانِ خالی فقط یک فضای خالیِ گیج‌کننده می‌ساخت. */}
        {title && <strong>{title}</strong>}
        <span>{text}</span>
      </div>
    </div>
  )
}

function TafsiliModeCard({
  token,
  onMessage,
}: {
  token: string
  onMessage: (m: { text: string; kind: 'ok' | 'err' }) => void
}) {
  const [data, setData] = useState<TafsiliMode | null>(null)
  //: انتخابِ *در حالِ بررسی* جدا از انتخابِ ذخیره‌شده نگه داشته می‌شود، تا کاربر
  //: بتواند پیامدِ گزینه‌ها را بخواند بی‌آنکه چیزی عوض شود. ذخیره با دکمه‌ی صریح.
  const [picked, setPicked] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    void fetchTafsiliMode(token)
      .then((r) => {
        setData(r)
        setPicked(r.mode)
      })
      .catch(() => {})
  }, [token])

  async function save() {
    if (!data || !picked || picked === data.mode) return
    setBusy(true)
    try {
      const r = await setTafsiliMode(token, picked)
      setData(r)
      setPicked(r.mode)
      const label = r.options.find((o) => o.key === r.mode)?.label ?? r.mode
      onMessage({ text: `سطحِ اجبارِ تفصیلی روی «${label}» تنظیم شد.`, kind: 'ok' })
    } catch (err) {
      onMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const shown: TafsiliModeOption | undefined = data?.options.find((o) => o.key === picked)
  const dirty = data != null && picked != null && picked !== data.mode

  return (
    <SectionCard
      icon={Layers}
      title="سطح اجبار تفصیلی"
      description="حسابی که «تفصیلی پذیر» است یعنی ردیفِ سندش باید تفصیلی داشته باشد. این‌جا تعیین می‌کنید چقدر اجباری — و روی چه چیزهایی."
    >
      {data == null ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : (
        <>
          <div className="pz-options">
            {data.options.map((o) => (
              <label key={o.key} className={`pz-option${picked === o.key ? ' pz-option--on' : ''}`}>
                <input
                  type="radio"
                  name="tafsili-mode"
                  checked={picked === o.key}
                  onChange={() => setPicked(o.key)}
                />
                <div className="pz-option-body">
                  <div className="pz-option-head">
                    <strong>{o.label}</strong>
                    {o.is_default && <span className="chart-trait-tag">پیش‌فرض</span>}
                    {data.mode === o.key && <span className="fy-badge fy-badge--open">فعلی</span>}
                  </div>
                  <span className="pz-option-hint">{o.hint}</span>
                </div>
              </label>
            ))}
          </div>

          {shown && (
            <div className="pz-effects">
              <div className="pz-effects-head">
                <Info size={14} />
                اگر «{shown.label}» را انتخاب کنید چه می‌شود؟
              </div>
              <Effect icon={FileText} title="سندِ دستی" text={shown.effects.manual} />
              <Effect icon={Layers} title="فاکتور، انبار، تولید و حقوق" text={shown.effects.module} />
              <Effect icon={Info} title="گزارشِ «ردیف‌های بدونِ تفصیلی»" text={shown.effects.report} />
              {/* هشدار جداست و رنگِ دیگری دارد: سه ردیفِ بالا می‌گویند «چه می‌شود»،
                  این می‌گوید «حواست به چه باشد» — و همان است که معمولاً خوانده نمی‌شود. */}
              <div className="pz-warning">
                <AlertTriangle size={14} />
                <span>{shown.effects.warning}</span>
              </div>
            </div>
          )}

          <div className="pz-actions">
            <button type="button" className="btn-primary" onClick={() => void save()} disabled={!dirty || busy}>
              ذخیره‌ی انتخاب
            </button>
            {dirty && (
              <button type="button" onClick={() => setPicked(data.mode)} disabled={busy}>
                انصراف
              </button>
            )}
            {/* تغییرِ تنظیم فقط ثبت‌های بعدی را می‌سنجد. گفتنش این‌جا لازم است چون
                کاربری که «اجباری» می‌زند انتظار دارد گذشته هم اصلاح شود. */}
            <span className="bk-hint">
              این تنظیم فقط ثبت‌های بعدی را می‌سنجد؛ سندهای گذشته دست‌نخورده می‌مانند و در
              گزارشِ «ردیف‌های بدونِ تفصیلی» دیده می‌شوند.
            </span>
          </div>
        </>
      )}
    </SectionCard>
  )
}


// ── کنترلِ شماره‌ی چکِ پرداختنی ────────────────────────────────────────────────

/**
 * آیا چکِ پرداختنی باید حتماً از یک دسته‌چک صادر شود؟
 *
 * **مرزی که این کارت عوضش نمی‌کند:** بازه و تکراری‌نبودنِ برگ در هر دو حالت
 * سنجیده می‌شوند. اگر دسته‌ای انتخاب شود، شماره باید واقعاً از همان دسته و
 * خرج‌نشده باشد — وگرنه «برگِ مانده» عددِ دروغ می‌دهد. این انتخاب فقط می‌گوید
 * صدورِ چکِ **بی‌دسته** مجاز است یا نه.
 */
function ChequeControlCard({
  token,
  onMessage,
}: {
  token: string
  onMessage: (m: { text: string; kind: 'ok' | 'err' }) => void
}) {
  const [data, setData] = useState<ChequeControl | null>(null)
  const [picked, setPicked] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    void fetchChequeControl(token)
      .then((r) => {
        setData(r)
        setPicked(r.mode)
      })
      .catch(() => {})
  }, [token])

  async function save() {
    if (!data || !picked || picked === data.mode) return
    setBusy(true)
    try {
      const r = await setChequeControl(token, picked)
      setData(r)
      setPicked(r.mode)
      const label = r.options.find((o) => o.key === r.mode)?.label ?? r.mode
      onMessage({ text: `کنترلِ شماره‌ی چک روی «${label}» تنظیم شد.`, kind: 'ok' })
    } catch (err) {
      onMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const shown: ChequeControlOption | undefined = data?.options.find((o) => o.key === picked)
  const dirty = data != null && picked != null && picked !== data.mode

  return (
    <SectionCard
      icon={BookMarked}
      title="کنترل شماره چک پرداختنی"
      description="شماره‌ی چکی که خودتان صادر می‌کنید یک متنِ آزاد باشد، یا حتماً برگی از یک دسته‌چکِ واقعی؟"
    >
      {data == null ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : (
        <>
          <div className="pz-options">
            {data.options.map((o) => (
              <label key={o.key} className={`pz-option${picked === o.key ? ' pz-option--on' : ''}`}>
                <input
                  type="radio"
                  name="cheque-number-control"
                  checked={picked === o.key}
                  onChange={() => setPicked(o.key)}
                />
                <div className="pz-option-body">
                  <div className="pz-option-head">
                    <strong>{o.label}</strong>
                    {o.is_default && <span className="chart-trait-tag">پیش‌فرض</span>}
                    {data.mode === o.key && <span className="fy-badge fy-badge--open">فعلی</span>}
                  </div>
                  <span className="pz-option-hint">{o.hint}</span>
                </div>
              </label>
            ))}
          </div>

          {shown && (
            <div className="pz-effects">
              <div className="pz-effects-head">
                <Info size={14} />
                اگر «{shown.label}» را انتخاب کنید چه می‌شود؟
              </div>
              {shown.effects.map((text) => (
                <Effect key={text} icon={CheckCircle2} text={text} />
              ))}
            </div>
          )}

          <div className="pz-actions">
            <button type="button" className="btn-primary" onClick={() => void save()} disabled={!dirty || busy}>
              ذخیره‌ی انتخاب
            </button>
            {dirty && (
              <button type="button" onClick={() => setPicked(data.mode)} disabled={busy}>
                انصراف
              </button>
            )}
            <span className="bk-hint">
              این تنظیم فقط صدورهای بعدی را می‌سنجد؛ چک‌های ثبت‌شده دست‌نخورده می‌مانند.
            </span>
          </div>
        </>
      )}
    </SectionCard>
  )
}
