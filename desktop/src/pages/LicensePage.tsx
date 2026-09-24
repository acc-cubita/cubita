import { useCallback, useEffect, useState } from 'react'
import { AlertTriangle, BadgeCheck, CheckCircle2, ClipboardCopy, Globe, KeyRound, ShieldCheck } from 'lucide-react'
import {
  activateLicenseOnline,
  fetchLicense,
  fetchLicenseRequestCode,
  fetchMe,
  installLicense,
  type LicenseInfo,
  type MeResponse,
} from '../api'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { formatJalali } from '../lib/jalali'
import { LICENSE_MODE_LABEL, licenseTone } from '../lib/license'

const fa = (n: number) => n.toLocaleString('fa-IR')

/**
 * «مجوز نرم‌افزار» — فقط در کوبیتا سازمانی.
 *
 * فعال‌سازیِ آفلاین‌محور: مالک «کدِ درخواست» را می‌گیرد و برای پشتیبانی می‌فرستد، کدِ
 * مجوز را پس می‌گیرد و اینجا می‌چسباند. سرورِ خیلی از شرکت‌ها اینترنت ندارد، پس این راه
 * باید بدونِ اینترنت هم کامل باشد. وضعیت برای همه‌ی اعضا دیده می‌شود — کسی که ثبتش
 * بسته شده باید بتواند بفهمد چرا.
 */
export function LicensePage({
  token,
  me,
  onMeUpdated,
}: {
  token: string
  me: MeResponse
  onMeUpdated: (me: MeResponse) => void
}) {
  const isOwner = me.role_key === 'owner'
  const [lic, setLic] = useState<LicenseInfo | null>(null)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [requestCode, setRequestCode] = useState('')
  const [copied, setCopied] = useState(false)
  const [licenseText, setLicenseText] = useState('')
  const [activationCode, setActivationCode] = useState('')
  const [busy, setBusy] = useState<'code' | 'install' | 'online' | null>(null)
  const [msg, setMsg] = useState<{ text: string; kind: 'ok' | 'err' } | null>(null)

  const refresh = useCallback(async () => {
    try {
      setLic(await fetchLicense(token))
      setLoadError(null)
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : 'وضعیتِ مجوز خوانده نشد.')
    }
  }, [token])

  useEffect(() => {
    void refresh()
  }, [refresh])

  async function getCode() {
    setBusy('code')
    setMsg(null)
    try {
      setRequestCode((await fetchLicenseRequestCode(token)).code)
      setCopied(false)
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : 'کدِ درخواست ساخته نشد.', kind: 'err' })
    } finally {
      setBusy(null)
    }
  }

  async function copyCode() {
    try {
      await navigator.clipboard.writeText(requestCode)
      setCopied(true)
    } catch {
      // کلیپ‌بورد در دسترس نبود؛ متن در کادر هست و دستی هم کپی می‌شود.
    }
  }

  async function activateOnline() {
    setBusy('online')
    setMsg(null)
    try {
      await applyInstalled(await activateLicenseOnline(token, activationCode.trim()))
      setActivationCode('')
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : 'فعال‌سازی ناموفق بود.', kind: 'err' })
    } finally {
      setBusy(null)
    }
  }

  async function applyInstalled(next: LicenseInfo) {
    setLic(next)
    setMsg({ text: 'مجوز نصب شد و کوبیتا سازمانی فعال است.', kind: 'ok' })
    // نوارِ بالا، منوی ماژول‌ها و قفلِ قابلیت‌ها از `me` می‌خوانند.
    onMeUpdated(await fetchMe(token))
  }

  async function install() {
    setBusy('install')
    setMsg(null)
    try {
      await applyInstalled(await installLicense(token, licenseText.trim()))
      setLicenseText('')
    } catch (e) {
      setMsg({ text: e instanceof Error ? e.message : 'نصبِ مجوز ناموفق بود.', kind: 'err' })
    } finally {
      setBusy(null)
    }
  }

  const tone = lic ? licenseTone(lic) : 'ok'

  return (
    <div className="page panels">
      <PageHeader
        icon={BadgeCheck}
        title="مجوز نرم‌افزار"
        description="وضعیتِ فعال‌سازیِ کوبیتا سازمانی روی این سرور، و نصبِ کدِ مجوز."
      />

      {msg && (
        <section className={`fy-note ${msg.kind === 'ok' ? 'fy-note--ok' : 'fy-note--err'}`}>
          {msg.kind === 'ok' ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
          <div>{msg.text}</div>
        </section>
      )}

      {lic?.message && (
        <section className={`fy-note ${tone === 'err' ? 'fy-note--err' : 'fy-note--warn'}`}>
          <AlertTriangle size={16} />
          <div>{lic.message}</div>
        </section>
      )}

      <div className="workspace-split">
        <SectionCard icon={ShieldCheck} title="وضعیت" description="آنچه همین حالا روی این سرور معتبر است.">
          {loadError ? (
            <p className="error">{loadError}</p>
          ) : !lic ? (
            <p className="muted">در حال بارگذاری…</p>
          ) : (
            <dl className="lic-facts">
              <dt>وضعیت</dt>
              <dd>
                <span className={`lic-pill lic-pill--${tone}`}>{LICENSE_MODE_LABEL[lic.mode]}</span>
              </dd>
              {lic.org && (
                <>
                  <dt>سازمان</dt>
                  <dd>{lic.org}</dd>
                </>
              )}
              <dt>کاربران</dt>
              <dd>
                {lic.seats_used != null ? fa(lic.seats_used) : '—'} از{' '}
                {lic.seats != null ? fa(lic.seats) : 'بی‌سقف'}
              </dd>
              <dt>{lic.mode === 'trial' || lic.mode === 'trial_expired' ? 'پایانِ آزمایشی' : 'انقضا'}</dt>
              <dd>{lic.expires_at ? formatJalali(lic.expires_at) : 'دائمی'}</dd>
              {lic.days_left != null && lic.writable && (
                <>
                  <dt>روزهای مانده</dt>
                  <dd>{fa(lic.days_left)}</dd>
                </>
              )}
              {lic.license_id && (
                <>
                  <dt>شناسه‌ی مجوز</dt>
                  <dd dir="ltr" className="lic-mono">
                    {lic.license_id}
                  </dd>
                </>
              )}
            </dl>
          )}
          <p className="muted lic-footnote">
            نبودِ مجوز فقط ثبتِ سندِ تازه را می‌بندد؛ دفترها، گزارش‌ها و پشتیبان‌گیری همیشه در دسترس‌اند.
          </p>
        </SectionCard>

        <SectionCard
          icon={KeyRound}
          title="فعال‌سازی"
          description="با کدِ فعال‌سازی و اینترنت در یک قدم؛ یا بدونِ اینترنت با کدِ درخواست."
        >
          {!isOwner ? (
            <p className="muted">فعال‌سازی و تمدید فقط با حسابِ مالکِ کسب‌وکار انجام می‌شود.</p>
          ) : (
            <div className="lic-steps">
              <div className="lic-step">
                <span className="lic-step-title">
                  <Globe size={15} /> فعال‌سازیِ آنلاین
                </span>
                <input
                  type="text"
                  dir="ltr"
                  className="lic-activation"
                  value={activationCode}
                  onChange={(e) => setActivationCode(e.target.value)}
                  spellCheck={false}
                  aria-label="کدِ فعال‌سازی"
                />
                <span className="field-hint">
                  کدِ ۱۶ نویسه‌ای که هنگامِ خرید گرفته‌اید. سرور فقط همین یک‌بار به اینترنت نیاز دارد.
                </span>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={activateOnline}
                  disabled={busy !== null || activationCode.replace(/[^0-9a-z]/gi, '').length < 8}
                >
                  {busy === 'online' ? 'در حال فعال‌سازی…' : 'فعال‌سازی'}
                </button>
              </div>

              <p className="lic-or">سرور اینترنت ندارد؟ از این دو قدم استفاده کنید:</p>

              <div className="lic-step">
                <span className="lic-step-title">۱. کدِ درخواستِ این سرور</span>
                {requestCode ? (
                  <>
                    <textarea className="lic-code" dir="ltr" readOnly rows={4} value={requestCode} />
                    <button type="button" className="btn-secondary" onClick={copyCode}>
                      <ClipboardCopy size={15} /> {copied ? 'کپی شد' : 'کپیِ کد'}
                    </button>
                  </>
                ) : (
                  <button type="button" className="btn-secondary" onClick={getCode} disabled={busy !== null}>
                    {busy === 'code' ? 'در حال ساخت…' : 'ساختِ کدِ درخواست'}
                  </button>
                )}
                <span className="field-hint">
                  این کد به همین رایانه گره می‌خورد؛ آن را روی خودِ سرور بسازید، نه روی رایانه‌ی دیگری.
                </span>
              </div>

              <div className="lic-step">
                <span className="lic-step-title">۲. کدِ مجوز</span>
                <textarea
                  className="lic-code"
                  dir="ltr"
                  rows={5}
                  value={licenseText}
                  onChange={(e) => setLicenseText(e.target.value)}
                  spellCheck={false}
                  aria-label="کدِ مجوز"
                />
                <span className="field-hint">کدی که با CUB1 شروع می‌شود؛ کاملش را بچسبانید.</span>
                <button
                  type="button"
                  className="btn-primary"
                  onClick={install}
                  disabled={busy !== null || licenseText.trim().length < 10}
                >
                  {busy === 'install' ? 'در حال نصب…' : 'نصبِ مجوز'}
                </button>
              </div>
            </div>
          )}
        </SectionCard>
      </div>
    </div>
  )
}
