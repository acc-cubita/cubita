"""Freeze and assemble an isolated full server. Run with the modern build-host Python.

The source tree must already be lowered; the supplied Python is a separate3.8
runtime. No migration, system service, installer publication or customer data is touched.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from native_compatibility import audit

WINSW_NET4_SHA256='923111c7142b3dc783a3c722b19b8a21bcb78222d7a136ac33f0ca8a29f4cb66'

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def build(args):
    source=args.source.resolve();output=args.output.resolve();python=args.python.resolve();pg=args.pg_dir.resolve()
    if output.exists():raise ValueError('Use a fresh output path; existing artifacts are not replaced')
    if not (source/'legacy-source.json').is_file():raise ValueError('An isolated generated source snapshot is required')
    snapshot=json.loads((source/'legacy-source.json').read_text(encoding='utf-8'))
    for entry in snapshot['files']:
        path=source/entry['path']
        if digest(path)!=entry['generatedSha256']:raise ValueError('Generated source changed: '+entry['path'])
    info=json.loads(subprocess.check_output([str(python),'-c','import sys,json,struct;print(json.dumps({"python":list(sys.version_info[:3]),"bits":struct.calcsize("P")*8}))'],text=True))
    if info['python'][:2]!=[3,8] or info['bits']!={'x86':32,'x64':64}[args.architecture]:raise ValueError('Python version/architecture does not match this legacy profile')
    pg_version=subprocess.check_output([str(pg/'bin/postgres.exe'),'--version'],text=True).strip()
    if not pg_version.startswith('postgres (PostgreSQL) 17.'):raise ValueError('PostgreSQL17 must be preserved')
    pg_audit=audit(pg,args.architecture)
    if pg_audit['issues']:raise ValueError('PostgreSQL native compatibility audit failed')
    if digest(args.winsw)!=WINSW_NET4_SHA256:raise ValueError('WinSW.NET4 does not match its verified release')
    output.mkdir(parents=True)
    env=os.environ.copy();env.update(EDITION='enterprise',ZARINPAL_SANDBOX='true',PSYCOPG_IMPL='python',DATABASE_URL='postgresql+psycopg://probe:probe@127.0.0.1:1/legacy_build_no_database',PYTHONUTF8='1')
    env['PATH']=str(pg/'bin')+';'+env['PATH']
    command=[str(python),'-m','PyInstaller','--noconfirm','--distpath',str(output/'frozen'),'--workpath',str(output/'work'),str(source/'packaging/cubita-server.spec')]
    subprocess.run(command,cwd=source,env=env,check=True)
    bundle=output/'server-bundle'
    shutil.copytree(output/'frozen/cubita-server',bundle)
    for part in ['bin','lib','share']:shutil.copytree(pg/part,bundle/'pgsql'/part)
    (bundle/'winsw').mkdir();shutil.copyfile(args.winsw,bundle/'winsw/WinSW-x64.exe')
    (bundle/'version.txt').write_text(args.version,encoding='utf-8')
    if args.notices_dir:
        shutil.copytree(args.notices_dir, bundle/'third-party-notices')
    dependencies=subprocess.check_output([str(python),'-m','pip','freeze'],text=True)
    (bundle/'runtime-dependencies.txt').write_text(dependencies,encoding='utf-8')
    probe=audit(bundle,args.architecture)
    (output/'native-audit.json').write_text(json.dumps(probe,indent=2),encoding='utf-8')
    if probe['issues']:raise ValueError('Frozen runtime native compatibility audit failed; artifact is not releasable')
    runtime_env = env.copy()
    runtime_env['PATH'] = str(Path(os.environ['SystemRoot'])/'System32') + ';' + os.environ['SystemRoot']
    runtime_env.pop('PSYCOPG_IMPL', None)
    subprocess.run([str(bundle/'cubita-server.exe'),'selftest'],cwd=output,env=runtime_env,check=True)
    manifest={'profile':'windows-legacy','architecture':args.architecture,'python':'.'.join(map(str,info['python'])),'postgresMajor':17,'postgresVersion':pg_version,'version':args.version,'serverSha256':digest(bundle/'cubita-server.exe'),'targetOsVerified':False,'minimumWindowsBuild':7601,'minimumFrameworkRelease':378389,'nativeAuditSha256':digest(output/'native-audit.json'),'sourceManifestSha256':digest(source/'legacy-source.json')}
    (bundle/'compatibility.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    print('Prepared experimental server bundle:',bundle)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--source',type=Path,required=True);parser.add_argument('--python',type=Path,required=True);parser.add_argument('--pg-dir',type=Path,required=True);parser.add_argument('--winsw',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--architecture',choices=['x86','x64'],required=True);parser.add_argument('--version',required=True)
    parser.add_argument('--notices-dir',type=Path)
    build(parser.parse_args())
