import { StrictMode } from 'react'
import { createRoot, hydrateRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import { AppRoutes } from './routes'

const root = document.getElementById('root')!
const app = (
  <StrictMode>
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  </StrictMode>
)

//: در تولید هر صفحه پیش‌رندر شده (`scripts/prerender.mjs`) و فقط هیدریت می‌شود؛ در `vite dev`
//: ریشه خالی است و همان رندرِ معمولیِ مرورگر.
//: `firstElementChild` نه `hasChildNodes`: قالبِ توسعه یک کامنتِ `<!--app-html-->` در ریشه دارد.
if (root.firstElementChild) hydrateRoot(root, app)
else createRoot(root).render(app)
