import { useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { AlertTriangle, Pencil, Save, X } from 'lucide-react'
import {
  ACCOUNT_NATURE_LABELS,
  ACCOUNT_TRAIT_META,
  STATEMENT_TYPE_LABELS,
  changeAccountCode,
  updateAccount,
  type AccountTraits,
  type ChartAccount,
} from '../api'

/**
 * فرمِ ویرایشِ حساب — همان چیزی که تا امروز سه‌تا `window.prompt` بود.
 *
 * دلیلِ ساختنش: «ویژگی‌های حساب» شش تیک است و ماهیت یک فهرست؛ اینها در پرسشِ
 * تک‌خطیِ مرورگر جا نمی‌شوند و مهم‌تر اینکه دو تیک به هم وابسته‌اند («تسعیر پذیر»
 * فقط روی «ارزی»)، که در پرامپت اصلاً قابلِ نشان‌دادن نیست.
 *
 * کد جدا از بقیه ثبت می‌شود چون سرور هم آن را جدا می‌گیرد (`PATCH …/code`):
 * تغییرِ کد ساختارِ کدینگ را می‌سنجد و می‌تواند شکست بخورد، در حالی که تغییرِ نام
 * و تیک‌ها همیشه می‌گیرد. یک‌کاسه کردنشان یعنی ردشدنِ کد، تیک‌ها را هم برمی‌گرداند.
 */

const TRAIT_KEYS = ACCOUNT_TRAIT_META.map((t) => t.key)

/** پرچم‌های حساب را از رکورد بیرون می‌کشد — بدونِ تکرارِ نامِ فیلدها در دو جا. */
function traitsOf(account: ChartAccount): AccountTraits {
  const out = {} as AccountTraits
  for (const key of TRAIT_KEYS) out[key] = account[key]
  return out
}

export function AccountEditDrawer({
  token,
  account,
  levelLabel,
  parentName,
  typeLabel,
  onClose,
  onSaved,
}: {
  token: string
  account: ChartAccount
  levelLabel: string
  parentName: string
  typeLabel: string
  onClose: () => void
  onSaved: (message: string) => void
}) {
  const [code, setCode] = useState(account.code)
  const [name, setName] = useState(account.name)
  const [name2, setName2] = useState(account.name2)
  //: '' یعنی «مشتق از نوعِ حساب» — همان چیزی که بک‌اند با null می‌فهمد.
  const [nature, setNature] = useState(account.nature ?? '')
  const [isActive, setIsActive] = useState(account.is_active)
  const [traits, setTraits] = useState<AccountTraits>(() => traitsOf(account))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  function setTrait(key: keyof AccountTraits, value: boolean) {
    setTraits((t) => {
      const next = { ...t, [key]: value }
      //: خاموش‌کردنِ «ارزی» تیکِ وابسته را هم برمی‌دارد. سرور همین را گارد می‌کند؛
      //: این‌جا فقط جلوی فرستادنِ ترکیبی گرفته می‌شود که قطعاً رد خواهد شد.
      if (key === 'is_fx' && !value) next.fx_revaluable = false
      return next
    })
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const trimmedName = name.trim()
      const trimmedName2 = name2.trim()
      const patch: Parameters<typeof updateAccount>[2] = {}
      if (trimmedName !== account.name) patch.name = trimmedName
      if (trimmedName2 !== account.name2) patch.name2 = trimmedName2
      if ((nature || null) !== account.nature) patch.nature = nature || null
      if (isActive !== account.is_active) patch.is_active = isActive
      for (const key of TRAIT_KEYS) {
        if (traits[key] !== account[key]) patch[key] = traits[key]
      }

      //: کد آخر می‌رود: اگر ساختارِ کدینگ ردش کند، دستِ‌کم بقیه ذخیره شده‌اند و
      //: کاربر پیامِ دقیقِ همان کد را می‌بیند، نه یک شکستِ مبهمِ کلی.
      if (Object.keys(patch).length > 0) await updateAccount(token, account.id, patch)
      const trimmedCode = code.trim()
      if (trimmedCode && trimmedCode !== account.code) {
        await changeAccountCode(token, account.id, trimmedCode)
      }
      onSaved(`حسابِ «${trimmedName || account.name}» ذخیره شد.`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'خطای ناشناخته')
    } finally {
      setBusy(false)
    }
  }

  return createPortal(
    <div className="drawer-overlay" onClick={onClose}>
      <div className="drawer-panel" onClick={(e) => e.stopPropagation()} role="dialog" aria-modal="true">
        <div className="drawer-head">
          <div className="drawer-title">
            <Pencil size={17} />
            <div>
              <div className="drawer-title-main">ویرایشِ حساب: {account.name}</div>
              <div className="drawer-title-sub ltr-cell">{account.code}</div>
            </div>
          </div>
          <button type="button" className="drawer-close" onClick={onClose} aria-label="بستن">
            <X size={18} />
          </button>
        </div>

        <div className="drawer-body">
          {error && (
            <div className="fy-note fy-note--err">
              <AlertTriangle size={16} />
              <div>{error}</div>
            </div>
          )}

          <form className="acc-edit" onSubmit={submit}>
            <div className="acc-edit-grid">
              {/* سطح، سرشاخه و گروه فقط خواندنی‌اند: هر سه روی اسناد و گزارش‌های
                  ثبت‌شده نشسته‌اند و سرور هم تغییرشان را نمی‌پذیرد. نمایششان لازم
                  است چون فرمِ سپیدار هم آنها را نشان می‌دهد و کاربر باید بداند
                  این حساب کجای درخت است. */}
              <label>
                <span>نوع حساب</span>
                <input value={levelLabel} readOnly disabled />
              </label>
              <label>
                <span>حساب سرشاخه</span>
                <input value={parentName || '—'} readOnly disabled />
              </label>
              <label>
                <span>کد حساب</span>
                <input value={code} onChange={(e) => setCode(e.target.value)} dir="ltr" required />
              </label>
              <label>
                <span>گروه حساب</span>
                <input value={typeLabel} readOnly disabled />
              </label>
              <label>
                <span>صورت مالی</span>
                {/* مشتق از نوعِ حساب است، پس هیچ‌وقت قابلِ ویرایش نیست — نشان دادنش
                    برای این است که کاربر بداند این حساب در ترازنامه می‌نشیند یا
                    در سود و زیان، بی‌آنکه لازم باشد خودش نتیجه بگیرد. */}
                <input
                  value={STATEMENT_TYPE_LABELS[account.statement_type] ?? account.statement_type}
                  readOnly
                  disabled
                />
              </label>
              <label>
                <span>عنوان حساب</span>
                <input value={name} onChange={(e) => setName(e.target.value)} required />
              </label>
              <label>
                <span>عنوان حساب (۲)</span>
                <input value={name2} onChange={(e) => setName2(e.target.value)} dir="ltr" />
              </label>
              <label>
                <span>ماهیت</span>
                <select value={nature} onChange={(e) => setNature(e.target.value)}>
                  <option value="">
                    پیش‌فرضِ نوعِ حساب ({ACCOUNT_NATURE_LABELS[account.effective_nature]})
                  </option>
                  <option value="debit">بدهکار</option>
                  <option value="credit">بستانکار</option>
                  <option value="any">مهم نیست</option>
                </select>
              </label>
              <label>
                <span>وضعیت</span>
                <select
                  value={isActive ? '1' : '0'}
                  onChange={(e) => setIsActive(e.target.value === '1')}
                >
                  <option value="1">فعال</option>
                  <option value="0">غیرفعال</option>
                </select>
              </label>
            </div>

            <fieldset className="acc-traits">
              <legend>ویژگی‌های حساب</legend>
              {ACCOUNT_TRAIT_META.map((trait) => {
                //: «تسعیر پذیر» تا «ارزی» روشن نشود خاکستری است — دقیقاً مثلِ سپیدار،
                //: و همان قیدی که پایگاه‌داده هم می‌بندد.
                const locked = trait.key === 'fx_revaluable' && !traits.is_fx
                return (
                  <label
                    key={trait.key}
                    className={`fy-check acc-trait${locked ? ' acc-trait--off' : ''}`}
                  >
                    <input
                      type="checkbox"
                      checked={traits[trait.key]}
                      disabled={locked || busy}
                      onChange={(e) => setTrait(trait.key, e.target.checked)}
                    />
                    <span className="acc-trait-label">{trait.label}</span>
                    <span className="acc-trait-hint">
                      {locked ? 'اول «ارزی» را روشن کنید.' : trait.hint}
                    </span>
                  </label>
                )
              })}
            </fieldset>

            <div className="acc-edit-actions">
              <button type="submit" className="btn-primary" disabled={busy}>
                <Save size={14} /> ذخیره
              </button>
              <button type="button" onClick={onClose} disabled={busy}>
                انصراف
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>,
    document.body,
  )
}
