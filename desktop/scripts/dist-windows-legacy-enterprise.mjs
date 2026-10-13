// Isolated server/client build; preserves the main profile, appId and user data identity.
import fs from 'node:fs'
import path from 'node:path'
import {fileURLToPath} from 'node:url'
import {createHash} from 'node:crypto'
import {execFileSync} from 'node:child_process'
const desktop=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..')
const root=path.dirname(desktop)
const arch=process.env.CUBITA_LEGACY_ARCH??'x86'
if(!['x86','x64'].includes(arch))throw new Error('Choose x86 or x64')
const electronArch=arch==='x86'?'ia32':'x64'
const output=path.join(root,'_deploy',`windows-legacy-enterprise-${arch}`)
const server=process.env.CUBITA_LEGACY_SERVER_BUNDLE??path.join(root,'_deploy',`windows-legacy-frozen-${arch}`,'server-bundle')
const sha=file=>createHash('sha256').update(fs.readFileSync(file)).digest('hex')
const manifest=JSON.parse(fs.readFileSync(path.join(server,'compatibility.json'),'utf8'))
const version=process.env.CUBITA_WINDOWS_LEGACY_VERSION??'1.9.17'
if(manifest.profile!=='windows-legacy'||manifest.architecture!==arch||!manifest.python.startsWith('3.8.')||manifest.postgresMajor!==17||manifest.version!==version||sha(path.join(server,'cubita-server.exe'))!==manifest.serverSha256)throw new Error('A reviewed matching full server bundle is required')
fs.mkdirSync(output,{recursive:true})
for(const entry of fs.readdirSync(desktop)){
 if(/^(node_modules|release.*|dist.*|\.vite|package-lock\.json|.*\.tsbuildinfo)$/.test(entry))continue
 fs.cpSync(path.join(desktop,entry),path.join(output,entry),{recursive:true})
}
const pkg=JSON.parse(fs.readFileSync(path.join(desktop,'package.json'),'utf8'))
pkg.name=`cubita-windows-legacy-${arch}-enterprise`;pkg.version=version
pkg.devDependencies.electron='22.3.27';pkg.dependencies['better-sqlite3']='9.4.3';pkg.dependencies.serialport='10.5.0';pkg.dependencies.undici='5.28.5'
fs.writeFileSync(path.join(output,'package.json'),JSON.stringify(pkg,null,2)+'\n')
fs.copyFileSync(path.join(desktop,'package-lock.json'),path.join(output,'package-lock.json'))
const run=(exe,args,extra={})=>execFileSync(exe,args,{cwd:output,stdio:'inherit',windowsHide:true,env:{...process.env,CUBITA_EDITION:'enterprise',CUBITA_WINDOWS81_COMPAT:'1',CUBITA_ELECTRON_ARCH:electronArch,...extra},shell:exe==='npm.cmd'})
run('npm.cmd',['install','--ignore-scripts','--no-audit','--no-fund','--prefer-offline','--fetch-timeout=120000','--fetch-retries=2'])
run('node',['node_modules/electron/install.js'],{npm_config_arch:electronArch})
run('npm.cmd',['run','build'])
run('npm.cmd',['run','rebuild-native'])
const release=path.join(output,'release-legacy');fs.mkdirSync(release,{recursive:true})
for(const name of ['installer-service-guard.ps1','installer-os.nsh','installer-prerequisites.ps1','installer-server-command.ps1','installer-legacy-bootstrap.ps1'])fs.copyFileSync(path.join(desktop,'build',name),path.join(release,name))
const payload=path.join(release,'prerequisites');fs.mkdirSync(payload,{recursive:true})
const old=path.join(desktop,'build','prerequisites-windows81')
const bootstrap=path.join(root,'_deploy','windows-legacy-bootstrap')
const pins={dotnet:'0a3a390c47e639d0f7fc65b21195fee6b7f65b066f80f70c60fab191d14b7e40',vc64:'6afae68a783f11292149175844aed0e2ce3f247bc0250f6cb18c931295b3f399',vc32:'38c9437e6e9ef1db2671b3f0c879febec08521bd2c23231199f626b69ae1c65e',wmf64:'c51abfc65dff5f6858c0b9f6420caa0c166df7a6d8b484f8a3c68ea99f0032b0',wmf32:'4575c47bedf732c7a215a5dd9e184ac2f06f10c0f23fcef38eec96b0ff3bd121'}
const copy=(from,name,expected)=>{if(sha(from)!==expected)throw new Error('Prerequisite SHA256 mismatch: '+name);fs.copyFileSync(from,path.join(payload,name))}
const vc=arch==='x86'?path.join(bootstrap,'vc_redist.x86.exe'):path.join(old,'vc_redist.x64.exe')
copy(vc,`vc_redist.${arch}.exe`,arch==='x86'?pins.vc32:pins.vc64)
copy(path.join(old,'dotnet48.exe'),'dotnet48.exe',pins.dotnet)
copy(path.join(bootstrap,'x64','Win7AndW2K8R2-KB3191566-x64.msu'),'wmf-x64.msu',pins.wmf64)
copy(path.join(bootstrap,'x86','Win7-KB3191566-x86.msu'),'wmf-x86.msu',pins.wmf32)
fs.writeFileSync(path.join(payload,'runtime.json'),JSON.stringify({version:'14.29.30157.0',architecture:arch,sha256:arch==='x86'?pins.vc32:pins.vc64}))
fs.writeFileSync(path.join(payload,'dotnet.json'),JSON.stringify({version:'4.8',sha256:pins.dotnet}))
const defines=['CUBITA_HAS_SERVER','CUBITA_WINDOWS_LEGACY','CUBITA_WINDOWS81_COMPAT',...(arch==='x86'?['CUBITA_LEGACY_X86']:[])].map(s=>'!define '+s).join('\n')
fs.writeFileSync(path.join(release,'installer-enterprise.nsh'),'\uFEFF'+defines+'\n!define CUBITA_MIN_WINDOWS_BUILD 7601\n!define CUBITA_LEGACY_DOTNET_SHA256 "'+pins.dotnet+'"\n!define CUBITA_LEGACY_WMF64_SHA256 "'+pins.wmf64+'"\n!define CUBITA_LEGACY_WMF32_SHA256 "'+pins.wmf32+'"\n'+fs.readFileSync(path.join(desktop,'build','installer-enterprise.nsh'),'utf8').replace(/^\uFEFF/,''))
const config={...pkg.build,appId:'ir.ipnetcity.cubita.enterprise',productName:'Cubita Enterprise',directories:{output:release},publish:null,extraResources:[{from:server,to:'server'}],artifactName:`Cubita-Enterprise-Legacy-${arch}-Setup-\${version}.\${ext}`,nsis:{...pkg.build.nsis,perMachine:true,shortcutName:'کوبیتا سازمانی',include:path.join(release,'installer-enterprise.nsh')}}
fs.writeFileSync(path.join(release,'builder.json'),JSON.stringify(config,null,2))
run('node',['scripts/builder-win-retry.cjs','--config',path.join(release,'builder.json'),electronArch==='ia32'?'--ia32':'--x64','--publish','never'])
console.log('Prepared experimental '+arch+' server/client installer: '+release)
