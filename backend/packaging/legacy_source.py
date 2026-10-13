"""Prepare an isolated Python3.8 source tree. Run using the build-host Python and libcst.

Only annotations and explicit newer runtime APIs are lowered. No source, schema,
financial rule, environment file or customer data is changed in the original tree.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import libcst as cst

class TypeExpression(cst.CSTTransformer):
    def __init__(self, abc_names=None): self.abc_names = abc_names or {}
    def leave_BinaryOperation(self, original, updated):
        if isinstance(updated.operator, cst.BitOr):
            return cst.Subscript(cst.Attribute(cst.Name('_cubita_typing'), cst.Name('Union')), [cst.SubscriptElement(cst.Index(updated.left)), cst.SubscriptElement(cst.Index(updated.right))])
        return updated

    def leave_Subscript(self, original, updated):
        names = {**self.abc_names, 'list': 'List', 'dict': 'Dict', 'tuple': 'Tuple', 'set': 'Set', 'frozenset': 'FrozenSet', 'type': 'Type'}
        if isinstance(updated.value, cst.Name) and updated.value.value in names:
            return updated.with_changes(value=cst.Attribute(cst.Name('_cubita_typing'), cst.Name(names[updated.value.value])))
        return updated

class LegacySource(cst.CSTTransformer):
    def __init__(self): self.typing = False; self.runtime = False; self.abc_names = {}

    def visit_ImportFrom(self, node):
        if isinstance(node.module,cst.Attribute) and isinstance(node.module.value,cst.Name) and node.module.value.value=='collections' and node.module.attr.value=='abc' and not isinstance(node.names,cst.ImportStar):
            for alias in node.names:
                if isinstance(alias.name,cst.Name):
                    self.abc_names[alias.asname.name.value if alias.asname else alias.name.value] = alias.name.value

    def leave_SimpleStatementLine(self, original, updated):
        body=[]
        for stmt in updated.body:
            if isinstance(stmt,cst.ImportFrom) and isinstance(stmt.module,cst.Name) and stmt.module.value=='typing' and not isinstance(stmt.names,cst.ImportStar):
                newer=[a for a in stmt.names if isinstance(a.name,cst.Name) and a.name.value in {'Annotated','Self','TypeAlias','Required','NotRequired'}]
                old=[a for a in stmt.names if a not in newer]
                if old: old[-1]=old[-1].with_changes(comma=cst.MaybeSentinel.DEFAULT); body.append(stmt.with_changes(names=old))
                if newer: newer[-1]=newer[-1].with_changes(comma=cst.MaybeSentinel.DEFAULT); body.append(stmt.with_changes(module=cst.Name('typing_extensions'),names=newer))
            else:body.append(stmt)
        return updated.with_changes(body=body)

    def leave_Annotation(self, original, updated):
        annotation = updated.annotation.visit(TypeExpression(self.abc_names))
        if not annotation.deep_equals(updated.annotation): self.typing = True
        return updated.with_changes(annotation=annotation)

    def leave_Subscript(self, original, updated):
        names = {**self.abc_names, 'list':'List','dict':'Dict','tuple':'Tuple','set':'Set','frozenset':'FrozenSet','type':'Type'}
        if isinstance(updated.value,cst.Name) and updated.value.value in names:
            self.typing=True
            return updated.with_changes(value=cst.Attribute(cst.Name('_cubita_typing'),cst.Name(names[updated.value.value]))).visit(TypeExpression(self.abc_names))
        return updated

    def leave_Arg(self, original, updated):
        if updated.keyword and updated.keyword.value=='response_model':
            value=updated.value.visit(TypeExpression(self.abc_names))
            if not value.deep_equals(updated.value):self.typing=True
            return updated.with_changes(value=value)
        return updated

    def leave_Call(self, original, updated):
        func = updated.func
        if isinstance(func, cst.Name) and func.value == 'zip' and any(a.keyword and a.keyword.value == 'strict' for a in updated.args):
            self.runtime = True
            return updated.with_changes(func=cst.Attribute(cst.Name('_cubita_legacy'), cst.Name('zip_strict')))
        if isinstance(func, cst.Attribute) and func.attr.value in ('removeprefix', 'removesuffix', 'is_relative_to'):
            self.runtime = True
            return updated.with_changes(func=cst.Attribute(cst.Name('_cubita_legacy'), func.attr), args=[cst.Arg(func.value), *updated.args])
        return updated

def lower(source):
    tree=cst.parse_module(source)
    transform=LegacySource(); tree=tree.visit(transform)
    imports=[]
    if transform.typing: imports.append(cst.parse_statement('import typing as _cubita_typing\n'))
    if transform.runtime: imports.append(cst.parse_statement('from app import _legacy_runtime as _cubita_legacy\n'))
    body=list(tree.body); index=0
    # Preserve the module docstring and keep future imports at the required start.
    if body and isinstance(body[0], cst.SimpleStatementLine) and isinstance(body[0].body[0], cst.Expr) and isinstance(body[0].body[0].value, (cst.SimpleString,cst.ConcatenatedString)): index=1
    while index<len(body) and isinstance(body[index], cst.SimpleStatementLine) and any(isinstance(s,cst.ImportFrom) and isinstance(s.module,cst.Name) and s.module.value=='__future__' for s in body[index].body):index+=1
    body[index:index]=imports
    result=tree.with_changes(body=body).code
    ast.parse(result, feature_version=(3,8))
    return result

RUNTIME = r'''"""Local compatibility helpers; never disable strict financial alignment."""
import builtins

def removeprefix(value, prefix):
    return value[len(prefix):] if value.startswith(prefix) else value

def removesuffix(value, suffix):
    return value[:-len(suffix)] if suffix and value.endswith(suffix) else value

def is_relative_to(path, other):
    try: path.relative_to(other); return True
    except ValueError: return False

def zip_strict(*iterables, strict=False):
    if not strict:
        yield from builtins.zip(*iterables)
        return
    iterators = [iter(i) for i in iterables]
    if not iterators: return
    sentinel = object()
    while True:
        values = [next(i, sentinel) for i in iterators]
        if all(value is sentinel for value in values): return
        if any(value is sentinel for value in values):
            raise ValueError('zip() arguments have different lengths')
        yield tuple(values)
'''

def prepare(backend, output, include_tests=False):
    backend=backend.resolve();output=output.resolve()
    if output==backend or backend in output.parents: raise ValueError('Use a separate output tree outside backend')
    if output.exists(): raise ValueError('Output exists; use a fresh isolated path')
    output.mkdir(parents=True)
    manifest=[]
    for name in ['app','alembic','packaging','scripts'] + (['tests'] if include_tests else []):
        root=backend/name
        if not root.exists():continue
        for path in sorted(root.rglob('*')):
            if not path.is_file() or '__pycache__' in path.parts or path.suffix in ['.pyc','.pyo']:continue
            if path.name.startswith('.env'):continue
            relative=path.relative_to(backend);dest=output/relative;dest.parent.mkdir(parents=True,exist_ok=True)
            data=path.read_bytes()
            if path.suffix=='.py':data=lower(data.decode('utf-8-sig')).encode('utf-8')
            dest.write_bytes(data)
            manifest.append({'path':relative.as_posix(),'sourceSha256':hashlib.sha256(path.read_bytes()).hexdigest(),'generatedSha256':hashlib.sha256(data).hexdigest()})
    shutil.copy2(backend/'alembic.ini',output/'alembic.ini')
    (output/'app/_legacy_runtime.py').write_text(RUNTIME,encoding='utf-8')
    (output/'legacy-source.json').write_text(json.dumps({'experimental':True,'targetOsVerified':False,'files':manifest},indent=2),encoding='utf-8')
    return len(manifest)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--include-tests',action='store_true')
    args=parser.parse_args()
    print('Prepared isolated files:',prepare(Path(__file__).resolve().parents[1],args.output,args.include_tests))
