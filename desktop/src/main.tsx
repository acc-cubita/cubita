import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { applyTheme, getStoredThemeId } from './lib/theme'

// پیش از render تا صفحه بدونِ پرش با پوسته‌ی ذخیره‌شده بالا بیاید
applyTheme(getStoredThemeId())

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
