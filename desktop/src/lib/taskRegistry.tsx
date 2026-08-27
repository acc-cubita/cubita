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
  { key: 'sales-invoice', title: 'فاکتور فروش', desc: 'ثبتِ فروش — انبار و سندِ آن خودکار ثبت می‌شود.', icon: ShoppingCart, page: 'sales', section: 'invoices' },
  { key: 'quotation', title: 'پیش‌فاکتور', desc: 'صدورِ پیش‌فاکتور برای مشتری.', icon: FileText, page: 'sales', section: 'quotations' },
  { key: 'purchase-invoice', title: 'فاکتور خرید', desc: 'ثبتِ خرید از تأمین‌کننده.', icon: PackagePlus, page: 'purchases', section: 'invoices' },
  { key: 'treasury', title: 'دریافت و پرداخت', desc: 'ثبتِ دریافت/پرداختِ نقد و بانک.', icon: HandCoins, page: 'contacts', section: 'treasury' },
  { key: 'journal', title: 'ثبت سند', desc: 'سندِ دستیِ حسابداری.', icon: BookOpen, page: 'journalentry' },
  { key: 'product', title: 'کالای جدید', desc: 'افزودنِ کالا یا خدمت به انبار.', icon: Package, page: 'inventory', section: 'products' },
]
