import { ShoppingCart, FileText, PackagePlus, HandCoins, BookOpen, Package, type LucideIcon } from 'lucide-react'
import type { PageKey } from '../components/Sidebar'

/** یک «لانچرِ کار» برای مرکزِ اقدامِ داشبوردِ نسخه‌ی جدید. کلیک → onNavigate(page, section)؛
 *  کاری که به ویزارد تبدیل شده (مثلِ فاکتور فروش) مرحله‌ای باز می‌شود، بقیه فعلاً صفحه‌ی
 *  کلاسیک. افزودنِ کارِ تازه = یک ردیف اینجا. */
export interface TaskLauncher {
  key: string
  title: string
  desc: string
  icon: LucideIcon
  page: PageKey
  section?: string
}

export const TASK_LAUNCHERS: TaskLauncher[] = [
  { key: 'sales-invoice', title: 'فاکتور فروش', desc: 'ثبت فروش؛ سند حسابداری و خروج انبار جدا صادر می‌شوند.', icon: ShoppingCart, page: 'salesinvoice' },
  { key: 'quotation', title: 'پیش‌فاکتور', desc: 'صدورِ پیش‌فاکتور برای مشتری.', icon: FileText, page: 'quotations' },
  { key: 'purchase-invoice', title: 'فاکتور خرید', desc: 'ثبتِ خرید از تأمین‌کننده.', icon: PackagePlus, page: 'purchases', section: 'invoices' },
  //: `contacts/treasury` بود؛ چنین تبی وجود ندارد (نه در `MODULE_SECTIONS` و نه در
  //: خودِ صفحه‌ی طرف‌حساب) پس کارت و فرمانِ کامندپالت هر دو به تبِ اولِ «اشخاص»
  //: می‌افتادند. «رسید دریافت» همان کاری است که این لانچر نامش را می‌برد.
  { key: 'treasury', title: 'دریافت و پرداخت', desc: 'ثبتِ دریافت/پرداختِ نقد و بانک.', icon: HandCoins, page: 'receiptvoucher' },
  { key: 'journal', title: 'ثبت سند', desc: 'سندِ دستیِ حسابداری.', icon: BookOpen, page: 'journalentry' },
  { key: 'product', title: 'کالای جدید', desc: 'افزودنِ کالا یا خدمت به انبار.', icon: Package, page: 'inventory', section: 'products' },
]
