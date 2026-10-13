"""Bounded API backport for an independently verified PostgreSQL17 source tree.

No data format changes. Precise clocks remain in use where Windows supplies them.
"""
from pathlib import Path
import argparse
import hashlib
import json

HELPER = r'''/* Cubita legacy build: newer Windows keeps precise time, Windows7 gets its native clock. */
typedef VOID (WINAPI *CubitaTimeProc)(LPFILETIME);
static INIT_ONCE cubita_time_once = INIT_ONCE_STATIC_INIT;
static CubitaTimeProc cubita_time_proc = NULL;
static BOOL CALLBACK
cubita_initialize_time(PINIT_ONCE once, PVOID parameter, PVOID *context)
{
    (void) once; (void) parameter; (void) context;
    cubita_time_proc = (CubitaTimeProc) GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "GetSystemTimePreciseAsFileTime");
    if (cubita_time_proc == NULL)
        cubita_time_proc = GetSystemTimeAsFileTime;
    return TRUE;
}
'''

def patch(root):
    changes=[]
    path=root/'src/include/port/win32.h';original=path.read_bytes();text=original.decode()
    if text.count('#define _WIN32_WINNT 0x0A00') != 1:raise ValueError('Unexpected PostgreSQL Windows header; patch refused')
    text=text.replace('#define _WIN32_WINNT 0x0A00','#define _WIN32_WINNT 0x0601').replace('The minimum requirement is Windows 10.','Cubita legacy build targets Windows7 SP1; execution is verified separately.')
    changes.append((path,original,text.encode()))
    path=root/'src/port/win32gettimeofday.c';original=path.read_bytes();text=original.decode()
    if text.count('GetSystemTimePreciseAsFileTime(&file_time);') != 1:raise ValueError('Unexpected PostgreSQL clock source; patch refused')
    text=text.replace('int\ngettimeofday',HELPER+'\nint\ngettimeofday',1)
    text=text.replace('GetSystemTimePreciseAsFileTime(&file_time);','InitOnceExecuteOnce(&cubita_time_once, cubita_initialize_time, NULL, NULL);\n\tcubita_time_proc(&file_time);',1)
    changes.append((path,original,text.encode()))
    result=[]
    for path,original,data in changes:
        path.write_bytes(data);result.append({'path':str(path.relative_to(root)),'sourceSha256':hashlib.sha256(original).hexdigest(),'patchedSha256':hashlib.sha256(data).hexdigest()})
    (root/'cubita-legacy-patch.json').write_text(json.dumps({'targetOsVerified':False,'changes':result},indent=2))
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('source',type=Path);args=parser.parse_args();print(json.dumps(patch(args.source.resolve()),indent=2))
