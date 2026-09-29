import { build } from 'esbuild'
import { spawn } from 'node:child_process'
import path from 'node:path'
const bundle = path.resolve('node_modules/.tmp/native-journal-outbox.cjs')
await build({ entryPoints: ['tests/native-journal-outbox.ts'], outfile: bundle, bundle: true, platform: 'node', format: 'cjs', external: ['electron', 'better-sqlite3'] })
const environment = { ...process.env }; delete environment.ELECTRON_RUN_AS_NODE
const child = spawn(path.resolve('node_modules/electron/dist/electron.exe'), [bundle], { env: environment, windowsHide: true, stdio: 'inherit' })
const result = await new Promise((resolve, reject) => { child.on('error', reject); child.on('exit', resolve) })
process.exitCode = result ?? 1
