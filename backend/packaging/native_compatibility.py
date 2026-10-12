"""Conservative PE gate for legacy artifacts; not a substitute for target-OS execution."""
import argparse
import hashlib
import json
from pathlib import Path
import pefile

WINDOWS8_APIS={'GetSystemTimePreciseAsFileTime','WaitOnAddress','WakeByAddressAll','WakeByAddressSingle','GetOverlappedResultEx','SetThreadInformation','GetThreadInformation','GetProcessInformation','PrefetchVirtualMemory'}
WINDOWS10_APIS={'SetThreadDescription','GetThreadDescription','GetTempPath2W','DiscardVirtualMemory'}
MACHINES={'x86':0x14c,'x64':0x8664}

def audit(root,architecture,minimum_windows=7):
    result=[];issues=[]
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix.lower() not in {'.exe','.dll','.pyd'}:continue
        pe=pefile.PE(str(path),fast_load=True)
        pe.parse_data_directories(directories=[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_IMPORT']])
        imports={item.name.decode('ascii') for entry in getattr(pe,'DIRECTORY_ENTRY_IMPORT',[]) for item in entry.imports if item.name}
        clr=pe.OPTIONAL_HEADER.DATA_DIRECTORY[pefile.DIRECTORY_ENTRY['IMAGE_DIRECTORY_ENTRY_COM_DESCRIPTOR']]
        anycpu=False
        if clr.VirtualAddress:
            flags=int.from_bytes(pe.get_data(clr.VirtualAddress+16,4),'little')
            anycpu=bool(flags&1) and not bool(flags&2)
        blocked=(WINDOWS10_APIS | (WINDOWS8_APIS if minimum_windows<8 else set()))&imports
        relative=str(path.relative_to(root))
        if pe.FILE_HEADER.Machine!=MACHINES[architecture] and not anycpu:issues.append({'file':relative,'reason':'wrong architecture','machine':pe.FILE_HEADER.Machine})
        if blocked:issues.append({'file':relative,'reason':'unsupported direct Windows API import','apis':sorted(blocked)})
        result.append({'file':relative,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'machine':pe.FILE_HEADER.Machine,'managedAnyCpu':anycpu})
        pe.close()
    if not result:raise ValueError('No executable binaries found')
    return {'architecture':architecture,'minimumWindows':minimum_windows,'targetOsVerified':False,'binaries':result,'issues':issues}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);parser.add_argument('--architecture',choices=MACHINES,required=True);parser.add_argument('--minimum-windows',type=int,default=7);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=audit(args.root.resolve(),args.architecture,args.minimum_windows)
    args.output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('PE binaries:',len(result['binaries']),'issues:',len(result['issues']));raise SystemExit(1 if result['issues'] else 0)
