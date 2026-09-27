import { BookOpen, Inbox } from 'lucide-react'
import type { AccountCache, OutboxEntry } from '../../electron.d'
import { JournalEntryForm } from '../../components/JournalEntryForm'
import { OutboxList } from '../../components/OutboxList'
import { SectionCard } from '../../components/SectionCard'
import { isElectron } from '../../platform'
import { OpsPage } from './kit'

/**
 * چهار عملیاتی که مستقیماً روی *سند* کار می‌کنند.
 *
 * تقسیم‌بندی عمدی است و از خودِ کارِ دفترداری می‌آید:
 *  - **سند حسابداری** جایی است که سند *ساخته* می‌شود.
 *  - **کارتابل اسناد موقت** جایی است که سند *بازبینی* و دائم می‌شود — تکی، دسته‌ای به منشأ، یا کلِ
 *    یک بازه برای پایانِ ماه. منوی جدای «تبدیل اسناد موقت به دائم» همین کارِ آخر را روی همین داده
 *    می‌کرد و در بازچینیِ ۱۴۰۵/۰۷/۰۳ در کارتابل ادغام شد.
 *  - **شماره‌گذاری مجدد** و **ادغام** دو ابزارِ مرتب‌کردنِ دفترِ به‌هم‌ریخته‌اند و
 *    هر دو عمداً فقط روی اسنادِ موقت کار می‌کنند.
 */

// ═══════════════════════ ۱) سند حسابداری ═══════════════════════

export function JournalEntryPage({
  token,
  accounts,
  outbox,
  onQueued,
}: {
  token: string
  accounts: AccountCache[]
  outbox: OutboxEntry[]
  onQueued: () => void
}) {
  return (
    <OpsPage
      canvas
      icon={BookOpen}
      title="سند حسابداری"
      description="ثبتِ سندِ دستی. سندِ تازه «موقت» ثبت می‌شود تا در کارتابل بازبینی شود؛ فاکتور و فیش و چک خودشان خودکار سند می‌خورند. دفترِ کاملِ اسناد زیرِ کارتِ «فهرست» است."
    >
      <JournalEntryForm token={token} accounts={accounts} onQueued={onQueued} />

      {isElectron && (
        <SectionCard
          icon={Inbox}
          title="صف اسناد ارسال‌نشده"
          description="سندهایی که آفلاین ثبت شده‌اند و هنوز به سرور مرکزی نرسیده‌اند."
        >
          <OutboxList entries={outbox} emptyHint="سندی در صف نیست." />
        </SectionCard>
      )}
    </OpsPage>
  )
}

// ═══════════════════ ۲) کارتابل اسناد موقت ═══════════════════
//: برگه‌ی اکسلیِ کارتابل فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { EntryCartablePage } from './EntryCartablePage'

// ═══════════════ ۳) شماره‌گذاری مجدد اسناد ═══════════════
//: برگه‌ی اکسلیِ نقشه‌ی شماره‌ها فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { RenumberEntriesPage } from './RenumberEntriesPage'

// ═══════════════════════ ۴) ادغام اسناد ═══════════════════════
//: برگه‌ی اکسلیِ ادغام فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { MergeEntriesPage } from './MergeEntriesPage'

// ═══════════════════════ فهرستِ «اسناد حسابداری» ═══════════════════════
//: برگه‌ی اکسلیِ دفترِ اسناد فایلِ خودش را دارد؛ از این‌جا صادر می‌شود تا مسیرِ ورودِ صفحه عوض نشود.
export { EntryListPage } from './EntryListPage'
