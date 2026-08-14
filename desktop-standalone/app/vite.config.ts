import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import electronSimple, { type ElectronSimpleOptions } from 'vite-plugin-electron/simple'

// در این نسخه از پکیج، تایپ default-import به‌جای تابع، کل namespace را نشان می‌دهد؛
// خودِ تابع در زمان اجرا همیشه در دسترس است، فقط با یک cast صریح تایپش درست می‌شود.
const electron = electronSimple as unknown as (options: ElectronSimpleOptions) => Promise<Plugin[]>

// عمداً package.json فاقد "type": "module" است تا vite-plugin-electron خروجی main/preload را CJS بسازد
// (require('electron') در CJS همیشه کار می‌کند؛ import ESM با ماژول مجازی «electron» در این نسخه‌ی الکترون قابل‌اعتماد نبود).
export default defineConfig({
  plugins: [
    react(),
    electron({
      main: {
        entry: 'electron/main.ts',
      },
      preload: {
        input: 'electron/preload.ts',
      },
    }),
  ],
})
