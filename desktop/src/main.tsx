import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { applyTheme, getStoredThemeId } from './lib/theme'
import { applyExperience, getStoredMode } from './lib/experienceMode'

// پیش از render تا صفحه بدونِ پرش با پوسته‌ی ذخیره‌شده بالا بیاید
applyTheme(getStoredThemeId())
//: همین دلیل برای حالتِ تجربه: تراکمِ گرید با CSS و صفتِ `data-experience` می‌آید،
//: پس اگر بعد از render اعمال شود، صفحه یک‌بار با تراکمِ اشتباه رندر می‌شود.
//: مقدارِ سرور بعد از `GET /me` می‌نشیند و اگر فرق داشت همان‌جا اصلاح می‌کند.
applyExperience(getStoredMode())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
