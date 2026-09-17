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
    // در حالتِ WEB_ONLY (تستِ سریعِ مرورگری) پلاگینِ Electron لود نمی‌شود تا پردازه‌ی
    // electron باز/بسته نشود و سرورِ vite پایدار بماند. پیش‌فرض (بدونِ متغیر) بی‌تغییر.
    ...(process.env.WEB_ONLY
      ? []
      : [
          electron({
            main: {
              entry: 'electron/main.ts',
              vite: {
                build: {
                  // better-sqlite3 و serialport هر دو native addon اند؛ باندل‌کردنشان داخل main.js باعث می‌شود
                  // require دینامیک فایل .node را در زمان اجرا پیدا نکند، پس باید بیرون از باندل بمانند و از
                  // node_modules عادی require شوند. (هر دو در asarUnpack هم هستند.)
                  rollupOptions: { external: ['better-sqlite3', 'serialport'] },
                },
              },
            },
            preload: {
              input: 'electron/preload.ts',
            },
          }),
        ]),
  ],
})
