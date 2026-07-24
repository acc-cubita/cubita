import './App.css'
import { SoftBackground } from './components/SoftBackground'
import { Header } from './components/Header'
import { Hero } from './components/Hero'
import { StatsBar } from './components/StatsBar'
import { Features } from './components/Features'
import { HowItWorks } from './components/HowItWorks'
import { ProductGallery } from './components/ProductGallery'
import { DemoSection } from './components/DemoSection'
import { PricingSection } from './components/PricingSection'
import { FAQ } from './components/FAQ'
import { FinalCta } from './components/FinalCta'
import { Footer } from './components/Footer'

function App() {
  return (
    <>
      <SoftBackground />
      <Header />
      <Hero />
      <StatsBar />
      <Features />
      <HowItWorks />
      <ProductGallery />
      <DemoSection />
      <PricingSection />
      <FAQ />
      <FinalCta />
      <Footer />
    </>
  )
}

export default App
