"""No database: validate lowering and strict financial alignment on generated code."""
import importlib.util
from pathlib import Path
import unittest
spec=importlib.util.spec_from_file_location('legacy_source',Path(__file__).with_name('legacy_source.py'))
legacy=importlib.util.module_from_spec(spec);spec.loader.exec_module(legacy)

class LegacySourceTests(unittest.TestCase):
    def test_annotations_and_future_order(self):
        source='"""Keep docstring"""\nfrom __future__ import annotations\n# Preserve comment\ndef f(value: list[str | None]) -> dict[str, int]:\n    return {}\n'
        output=legacy.lower(source)
        namespace={};exec(output,namespace)
        self.assertEqual(namespace['__doc__'],'Keep docstring')
        self.assertIn('# Preserve comment',output)
        self.assertIn('_cubita_typing.Union',output)
        self.assertIn('_cubita_typing.List',output)

    def test_bitwise_values_untouched(self):
        source='result = 3 | 4\nvalue = flags[3 | 4]\n'
        self.assertEqual(legacy.lower(source),source)

    def test_runtime_response_type(self):
        output=legacy.lower('from typing import Annotated\nfrom collections.abc import Iterable\ndef f(rows: Iterable[str]):\n    pass\nroute(response_model=list[str] | None)\n')
        self.assertIn('from typing_extensions import Annotated',output)
        self.assertIn('_cubita_typing.Iterable',output)
        self.assertIn('_cubita_typing.Union',output)

    def test_financial_zip_cannot_truncate(self):
        runtime={};exec(legacy.RUNTIME,runtime)
        zip_strict=runtime['zip_strict']
        self.assertEqual(list(zip_strict([1,2],[3,4],strict=True)),[(1,3),(2,4)])
        for args in [([1],[2,3]),([1,2],[3]),([], [1])]:
            with self.assertRaises(ValueError):list(zip_strict(*args,strict=True))
        self.assertEqual(list(zip_strict([1],[2,3])),[(1,2)])
        self.assertEqual(list(zip_strict(strict=True)),[])

    def test_text_and_path_boundaries(self):
        runtime={};exec(legacy.RUNTIME,runtime)
        self.assertEqual(runtime['removeprefix']('cubita:repair:123','cubita:repair:'),'123')
        self.assertEqual(runtime['removesuffix']('123',''),'123')
        self.assertTrue(runtime['is_relative_to'](Path('/a/b'),Path('/a')))
        self.assertFalse(runtime['is_relative_to'](Path('/abc'),Path('/a')))

    def test_generated_call_preserves_strict(self):
        result=legacy.lower('for a,b in zip(lines,amounts,strict=True):\n    pass\n')
        self.assertIn('_cubita_legacy.zip_strict',result)
        self.assertIn('strict=True',result)

if __name__=='__main__':unittest.main()
