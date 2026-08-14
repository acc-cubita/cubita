import { Save, PlugZap } from 'lucide-react'
import { useMoadianPanel, type MoadianPanelState } from '../../lib/moadianPanel'
import {
  MoadianStats,
  MoadianCredentialFields,
  MoadianToggles,
  MoadianHints,
  MoadianSend,
  MoadianHistory,
} from '../MoadianPanel'
import { TaskFlow, type WizardStep } from './TaskFlow'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

/**
 * ویزاردِ «سامانه مؤدیان» برای نسخه‌ی جدید. برخلافِ فاکتور، مراحل مستقل‌اند (تنظیمات/تست/
 * ارسال)، پس allowJump روشن است تا کاربرِ قبلاً تنظیم‌کرده مستقیم به «ارسال» برود. KPIها
 * بالای ویزارد و تاریخچه‌ی ارسال‌ها زیرِ آن، همان‌طور که در پنلِ کلاسیک.
 */
export function MoadianWizard({ token }: { token: string }) {
  const m = useMoadianPanel({ token })

  const steps: WizardStep[] = [
    {
      key: 'credentials',
      title: 'اعتبارنامه',
      subtitle: 'اطلاعاتِ کارپوشه و کلید/گواهیِ امضا را وارد و ذخیره کنید.',
      body: (
        <div className="invoice-form form-full">
          <MoadianCredentialFields m={m} />
          <div className="invoice-form-footer">
            <button type="button" className="btn-primary" onClick={() => void m.save()} disabled={m.saving}>
              <Save size={14} /> ذخیره تنظیمات
            </button>
          </div>
          {m.msg && <div className="hint">{m.msg}</div>}
        </div>
      ),
    },
    {
      key: 'environment',
      title: 'محیط و تستِ اتصال',
      subtitle: 'محیط (سندباکس/واقعی) را انتخاب، اتصال را تست و ارسال را فعال کنید.',
      body: (
        <div className="invoice-form form-full">
          <MoadianToggles m={m} />
          <div className="invoice-form-footer">
            <button type="button" className="btn-primary" onClick={() => void m.save()} disabled={m.saving}>
              <Save size={14} /> ذخیره تنظیمات
            </button>
            <button type="button" className="btn-ghost" onClick={() => void m.testConnection()} disabled={m.testing} title="فقط احراز هویت با سامانه را می‌سنجد">
              <PlugZap size={14} /> {m.testing ? 'در حالِ آزمایش…' : 'تستِ اتصال'}
            </button>
          </div>
          <MoadianHints m={m} />
        </div>
      ),
    },
    {
      key: 'send',
      title: 'ارسال صورتحساب',
      subtitle: 'یک فاکتورِ ارسال‌نشده را انتخاب کنید؛ با دکمه‌ی «ارسال به سامانه» فرستاده می‌شود.',
      body: <MoadianSend m={m} showButton={false} />,
    },
  ]

  return (
    <>
      <MoadianStats m={m} />
      <TaskFlow
        title="سامانه مؤدیان"
        steps={steps}
        submitLabel="ارسال به سامانه"
        submitting={m.sending}
        allowJump
        preview={<LivePreview m={m} />}
        onSubmit={() => void m.submitInvoice()}
      />
      <MoadianHistory m={m} />
    </>
  )
}

function LivePreview({ m }: { m: MoadianPanelState }) {
  const s = m.settings
  return (
    <div className="live-preview">
      <p className="live-preview-title">وضعیتِ سامانه</p>
      <div className="live-preview-row"><span>ارسال</span><strong>{s?.is_active ? 'فعال' : 'غیرفعال'}</strong></div>
      <div className="live-preview-row"><span>محیط</span><strong>{s?.is_sandbox ? 'سندباکس' : 'واقعی'}</strong></div>
      <div className="live-preview-row"><span>کلید خصوصی</span><strong>{s?.has_private_key ? 'ثبت‌شده' : 'ندارد'}</strong></div>
      <div className="live-preview-row"><span>گواهیِ امضا</span><strong>{s?.has_certificate ? 'ثبت‌شده' : 'ندارد'}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row"><span>ارسال موفق</span><strong>{fa(m.sentCount)}</strong></div>
      <div className="live-preview-row"><span>ردشده / خطا</span><strong>{fa(m.failedCount)}</strong></div>
      <div className="live-preview-row"><span>آخرین سریال</span><strong>{fa(s?.last_serial ?? 0)}</strong></div>
    </div>
  )
}
