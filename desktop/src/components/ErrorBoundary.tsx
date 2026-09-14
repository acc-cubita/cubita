import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle, RotateCcw } from 'lucide-react'

/**
 * مهارِ خطای رندر — تا یک صفحه‌ی خراب کلِ برنامه را نبرد.
 *
 * **چرا لازم شد.** React هر خطای رندرِ مهارنشده را تا ریشه بالا می‌برد و آن‌جا
 * **کلِ درخت را unmount می‌کند**. یعنی یک `ReferenceError` در یک صفحه، به کاربر
 * یک **صفحه‌ی کاملاً سفید** نشان می‌دهد: نه ناوبری، نه پیام، نه راهِ برگشت. تنها
 * راهِ خروج بستن و باز کردنِ دوباره‌ی برنامه است.
 *
 * این دقیقاً یک بار اتفاق افتاد — «حسابداری ← گزارش ترازها» — و تا وقتی کاربر
 * گزارشش نداد هیچ‌کس نفهمید، چون `tsc` و لینت سبز بودند و دسکتاپ خطاهایش را
 * جایی نمی‌فرستد.
 *
 * با این مرز، همان خطا به یک کارتِ خطا در ناحیه‌ی محتوا تبدیل می‌شود و **پوسته،
 * ناوبری و بقیه‌ی صفحه‌ها زنده می‌مانند**.
 *
 * **چرا `key={page}` سرِ محلِ استفاده مهم است:** مرزِ خطا پس از گرفتنِ خطا در
 * حالتِ خراب می‌ماند و خودش بیرون نمی‌آید. با `key`، رفتن به صفحه‌ی دیگر یک
 * نمونه‌ی تازه می‌سازد و حالت پاک می‌شود — وگرنه کاربر بعد از یک خطا در کلِ
 * برنامه گیر می‌کرد، که از خودِ باگ بدتر است.
 */
type Props = { children: ReactNode }
type State = { error: Error | null }

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error): State {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    //: کنسول تنها جایی است که امروز این خطا دیده می‌شود — دسکتاپ برخلافِ موبایل
    //: به `/api/client-errors` گزارش نمی‌دهد. تا وقتی آن وصل نشود، این خط تنها
    //: تفاوتِ بینِ «یک ردِ قابلِ پیگیری» و «هیچ» است.
    console.error('[ErrorBoundary] خطای رندر:', error, info.componentStack)
  }

  render() {
    const { error } = this.state
    if (!error) return this.props.children

    return (
      <div className="page panels">
        <section className="fy-status">
          <h2>
            <AlertTriangle size={18} /> این صفحه خطا داد
          </h2>
          <p className="muted">
            بقیه‌ی برنامه سالم است — از منو می‌توانید به صفحه‌ی دیگری بروید. اگر این
            خطا تکرار شد، متنِ زیر را برای تیمِ پشتیبانی بفرستید.
          </p>
          {/* پیامِ فنی عمداً نمایش داده می‌شود: کاربرِ این نرم‌افزار اغلب خودش
              حسابدار یا مدیرِ کسب‌وکار است و همین یک خط، تشخیص را از «سفید شد»
              به یک گزارشِ قابلِ پیگیری تبدیل می‌کند. */}
          <pre className="error-detail" dir="ltr">
            {error.message}
          </pre>
          <button type="button" className="btn-primary" onClick={() => this.setState({ error: null })}>
            <RotateCcw size={14} /> تلاش دوباره
          </button>
        </section>
      </div>
    )
  }
}
