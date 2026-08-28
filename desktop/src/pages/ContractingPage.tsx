import { HardHat, FileText, Layers, Receipt, PiggyBank } from 'lucide-react'
import { PageHeader } from '../components/PageHeader'
import { SectionCard } from '../components/SectionCard'
import { EmptyState } from '../components/EmptyState'

/**
 * پیمانکاری — ماژولِ تازه، هنوز بدونِ قابلیت.
 *
 * عمداً یک جای‌نگه‌دارِ صادق است، نه صفحه‌ی خالی: ساختارِ ماژول‌ها همین حالا نهایی شده
 * تا زیرمنوها یکی‌یکی رویش سوار شوند، ولی هیچ‌کدام هنوز ساخته نشده‌اند. نمایشِ
 * سرفصل‌های پیش‌رو باعث می‌شود کاربر بداند این ماژول چه خواهد شد و منتظرِ چیزی که
 * وجود ندارد نماند.
 */
const PLANNED = [
  { icon: FileText, title: 'قراردادها', desc: 'ثبتِ قرارداد، طرفِ قرارداد، مبلغ و مدت، و ضمانت‌نامه‌ها.' },
  { icon: Layers, title: 'پروژه‌ها و فازها', desc: 'تفکیکِ پروژه به فاز و فعالیت، با بودجه و درصدِ پیشرفت.' },
  { icon: Receipt, title: 'صورت‌وضعیت', desc: 'صورت‌وضعیتِ دوره‌ای، کسورات، و تأییدِ کارفرما.' },
  { icon: PiggyBank, title: 'بهای تمام‌شده‌ی پروژه', desc: 'تجمیعِ هزینه‌ی مصالح، دستمزد و پیمانکارِ جزء روی هر پروژه.' },
]

export function ContractingPage() {
  return (
    // پوسته‌ی کارتیِ صفحه — بدونِ آن محتوا روی پس‌زمینه‌ی برنامه شناور می‌ماند.
    <div className="page panels">
      <PageHeader
        icon={HardHat}
        title="پیمانکاری"
        description="مدیریتِ قرارداد، پروژه، صورت‌وضعیت و بهای تمام‌شده‌ی پروژه‌های پیمانکاری. این ماژول در حالِ ساخت است."
      />

      <div className="workspace-split">
        {PLANNED.map((s) => (
          <SectionCard key={s.title} icon={s.icon} title={s.title} description={s.desc}>
            <EmptyState icon={s.icon} text="به‌زودی" />
          </SectionCard>
        ))}
      </div>
    </div>
  )
}
