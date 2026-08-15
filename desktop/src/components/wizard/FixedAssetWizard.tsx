import { useFixedAssetDraft, type FixedAssetDraft } from '../../lib/fixedAssetDraft'
import { FixedAssetFields, FixedAssetsList, DepreciationRun } from '../FixedAssetsPanel'
import { SectionCard } from '../SectionCard'
import { Landmark } from 'lucide-react'
import { TaskFlow, type WizardStep } from './TaskFlow'

const fa = (v: string | number) => Number(v).toLocaleString('fa-IR')

/** ویزاردِ «دارایی ثابت» — مشخصات ← بها و استهلاک + پیش‌نمایشِ زنده؛ فهرست و اجرای استهلاک زیرِ ویزارد. */
export function FixedAssetWizard({ token }: { token: string }) {
  const d = useFixedAssetDraft({ token })

  const steps: WizardStep[] = [
    {
      key: 'identity',
      title: 'مشخصاتِ دارایی',
      subtitle: 'نام، دسته و تاریخِ تحصیل را وارد کنید.',
      canAdvance: !!d.form.name,
      blockHint: 'نامِ دارایی الزامی است.',
      body: (
        <div className="invoice-form form-full">
          <FixedAssetFields d={d} splitStep="identity" />
        </div>
      ),
    },
    {
      key: 'valuation',
      title: 'بها و استهلاک',
      subtitle: 'بهای تمام‌شده، ارزشِ اسقاط، عمرِ مفید و (در صورت نیاز) حساب پرداخت را وارد کنید.',
      canAdvance: d.identityValid,
      blockHint: 'بهای تمام‌شده (بزرگ‌تر از صفر) و عمرِ مفید (ماه) الزامی است.',
      body: (
        <div className="invoice-form form-full">
          <FixedAssetFields d={d} splitStep="valuation" />
        </div>
      ),
    },
  ]

  return (
    <>
      <TaskFlow
        title={d.editingId ? 'ویرایشِ دارایی ثابت' : 'ثبتِ داراییِ ثابتِ جدید'}
        steps={steps}
        submitLabel={d.editingId ? 'ذخیره' : 'ثبت دارایی'}
        submitting={d.submitting}
        message={d.formMsg}
        resetKey={d.formVersion}
        preview={<LivePreview d={d} />}
        onSubmit={() => void d.submit()}
      />
      <SectionCard icon={Landmark} title="فهرست دارایی‌ها" description={`${fa(d.assets.length)} قلم دارایی`}>
        <FixedAssetsList d={d} />
      </SectionCard>
      <DepreciationRun d={d} />
    </>
  )
}

function LivePreview({ d }: { d: FixedAssetDraft }) {
  return (
    <div className="live-preview">
      <p className="live-preview-title">پیش‌نمایشِ دارایی</p>
      <div className="live-preview-row"><span>نام</span><strong>{d.form.name || '—'}</strong></div>
      <div className="live-preview-row"><span>دسته</span><strong>{d.form.category || '—'}</strong></div>
      <div className="live-preview-row"><span>بهای تمام‌شده</span><strong>{fa(Number(d.form.cost) || 0)}</strong></div>
      <div className="live-preview-row"><span>عمر مفید</span><strong>{d.form.useful_life_months ? `${fa(d.form.useful_life_months)} ماه` : '—'}</strong></div>
      <div className="live-preview-divider" />
      <div className="live-preview-row live-preview-total"><span>استهلاکِ ماهانه (تخمین)</span><strong>{fa(d.monthlyEstimate)}</strong></div>
    </div>
  )
}
