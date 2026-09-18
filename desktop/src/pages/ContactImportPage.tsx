import { FileUp } from 'lucide-react'
import { BulkImportPanel } from '../components/BulkImportPanel'
import { PageHeader } from '../components/PageHeader'

/**
 * ورود گروهی اشخاص — صفحه‌ی مستقلِ ماژولِ «تنظیمات».
 *
 * پیش‌تر تبِ صفحه‌ی «اشخاص» بود. به خواستِ کاربر به «تنظیمات» آمد: ورودِ گروهی کارِ
 * راه‌اندازی است که یک‌بار انجام می‌شود، کنارِ کدینگ و شماره‌گذاری — نه کارِ روزانه‌ی
 * طرف‌حساب‌ها. پنل همان پنلِ قبلی است و دفترِ نتیجه‌اش «طرف حساب‌ها».
 */
export function ContactImportPage({ token }: { token: string }) {
  return (
    <div className="page panels">
      <PageHeader
        icon={FileUp}
        title="ورود گروهی اشخاص"
        description="فهرستِ مشتریان و تأمین‌کنندگان را یک‌جا از فایلِ CSV وارد کنید."
      />
      <BulkImportPanel token={token} kind="contacts" />
    </div>
  )
}
