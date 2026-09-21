import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// اپِ ستاد عمداً هیچ افزونه‌ی Electron ندارد: فقط مرورگر، فقط admin.cubita.ir.
export default defineConfig({
  plugins: [react()],
  server: { port: 5175, strictPort: true },
})
