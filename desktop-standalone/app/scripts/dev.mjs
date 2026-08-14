// اگر ELECTRON_RUN_AS_NODE در محیط ست شده باشد (مثلاً توسط بعضی محیط‌های dev/CI)، هر اجرای electron.exe
// را مجبور می‌کند مثل Node ساده رفتار کند؛ در آن حالت electron.app همیشه undefined است و اپ بالا نمی‌آید.
// چون vite-plugin-electron پردازه‌ی electron را با همین process.env اسپاون می‌کند، باید همین‌جا حذفش کنیم
// تا قبل از رسیدن به آن spawn از بین رفته باشد.
delete process.env.ELECTRON_RUN_AS_NODE

const { spawn } = await import('node:child_process')
const { fileURLToPath } = await import('node:url')
const path = (await import('node:path')).default

const viteBin = path.join(path.dirname(fileURLToPath(import.meta.url)), '..', 'node_modules', 'vite', 'bin', 'vite.js')

const vite = spawn(process.execPath, [viteBin], {
  stdio: 'inherit',
  env: process.env,
})

vite.on('exit', (code) => process.exit(code ?? 0))
