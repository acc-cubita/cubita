/* oxlint-disable react/only-export-components -- ورودیِ build است (پیش‌رندر)، نه ماژولی که Fast Refresh بارش کند. */
import { StrictMode } from 'react'
import { renderToString } from 'react-dom/server'
import { StaticRouter } from 'react-router-dom'
import { AppRoutes } from './routes'

/**
 * ورودیِ پیش‌رندر — فقط در زمانِ build اجرا می‌شود (`vite build --ssr`، بعد `scripts/prerender.mjs`).
 * HTMLِ هر مسیر را می‌سازد تا خزنده‌ی جست‌وجو و پیش‌نمایشِ پیام‌رسان‌ها متنِ واقعی ببینند، نه یک
 * `<div id="root">`ِ خالی.
 */
export function render(url: string): string {
  return renderToString(
    <StrictMode>
      <StaticRouter location={url}>
        <AppRoutes />
      </StaticRouter>
    </StrictMode>,
  )
}

export { headTags } from './seo/meta'
export { ALL_PAGES, NOT_FOUND_META } from './seo/pages'
