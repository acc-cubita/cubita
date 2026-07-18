import './App.css'
import { LightStreakBackground } from './components/LightStreakBackground'
import { Header } from './components/Header'
import { Hero } from './components/Hero'
import { StatsBar } from './components/StatsBar'
import { Features } from './components/Features'
import { HowItWorks } from './components/HowItWorks'
import { DemoSection } from './components/DemoSection'
import { PricingSection } from './components/PricingSection'
import { FAQ } from './components/FAQ'
import { FinalCta } from './components/FinalCta'
import { Footer } from './components/Footer'

function App() {
  return (
    <>
      <LightStreakBackground />
      <Header />
      <Hero />
      <StatsBar />
      <Features />
      <HowItWorks />
      <DemoSection />
      <PricingSection />
      <FAQ />
      <FinalCta />
      <Footer />
    </>
  )
}

export default App
