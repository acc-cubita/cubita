// Build an isolated legacy server/client edition. Never replace the normal Electron/native modules.
import fs from 'node:fs'
import {createHash} from 'node:crypto'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {execFileSync} from 'node:child_process'

const desktop=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const output=path.resolve(desktop,'..','_deploy','windows81-enterprise')
const serverBundle=path.resolve(desktop,'..','backend','dist','server-bundle-windows81')
const manifest=JSON.parse(fs.readFileSync(path.join(serverBundle,'compatibility.json'),'utf8'))
if(manifest.profile!=='windows81' || !manifest.python.startsWith('3.12.') || manifest.postgresMajor!==17) throw new Error('A Windows 8.1 server bundle built with Python 3.12 and PostgreSQL 17 is required; refusing a client-only installer or incompatible data engine.')
const runtimeDirectory=path.join(desktop,'build','prerequisites-windows81')
const runtime=JSON.parse(fs.readFileSync(path.join(runtimeDirectory,'runtime.json'),'utf8').replace(/^\uFEFF/,''))
if(!runtime.version.startsWith('14.29.') || createHash('sha256').update(fs.readFileSync(path.join(runtimeDirectory,'vc_redist.x64.exe'))).digest('hex').toUpperCase()!==runtime.sha256.toUpperCase()) throw new Error('Verified VC 2019 runtime is required.')
fs.mkdirSync(output,{recursive:true})
for(const entry of fs.readdirSync(desktop)) {
  if (/^(node_modules|release.*|dist.*|\.vite|package-lock\.json|.*\.tsbuildinfo)$/.test(entry)) continue
  fs.cpSync(path.join(desktop,entry),path.join(output,entry),{recursive:true})
}
const pkg=JSON.parse(fs.readFileSync(path.join(desktop,'package.json'),'utf8'))
pkg.version=process.env.CUBITA_WINDOWS81_VERSION??'1.9.16'
pkg.name='cubita-windows81-enterprise'
pkg.devDependencies.electron='22.3.27'
pkg.dependencies['better-sqlite3']='9.4.3'
pkg.dependencies.serialport='10.5.0'
pkg.dependencies.undici='5.28.5'
fs.writeFileSync(path.join(output,'package.json'),JSON.stringify(pkg,null,2)+'\n')
fs.copyFileSync(path.join(desktop,'package-lock.json'),path.join(output,'package-lock.json'))
const run=(exe,args)=>execFileSync(exe,args,{cwd:output,stdio:'inherit',windowsHide:true,env:{...process.env,CUBITA_EDITION:'enterprise',CUBITA_WINDOWS81_COMPAT:'1'},shell:exe==='npm.cmd'})
run('npm.cmd',['install','--ignore-scripts','--no-audit','--no-fund','--prefer-offline','--fetch-timeout=120000','--fetch-retries=2'])
run('node',['node_modules/electron/install.js'])
run('npm.cmd',['run','build'])
run('npm.cmd',['run','rebuild-native'])
if(manifest.version!==pkg.version || createHash('sha256').update(fs.readFileSync(path.join(serverBundle,'cubita-server.exe'))).digest('hex')!==manifest.serverSha256) throw new Error('Server version/hash does not match the reviewed bundle.')
const release=path.join(output,'release-windows81')
fs.mkdirSync(release,{recursive:true})
for(const name of ['installer-service-guard.ps1','installer-os.nsh','installer-prerequisites.ps1','installer-server-command.ps1']) fs.copyFileSync(path.join(desktop,'build',name),path.join(release,name))
fs.cpSync(path.join(desktop,'build','prerequisites-windows81'),path.join(release,'prerequisites'),{recursive:true})
fs.writeFileSync(path.join(release,'installer-enterprise.nsh'),'\uFEFF!define CUBITA_HAS_SERVER\n!define CUBITA_WINDOWS81_COMPAT\n!define CUBITA_MIN_WINDOWS_BUILD 9600\n'+fs.readFileSync(path.join(desktop,'build','installer-enterprise.nsh'),'utf8').replace(/^\uFEFF/,''))
const config={...pkg.build,appId:'ir.ipnetcity.cubita.enterprise',productName:'Cubita Enterprise',directories:{output:release},publish:null,extraResources:[{from:serverBundle,to:'server'}],artifactName:'Cubita-Enterprise-Windows81-Setup-${version}.${ext}',nsis:{...pkg.build.nsis,perMachine:true,shortcutName:'کوبیتا سازمانی',include:path.join(release,'installer-enterprise.nsh')}}
fs.writeFileSync(path.join(release,'builder.json'),JSON.stringify(config,null,2))
run('node',['scripts/builder-win-retry.cjs','--config',path.join(release,'builder.json'),'--publish','never'])
console.log('Windows 8.1 server/client installer prepared at '+release)
