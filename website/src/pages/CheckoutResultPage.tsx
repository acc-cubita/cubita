import { CheckCircle2, XCircle } from 'lucide-react'
import { LightStreakBackground } from '../components/LightStreakBackground'
import { Header } from '../components/Header'
import { Footer } from '../components/Footer'

export function CheckoutResultPage() {
  const params = new URLSearchParams(window.location.search)
  const success = params.get('status') === 'success'

  return (
    <>
      <LightStreakBackground />
      <Header />
      <div className="result-page">
        <div className="result-card">
          {success ? (
            <>
              <div className="result-icon success">
                <CheckCircle2 size={32} />
              </div>
              <h2>پرداخت با موفقیت انجام شد</h2>
              <p>
                خرید شما ثبت شد. تیم کوبیتا طی چند ساعت آینده با اطلاعات ورود به نسخه‌ی اختصاصی‌تان، از طریق
                ایمیل یا تماس تلفنی با شما در ارتباط خواهد بود.
              </p>
            </>
          ) : (
            <>
              <div className="result-icon failed">
                <XCircle size={32} />
              </div>
              <h2>پرداخت ناموفق بود</h2>
              <p>تراکنش تکمیل نشد یا لغو شد. مبلغی از حساب شما کسر نشده است؛ می‌توانید دوباره تلاش کنید.</p>
            </>
          )}
          <a href="/" className="btn btn-primary">
            بازگشت به صفحه‌ی اصلی
          </a>
        </div>
      </div>
      <Footer />
    </>
  )
}
