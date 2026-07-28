import './App.css'
import { SoftBackground } from './components/SoftBackground'
import { PromoBar } from './components/PromoBar'
import { Header } from './components/Header'
import { Hero } from './components/Hero'
import { StatsBar } from './components/StatsBar'
import { Platforms } from './components/Platforms'
import { Industries } from './components/Industries'
import { Solutions } from './components/Solutions'
import { Features } from './components/Features'
import { ProductGallery } from './components/ProductGallery'
import { PricingSection } from './components/PricingSection'
import { TrialCta } from './components/TrialCta'
import { WhyCubita } from './components/WhyCubita'
import { FAQ } from './components/FAQ'
import { FinalCta } from './components/FinalCta'
import { Footer } from './components/Footer'

// چینشِ صفحه به تقلیدِ ساختارِ رقیب (shatootsoft.com)، با حفظِ کاملِ پالتِ رنگیِ خودمان:
// نوارِ اعلان → هدر → هیرو → نسخه‌ها (وب/دسکتاپ) → صنف‌ها → راهکارها → امکانات →
// نمای برنامه → قیمت → «اول امتحان کنید» → چرا کوبیتا → سؤالات → دعوتِ پایانی → فوتر.
function App() {
  return (
    <>
      <SoftBackground />
      <PromoBar />
      <Header />
      <Hero />
      <StatsBar />
      <Platforms />
      <Industries />
      <Solutions />
      <Features />
      <ProductGallery />
      <PricingSection />
      <TrialCta />
      <WhyCubita />
      <FAQ />
      <FinalCta />
      <Footer />
    </>
  )
}

export default App
