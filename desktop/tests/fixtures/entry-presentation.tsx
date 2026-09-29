// فقط QA با API نمونهٔ رهگیری‌شده؛ این fixture وارد محصول نمی‌شود.
import { createRoot } from 'react-dom/client'
import { EntryListPage } from '../../src/pages/accounting/EntryListPage'
import { applyTheme } from '../../src/lib/theme'
import '../../src/index.css'
import '../../src/App.css'
applyTheme(new URLSearchParams(location.search).get('theme') ?? 'tipalti')
createRoot(document.getElementById('root')!).render(
  <div className="page" style={{ padding: 24 }}><EntryListPage token="QA-mock-only" /></div>,
)
