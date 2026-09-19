import { useEffect, useState } from 'react'
import { CreditCard, X, Loader2, CheckCircle2, AlertTriangle, Monitor } from 'lucide-react'
import {
  fetchPosTerminals,
  recordCardPayment,
  newIdempotencyKey,
  type PosTerminalRecord,
  type TreasuryTransactionRecord,
} from '../api'
import { todayIso } from '../lib/jalali'
import { SearchSelect } from '../components/SearchSelect'

const fa = (n: number) => Math.round(n).toLocaleString('fa-IR')

type Stage = 'loading' | 'web' | 'no-terminals' | 'select' | 'paying' | 'recording' | 'done' | 'error'

/** دکمه‌ی «پرداخت با کارتخوان» — با کلیک، مودالِ پرداخت را باز می‌کند. */
export function CardPaymentButton({
  token,
  amount,
  contactId = null,
  description = '',
  onPaid,
  className,
  disabled,
}: {
  token: string
  amount: number
  contactId?: string | null
  description?: string
  onPaid?: (txn: TreasuryTransactionRecord) => void
  className?: string
  disabled?: boolean
}) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        type="button"
        className={className ?? 'btn-ghost'}
        onClick={() => setOpen(true)}
        disabled={disabled || amount <= 0}
        title="ارسالِ مبلغ به دستگاهِ کارتخوان"
      >
        <CreditCard size={16} /> پرداخت با کارتخوان
      </button>
      {open && (
        <CardPaymentDialog
          token={token}
          amount={amount}
          contactId={contactId}
          description={description}
          onClose={() => setOpen(false)}
          onPaid={(txn) => onPaid?.(txn)}
        />
      )}
    </>
  )
}

function CardPaymentDialog({
  token,
  amount,
  contactId,
  description,
  onClose,
  onPaid,
}: {
  token: string
  amount: number
  contactId: string | null
  description: string
  onClose: () => void
  onPaid: (txn: TreasuryTransactionRecord) => void
}) {
  // اتصال به سخت‌افزار فقط در الکترون؛ در وب window.cubita.posTerminal وجود ندارد.
  const desktop = typeof window !== 'undefined' && !!window.cubita?.posTerminal
  const [stage, setStage] = useState<Stage>(desktop ? 'loading' : 'web')
  const [terminals, setTerminals] = useState<PosTerminalRecord[]>([])
  const [terminalId, setTerminalId] = useState('')
  const [msg, setMsg] = useState('')
  const [result, setResult] = useState<{ rrn?: string; cardMask?: string } | null>(null)

  useEffect(() => {
    if (!desktop) return
    fetchPosTerminals(token)
      .then((all) => {
        const active = all.filter((t) => t.is_active)
        setTerminals(active)
        if (active.length === 0) {
          setStage('no-terminals')
          return
        }
        const def = active.find((t) => t.is_default) ?? active[0]
        setTerminalId(def.id)
        setStage('select')
      })
      .catch((e) => {
        setMsg(e instanceof Error ? e.message : 'خطا در بارگیریِ کارتخوان‌ها')
        setStage('error')
      })
  }, [token, desktop])

  const selected = terminals.find((t) => t.id === terminalId)

  async function pay() {
    if (!selected || !window.cubita?.posTerminal) return
    if (!selected.bank_account_id) {
      setMsg('برای این کارتخوان حسابِ بانکیِ تسویه تعیین نشده است — در «تنظیمات ← کارتخوان‌ها» آن را مشخص کنید.')
      setStage('error')
      return
    }
    setStage('paying')
    setMsg('')
    const profile = {
      transport: selected.transport,
      host: selected.host || undefined,
      port: selected.port || undefined,
      comPort: selected.com_port || undefined,
      psp: selected.psp || undefined,
    }
    let pr
    try {
      pr = await window.cubita.posTerminal.pay(profile, Math.round(amount), newIdempotencyKey())
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'خطا در ارتباط با کارتخوان')
      setStage('error')
      return
    }
    if (!pr.approved) {
      setMsg(pr.message || 'تراکنش تأیید نشد')
      setStage('error')
      return
    }
    // شماره‌ی مرجع کلیدِ idempotency و تنها راهِ تطبیق با صورت‌حسابِ بانک است.
    // پیش از این رشته‌ی خالی فرستاده می‌شد و سرور ۴۲۲ می‌داد — **بعد از اینکه
    // کارتِ مشتری کشیده شده بود**، با پیامی که نمی‌گفت چه باید کرد.
    if (!pr.rrn) {
      setMsg(
        'تراکنش تأیید شد ولی دستگاه شماره‌ی مرجع (RRN) نداد. ' +
          'پول از حسابِ مشتری کم شده — رسید را دستی از «رسید دریافت» ثبت کنید.',
      )
      setStage('error')
      return
    }
    setStage('recording')
    try {
      const txn = await recordCardPayment(token, {
        transaction_date: todayIso(),
        amount: Math.round(amount),
        //: حساب دیگر فرستاده نمی‌شود — سرور از خودِ دستگاه درش می‌آورد (§۴).
        pos_terminal_id: selected.id,
        contact_id: contactId ?? null,
        reference_no: pr.rrn,
        trace_no: pr.traceNo,
        card_mask: pr.cardMask,
        terminal_no: pr.terminalNo,
        psp: pr.psp,
        description,
      })
      setResult({ rrn: pr.rrn, cardMask: pr.cardMask })
      setStage('done')
      onPaid(txn)
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'خطا در ثبتِ حسابداریِ پرداخت')
      setStage('error')
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <span>
            <CreditCard size={16} /> پرداخت با کارتخوان
          </span>
          <button type="button" onClick={onClose} aria-label="بستن">
            <X size={16} />
          </button>
        </div>
        <div className="modal-body card-pay-body">
          <div className="card-pay-amount">
            مبلغِ قابل پرداخت: <strong>{fa(amount)}</strong> ریال
          </div>

          {stage === 'web' && (
            <div className="card-pay-note">
              <Monitor size={16} /> اتصال به دستگاهِ کارتخوان فقط در «نسخه‌ی دسکتاپِ» کوبیتا فعال است. در مرورگر
              می‌توانید پرداخت را دستی در بخشِ «دریافت وجه» ثبت کنید.
            </div>
          )}
          {stage === 'loading' && (
            <div className="card-pay-note">
              <Loader2 className="spin" size={16} /> در حال بارگیری…
            </div>
          )}
          {stage === 'no-terminals' && (
            <div className="card-pay-note">
              <AlertTriangle size={16} /> هیچ کارتخوانِ فعالی تنظیم نشده است. ابتدا در «تنظیمات ← کارتخوان‌ها» یک
              دستگاه اضافه کنید.
            </div>
          )}
          {stage === 'select' && (
            <>
              {terminals.length > 1 && (
                <label>
                  دستگاه
                  <SearchSelect value={terminalId} onChange={(e) => setTerminalId(e.target.value)}>
                    {terminals.map((t) => (
                      <option key={t.id} value={t.id}>
                        {t.label || 'کارتخوان'}
                      </option>
                    ))}
                  </SearchSelect>
                </label>
              )}
              <div className="card-pay-hint">با فشردنِ دکمه، مبلغ به دستگاه ارسال می‌شود؛ سپس مشتری کارت می‌کشد.</div>
            </>
          )}
          {stage === 'paying' && (
            <div className="card-pay-note big">
              <Loader2 className="spin" size={22} /> مبلغ روی دستگاه است — لطفاً کارت را بکشید…
            </div>
          )}
          {stage === 'recording' && (
            <div className="card-pay-note">
              <Loader2 className="spin" size={16} /> در حال ثبتِ پرداخت در حسابداری…
            </div>
          )}
          {stage === 'done' && (
            <div className="card-pay-ok">
              <CheckCircle2 size={22} /> پرداخت با موفقیت ثبت شد
              {result?.rrn && (
                <div className="card-pay-meta">
                  شماره‌ی مرجع: {result.rrn}
                  {result.cardMask ? ` — ${result.cardMask}` : ''}
                </div>
              )}
            </div>
          )}
          {stage === 'error' && (
            <div className="card-pay-err">
              <AlertTriangle size={16} /> {msg}
            </div>
          )}
        </div>
        <div className="modal-foot">
          {stage === 'select' && (
            <button type="button" className="btn-primary" onClick={() => void pay()}>
              <CreditCard size={16} /> ارسال به کارتخوان
            </button>
          )}
          {stage === 'error' && desktop && terminals.length > 0 && (
            <button type="button" className="btn-ghost" onClick={() => setStage('select')}>
              تلاش دوباره
            </button>
          )}
          {(stage === 'done' || stage === 'web' || stage === 'no-terminals') && (
            <button type="button" className="btn-primary" onClick={onClose}>
              بستن
            </button>
          )}
          {(stage === 'select' || stage === 'error') && (
            <button type="button" className="btn-ghost" onClick={onClose}>
              انصراف
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
