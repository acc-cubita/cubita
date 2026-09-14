import { useEffect, useState } from 'react'
import {
  AlertTriangle,
  CheckCircle2,
  ListTree,
  RotateCcw,
  Save,
  Sparkles,
  Trash2,
  Undo2,
} from 'lucide-react'
import {
  applyChartTemplate,
  deleteAccount,
  fetchChartTemplates,
  fetchCodingRule,
  fetchDeletableAccounts,
  revertChartTemplate,
  setCodingRule,
  wipeChart,
  type ChartTemplate,
  type CodingRule,
  type DeletableAccount,
} from '../api'
import { EmptyState } from '../components/EmptyState'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'

/**
 * کدینگ — قاعده‌ی شماره‌گذاریِ حساب‌ها و قالب‌های آماده‌ی صنفی.
 *
 * **چرا این‌جا و نه در درختواره.** هر دو تنظیم‌اند، نه کارِ روزمره: قاعده‌ی کدینگ
 * یک‌بار در عمرِ کسب‌وکار تعیین می‌شود و قالب هم یک‌بار درج می‌شود. نشستنشان بالای
 * درختواره یعنی کاربری که روزی صد بار حساب را باز می‌کند، هر بار از کنارِ دکمه‌ای رد
 * شود که نباید بزند — و همان اتفاق افتاد: چهار قالب پشتِ هم درج شد و چارت پر از
 * حسابِ بی‌ربطِ چهار صنف شد.
 *
 * قاعده‌ی کدینگ پیش‌تر در «روش‌های شماره‌گذاری» بود. آن‌جا هم غریبه بود: آن صفحه
 * شماره‌ی سریِ *اسناد* را تنظیم می‌کند، نه کدِ *حساب‌ها*. دو مفهومِ متفاوت‌اند که
 * فقط واژه‌ی «شماره» مشترک دارند.
 */

const fa = (n: number) => n.toLocaleString('fa-IR')

/** پیش‌فرضِ سرویس — همان ساختارِ چارتِ کاشته‌شده. */
const DEFAULT_WIDTHS = [1, 1, 2, 2]
//: آینه‌ی `MIN_WIDTH, MAX_WIDTH = 1, 6` در `services/account_coding.py`.
const MIN_WIDTH = 1
const MAX_WIDTH = 6

type Msg = { text: string; kind: 'ok' | 'err' }

export function CodingPage({ token }: { token: string }) {
  const [msg, setMsg] = useState<Msg | null>(null)

  return (
    <div className="page panels">
      <PageHeader
        icon={ListTree}
        title="کدینگ"
        description="قاعده‌ی کدِ حساب‌ها و قالب‌های آماده‌ی صنفی. یک‌بار تنظیم می‌شود و بعد کارتان با درختواره است."
      />

      {msg && (
        <div className={`fy-note ${msg.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
          {msg.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <div>{msg.text}</div>
        </div>
      )}

      <CodingRuleCard token={token} onMessage={setMsg} />
      <ChartTemplatesCard token={token} onMessage={setMsg} />
      <DeleteAccountsCard token={token} onMessage={setMsg} />
      <WipeChartCard token={token} onMessage={setMsg} />
    </div>
  )
}

// ── قاعده‌ی کدینگ ─────────────────────────────────────────────────────────────

function CodingRuleCard({ token, onMessage }: { token: string; onMessage: (m: Msg) => void }) {
  const [rule, setRule] = useState<CodingRule | null>(null)
  const [draft, setDraft] = useState<number[] | null>(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    void fetchCodingRule(token)
      .then(setRule)
      .catch(() => {})
  }, [token])

  const widths = draft ?? rule?.widths ?? DEFAULT_WIDTHS
  const names = rule?.levels.map((l) => l.name) ?? ['گروه', 'کل', 'معین', 'تفصیلی']
  // پیش‌نمایش محلی محاسبه می‌شود تا با هر تیک زنده عوض شود، نه پس از ذخیره.
  const samples = widths.reduce<string[]>((acc, w, i) => {
    acc.push((acc[i - 1] ?? '') + '1'.padStart(w, '0'))
    return acc
  }, [])
  const dirty = draft != null && JSON.stringify(draft) !== JSON.stringify(rule?.widths)

  async function save() {
    if (!draft) return
    setBusy(true)
    try {
      const next = await setCodingRule(token, draft)
      setRule(next)
      setDraft(null)
      onMessage({ text: 'قاعده‌ی کدینگ ذخیره شد. حساب‌های موجود دست نخوردند.', kind: 'ok' })
    } catch (err) {
      onMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard
      icon={ListTree}
      title="قاعده‌ی کدِ حساب‌ها"
      description="کدِ هر حساب = کدِ سرفصلش + چند رقم. این‌جا تعیین می‌کنید هر سطح چند رقم بگیرد."
      actions={
        dirty ? (
          <button type="button" onClick={() => setDraft(null)} disabled={busy}>
            <RotateCcw size={13} /> انصراف
          </button>
        ) : undefined
      }
    >
      <div className="cd-levels">
        {widths.map((w, i) => (
          <label key={i} className="cd-level">
            <span className="cd-level-name">{names[i]}</span>
            <input
              type="number"
              min={1}
              max={6}
              value={w}
              onChange={(e) => {
                const next = [...widths]
                //: **محدودکردن اجباری است، نه آرایشی.** `min`/`max`ِ HTML فقط
                //: راهنمای‌اند و مرورگر هر عددی را می‌پذیرد (تایپ یا paste). خطِ
                //: پیش‌نمایشِ بالا `'1'.padStart(w, '0')` می‌زند، پس عددِ نُه‌رقمی
                //: یعنی رشته‌ای بزرگ‌تر از سقفِ V8 (۵۳۶٬۸۷۰٬۸۸۹) و
                //: `RangeError: Invalid string length` در بدنه‌ی کامپوننت — یعنی
                //: صفحه‌ی سفید. حتی زیرِ آن سقف هم هر رندر صدها مگابایت می‌گیرد.
                //: همان بازه‌ی `MIN_WIDTH/MAX_WIDTH`ِ بک‌اند
                //: (`services/account_coding.py`) این‌جا تکرار می‌شود.
                next[i] = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, Math.trunc(Number(e.target.value)) || MIN_WIDTH))
                setDraft(next)
              }}
            />
            <span className="cd-level-sample">{samples[i]}</span>
          </label>
        ))}
      </div>

      <p className="bk-hint cd-preview">
        نمونه: {samples.join(' ← ')} — یعنی حسابِ سطحِ «{names[names.length - 1]}»{' '}
        {samples[samples.length - 1].length.toLocaleString('fa-IR')} رقم می‌شود.
      </p>

      <div className="invoice-form-footer">
        <button type="button" className="btn-primary" onClick={() => void save()} disabled={!dirty || busy}>
          <Save size={13} /> ذخیره‌ی قاعده
        </button>
      </div>

      <p className="bk-hint">
        حساب‌های موجود بازشماره‌گذاری نمی‌شوند؛ کدِ حساب روی اسناد و گزارش‌های چاپ‌شده نشسته است.
        قاعده از این پس روی حسابِ تازه اعمال می‌شود و کدِ خارج از قاعده رد خواهد شد.
      </p>
    </SectionCard>
  )
}

// ── قالب‌های صنفی ─────────────────────────────────────────────────────────────

function ChartTemplatesCard({ token, onMessage }: { token: string; onMessage: (m: Msg) => void }) {
  const [templates, setTemplates] = useState<ChartTemplate[]>([])
  const [busy, setBusy] = useState(false)

  const refresh = () => fetchChartTemplates(token).then(setTemplates)

  useEffect(() => {
    void refresh().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function apply(t: ChartTemplate) {
    //: تأیید برای *درج* هم لازم است، نه فقط برای برگرداندن. درج ده‌ها حساب اضافه
    //: می‌کند و همین بود که یک‌بار چارت را پر از حسابِ بی‌ربطِ چهار صنف کرد —
    //: همان اتفاقی که ساختنِ «برگرداندن» را ضروری کرد.
    const count = t.missing
      ? `${fa(t.missing)} حسابِ تازه به چارت اضافه می‌شود.`
      : 'این قالب از قبل کامل است و چیزی اضافه نمی‌شود.'
    if (!window.confirm(`«${t.label}» درج شود؟\n\n${count}`)) return
    setBusy(true)
    try {
      const r = await applyChartTemplate(token, t.key)
      await refresh()
      onMessage({
        text: r.created
          ? `«${t.label}» درج شد — ${fa(r.created)} حساب اضافه شد.`
          : `«${t.label}» از قبل کامل بود؛ چیزی اضافه نشد.`,
        kind: 'ok',
      })
    } catch (err) {
      onMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  async function revert(t: ChartTemplate) {
    //: تأیید می‌گیریم چون برخلافِ درج، این عملیات حذف است — و کاربر باید بداند که
    //: حسابِ استفاده‌شده نمی‌رود، وگرنه از نتیجه‌ی نصفه گیج می‌شود.
    if (!window.confirm(`حساب‌های بی‌استفاده‌ی «${t.label}» برداشته شوند؟ حسابی که سند خورده یا زیرحساب دارد می‌ماند.`))
      return
    setBusy(true)
    try {
      const r = await revertChartTemplate(token, t.key)
      await refresh()
      const kept = r.kept.length ? ` ${fa(r.kept.length)} حساب ماند: ${r.kept.map((k) => `${k.code} (${k.reason})`).join('، ')}.` : ''
      onMessage({
        text: r.removed
          ? `${fa(r.removed)} حساب از «${t.label}» برداشته شد.${kept}`
          : `چیزی برداشته نشد.${kept}`,
        kind: 'ok',
      })
    } catch (err) {
      onMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard
      icon={Sparkles}
      title="درج حساب‌های پیش‌فرض"
      description="حساب‌های استانداردِ صنفتان را یک‌جا اضافه کنید. هر قالب = حساب‌های عمومی + حساب‌های تخصصیِ همان صنف."
    >
      {templates.length === 0 ? (
        <p className="muted">در حال بارگذاری…</p>
      ) : (
        <div className="tpl-grid">
          {templates.map((t) => (
            <div key={t.key} className={`tpl-card${t.missing === 0 ? ' done' : ''}`}>
              <span className="tpl-title">{t.label}</span>
              <span className="tpl-hint">{t.hint}</span>
              <span className="tpl-meta">
                {t.missing === 0
                  ? 'همه‌ی حساب‌ها موجود است'
                  : `${fa(t.missing)} حساب از ${fa(t.total)} اضافه می‌شود`}
              </span>
              <div className="tpl-actions">
                <button type="button" onClick={() => void apply(t)} disabled={busy || t.missing === 0}>
                  <Sparkles size={13} /> درج
                </button>
                <button
                  type="button"
                  onClick={() => void revert(t)}
                  disabled={busy || t.missing === t.total}
                  title="حساب‌های بی‌استفاده‌ی این قالب را برمی‌دارد"
                >
                  <Undo2 size={13} /> برگرداندن
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
      <p className="bk-hint">
        حسابِ موجود هرگز دست نمی‌خورد و اجرای دوباره چیزی اضافه نمی‌کند. می‌توانید بیش از یک قالب را
        اعمال کنید — مثلاً کسب‌وکاری که هم تولید دارد هم بازرگانی.
      </p>
      <p className="bk-hint">
        «برگرداندن» فقط حسابِ بی‌استفاده را برمی‌دارد. حسابی که در سند آمده، زیرحساب دارد، یا سیستمی
        است می‌ماند و دلیلش گزارش می‌شود — دفتر نباید بشکند.
      </p>
    </SectionCard>
  )
}

// ── حذفِ حساب ─────────────────────────────────────────────────────────────────

/**
 * حذفِ حساب — عمداً این‌جا و نه در درختواره.
 *
 * دکمه‌ی ویرانگر کنارِ دکمه‌ای که روزی صد بار زده می‌شود، دیر یا زود اشتباه زده
 * می‌شود. درختواره کارِ روزمره است؛ حذفِ سرفصل تصمیمِ ساختاری است و باید عمدی باشد.
 * غیرفعال‌سازی همان‌جا ماند، چون برگشت‌پذیر است.
 *
 * فهرست *همه* را نشان می‌دهد، نه فقط پاک‌شدنی‌ها: کاربری که دنبالِ حسابی می‌گردد و
 * پیدایش نمی‌کند، فکر می‌کند اشتباه از اوست. حسابِ نگه‌داشتنی با دلیلش می‌آید.
 */
function DeleteAccountsCard({ token, onMessage }: { token: string; onMessage: (m: Msg) => void }) {
  const [rows, setRows] = useState<DeletableAccount[]>([])
  const [busy, setBusy] = useState(false)
  const [search, setSearch] = useState('')
  const [onlyDeletable, setOnlyDeletable] = useState(false)

  const refresh = () => fetchDeletableAccounts(token).then(setRows)

  useEffect(() => {
    void refresh().catch(() => {})
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token])

  async function remove(row: DeletableAccount) {
    if (!window.confirm(`حسابِ «${row.code} ${row.name}» برای همیشه حذف شود؟`)) return
    setBusy(true)
    try {
      await deleteAccount(token, row.id)
      await refresh()
      onMessage({ text: `حسابِ «${row.name}» حذف شد.`, kind: 'ok' })
    } catch (err) {
      onMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  const q = search.trim()
  const shown = rows.filter(
    (r) => (!onlyDeletable || r.can_delete) && (!q || r.code.includes(q) || r.name.includes(q)),
  )
  const deletable = rows.filter((r) => r.can_delete).length

  return (
    <SectionCard
      icon={Trash2}
      title="حذف حساب"
      description="فقط حسابی حذف می‌شود که سند نخورده، زیرحساب ندارد و سیستمی نیست. حسابِ سنددار را به‌جای حذف غیرفعال کنید."
    >
      <div className="chart-toolbar">
        <input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="جستجو نام یا کد…"
        />
        <label className="chart-toggle">
          <input
            type="checkbox"
            checked={onlyDeletable}
            onChange={(e) => setOnlyDeletable(e.target.checked)}
          />
          فقط حذف‌شدنی‌ها
        </label>
      </div>

      <p className="bk-hint">
        {fa(deletable)} حساب از {fa(rows.length)} حساب قابلِ حذف است.
      </p>

      {shown.length === 0 ? (
        <EmptyState icon={Trash2} text="حسابی با این جستجو نیست." />
      ) : (
        <div className="table-scroll">
          <table className="data-table cards-on-mobile">
            <thead>
              <tr>
                <th>حساب</th>
                <th>سطح</th>
                <th>وضعیت</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.id}>
                  <td data-label="حساب" className="card-title">
                    <span className="tree-code">{r.code}</span> {r.name}
                  </td>
                  <td data-label="سطح">
                    <span className="tree-level">{r.level}</span>
                  </td>
                  <td data-label="وضعیت">
                    {r.can_delete ? (
                      <span className="tree-level">قابلِ حذف</span>
                    ) : (
                      <span className="muted">{r.reason}</span>
                    )}
                  </td>
                  <td className="card-actions">
                    <button
                      type="button"
                      className="icon-btn-danger"
                      disabled={busy || !r.can_delete}
                      aria-label="حذف حساب"
                      title={r.can_delete ? 'حذف' : (r.reason ?? '')}
                      onClick={() => void remove(r)}
                    >
                      <Trash2 size={13} />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </SectionCard>
  )
}


// ── خام‌سازیِ درختواره ────────────────────────────────────────────────────────

/**
 * پاک‌کردنِ کلِ چارت — فقط پیش از ثبتِ اولین سند.
 *
 * پایین‌ترین کارت است و باید هم باشد: آخرین راهِ «از اول شروع کنم» است، نه کاری
 * روزمره. سرور خودش گارد دارد (با یک سند هم رد می‌کند)، ولی رابط باید پیش از آن
 * روشن بگوید چه از دست می‌رود — کدهای دلخواهی که کاربر روی حساب‌ها گذاشته.
 */
function WipeChartCard({ token, onMessage }: { token: string; onMessage: (m: Msg) => void }) {
  const [busy, setBusy] = useState(false)

  async function run() {
    if (
      !window.confirm(
        'کلِ درختواره‌ی حساب‌ها پاک شود؟\n\n' +
          'این کار فقط تا پیش از ثبتِ اولین سند ممکن است و برگشت ندارد. ' +
          'کدها و نام‌هایی که خودتان روی حساب‌ها گذاشته‌اید از بین می‌روند.',
      )
    )
      return
    setBusy(true)
    try {
      const r = await wipeChart(token)
      onMessage({
        text: r.kept.length
          ? `${fa(r.deleted)} حساب پاک شد؛ ${fa(r.kept.length)} حساب ماند چون جای دیگری به آن‌ها ارجاع دارد.`
          : `درختواره خام شد — ${fa(r.deleted)} حساب پاک شد.`,
        kind: 'ok',
      })
    } catch (err) {
      onMessage({ text: err instanceof Error ? err.message : 'خطای ناشناخته', kind: 'err' })
    } finally {
      setBusy(false)
    }
  }

  return (
    <SectionCard
      icon={AlertTriangle}
      title="خام‌سازی درختواره"
      description="کلِ چارت را پاک می‌کند تا از صفر بسازید. فقط تا پیش از ثبتِ اولین سند ممکن است؛ بعد از آن سرور ردش می‌کند."
    >
      <button type="button" className="btn-danger" onClick={() => void run()} disabled={busy}>
        <Trash2 size={14} /> پاک کردنِ همه‌ی حساب‌ها
      </button>
    </SectionCard>
  )
}
