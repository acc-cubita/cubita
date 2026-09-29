// Production NSIS hooks, with a MOCK guard in a disposable directory.
// Never execute a real installer or touch Cubita services/registry/data here.
import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { spawnSync } from 'node:child_process'
import { fileURLToPath } from 'node:url'

assert.equal(process.platform, 'win32', 'This QA harness requires Windows/NSIS')
const scripts = path.dirname(fileURLToPath(import.meta.url))
const cache = path.join(process.env.LOCALAPPDATA, 'electron-builder', 'Cache', 'nsis-3.0.4.1')
const compiler = process.env.CUBITA_QA_MAKENSIS ?? path.join(cache, fs.readdirSync(cache).find(name => name.startsWith('nsis-')), 'makensis.exe')
const output = fs.mkdtempSync(path.join(os.tmpdir(), 'CubitaInstallerMockQa-'))
const compiled = spawnSync(compiler, [
  '/V2', `/DQA_OUTPUT=${output}`,
  `/DCUBITA_INSTALLER_GUARD=${path.join(scripts, 'fixtures', 'installer-mock-guard.ps1')}`,
  path.join(scripts, 'fixtures', 'installer-lifecycle.nsi'),
], { encoding: 'utf8', windowsHide: true })
assert.equal(compiled.status, 0, compiled.error?.message ?? `${compiled.stdout}\n${compiled.stderr}`)

const queries = ['app-running', 'api-state', 'pg-state', 'network-state']
const prepare = [...queries, 'pause-network', 'stop-api', 'stop-pg']
const restore = ['start-pg', 'start-api', 'resume-network']
const cases = [
  ['init-cancel', 2, []],
  ['prepare-success', 0, prepare],
  ['app-running', 0, ['app-running', 'close-app', ...prepare.slice(1)]],
  ['all-stopped', 0, [...queries, 'pause-network']],
  ['all-absent', 0, [...queries, 'pause-network']],
  ['api-query-failure', 2, queries],
  ['pg-query-failure', 2, queries],
  ['task-query-failure', 2, queries],
  ['client-over-services', 2, queries],
  ['client-over-stopped-services', 2, queries],
  ['pause-failure', 2, [...queries, 'pause-network', ...restore]],
  ['stop-api-failure', 2, [...queries, 'pause-network', 'stop-api', ...restore]],
  ['stop-pg-failure', 2, [...prepare, ...restore]],
  // A partially replaced installation must not restart an unverified backend.
  ['copy-failure', 2, prepare],
  ['wrong-directory', 2, ['app-running']],
]
for (const [scenario, exitCode, expected] of cases) {
  const run = spawnSync(path.join(output, 'lifecycle-fixture.exe'), ['/S', `/scenario=${scenario}`], {
    windowsHide: true, encoding: 'utf8', timeout: 60000,
  })
  assert.equal(run.status, exitCode, `${scenario}: ${run.error?.message ?? run.stderr}`)
  const log = path.join(output, scenario, 'actions.log')
  const actions = fs.existsSync(log) ? fs.readFileSync(log, 'utf8').trim().split(/\r?\n/) : []
  assert.deepEqual(actions, expected, scenario)
  console.log(`PASS: ${scenario}`)
}
// Compile and exercise the uninstaller hook: close only the GUI, do not prepare an upgrade.
const uninstaller = spawnSync(compiler, [
  '/V2', '/DBUILD_UNINSTALLER', `/DQA_OUTPUT=${output}`,
  `/DCUBITA_INSTALLER_GUARD=${path.join(scripts, 'fixtures', 'installer-mock-guard.ps1')}`,
  path.join(scripts, 'fixtures', 'installer-lifecycle.nsi'),
], { encoding: 'utf8', windowsHide: true })
assert.equal(uninstaller.status, 0, `${uninstaller.stdout}\n${uninstaller.stderr}`)
const uninstallScenario = 'uninstall-gui-only'
const unrun = spawnSync(path.join(output, 'lifecycle-fixture.exe'), ['/S', `/scenario=${uninstallScenario}`], {
  windowsHide: true, encoding: 'utf8', timeout: 60000,
})
assert.equal(unrun.status, 0, unrun.error?.message ?? unrun.stderr)
assert.equal(fs.readFileSync(path.join(output, uninstallScenario, 'actions.log'), 'utf8').trim(), 'app-running')
console.log(`PASS: 16 NSIS lifecycle scenarios (mock services only). QA artifacts: ${output}`)
