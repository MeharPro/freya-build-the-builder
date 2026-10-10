"""An incomplete or contradictory inventory must not certify its own omissions."""
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2]))
from builder.rules import normalise, require_numbered_coverage


def rule(identifier, overrides=""):
    return {"id": identifier, "text": "Synthetic obligation " + identifier, "overrides": overrides}


class RuleIntegrityTests(unittest.TestCase):
    def test_override_chain_keeps_only_latest_in_force(self):
        rows = normalise([rule('original'), rule('memo', 'original'), rule('correction', 'memo')])
        self.assertEqual([r['in_force'] for r in rows], [False, False, True])
        self.assertEqual(rows[0]['superseded_by'], 'R02')
        self.assertEqual(rows[2]['overrides'], 'R02')

    def test_duplicate_ids_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            normalise([rule('same'), rule('same')])

    def test_unknown_override_is_not_silently_erased(self):
        with self.assertRaisesRegex(ValueError, 'unknown'):
            normalise([rule('memo', 'missing-policy')])

    def test_self_override_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'itself'):
            normalise([rule('memo', 'memo')])

    def test_cycle_cannot_remove_all_active_obligations(self):
        with self.assertRaisesRegex(ValueError, 'cyclic'):
            normalise([rule('a', 'b'), rule('b', 'c'), rule('c', 'a')])

    def test_competing_replacements_require_explicit_order(self):
        with self.assertRaisesRegex(ValueError, 'multiple replacements'):
            normalise([rule('original'), rule('memo1', 'original'), rule('memo2', 'original')])

    def test_uncovered_numbers_fail_but_metadata_tokens_are_diagnostic(self):
        with self.assertRaisesRegex(ValueError, 'omits numbered'):
            require_numbered_coverage({'missing_numbers': {'brief.md': [7]}, 'missing_tokens': []})
        require_numbered_coverage({'missing_numbers': {}, 'missing_tokens': ['2026-10-10']})


if __name__ == '__main__':
    unittest.main()
