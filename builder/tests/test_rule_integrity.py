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

    # A model-written inventory may be inconsistent. The normaliser must never crash the build on it (the hidden-case
    # build of 11 Oct 2026 died on "multiple replacements"): it resolves what it can and warns on stderr (the trace).
    def test_duplicate_ids_are_renumbered_not_fatal(self):
        out = normalise([rule('same'), rule('same')])
        self.assertEqual([r['id'] for r in out], ['R01', 'R02'])
        self.assertTrue(all(r['in_force'] for r in out))

    def test_unknown_override_is_dropped_with_rule_kept(self):
        out = normalise([rule('memo', 'missing-policy')])
        self.assertEqual(out[0]['overrides'], '')
        self.assertTrue(out[0]['in_force'])

    def test_self_override_is_dropped(self):
        out = normalise([rule('memo', 'memo')])
        self.assertEqual(out[0]['overrides'], '')
        self.assertTrue(out[0]['in_force'])

    def test_cycle_is_broken_and_one_rule_stays_in_force(self):
        out = normalise([rule('a', 'b'), rule('b', 'c'), rule('c', 'a')])
        self.assertEqual(sum(r['in_force'] for r in out), 1)
        for r in out:
            if r['overrides']:
                self.assertIn(r['overrides'], {x['id'] for x in out})

    def test_chaining_that_creates_a_second_shared_target_resolves(self):
        # X overrides A; A and B both override T. Chaining B after A makes A a shared target of X and B: before the fix
        # this raised "multiple replacements for"; now it chains to a fixed point with exactly one rule in force.
        out = normalise([rule('T'), rule('A', 'T'), rule('X', 'A'), rule('B', 'T')])
        self.assertEqual(sum(r['in_force'] for r in out), 1)
        self.assertEqual(out[0]['in_force'], False)
        chain = {r['id']: r['overrides'] for r in out if r['overrides']}
        self.assertEqual(len(set(chain.values())), len(chain), 'every superseded rule has exactly one successor')

    def test_competing_replacements_chain_in_document_order(self):
        # Two later documents overriding the same rule: the later one (by date, then position) is in force.
        out = normalise([rule('original'), rule('memo1', 'original'), rule('memo2', 'original')])
        self.assertEqual([r['in_force'] for r in out], [False, False, True])
        self.assertEqual(out[2]['overrides'], out[1]['id'])
        self.assertEqual(out[0]['superseded_by'], out[1]['id'])

    def test_uncovered_numbers_fail_but_metadata_tokens_are_diagnostic(self):
        with self.assertRaisesRegex(ValueError, 'omits numbered'):
            require_numbered_coverage({'missing_numbers': {'brief.md': [7]}, 'missing_tokens': []})
        require_numbered_coverage({'missing_numbers': {}, 'missing_tokens': ['2026-10-10']})

    def test_bundle_numbered_items_are_advisory(self):
        import tempfile, pathlib
        from builder.rules import self_check
        bundle = ("=" * 20 + " DOCUMENT FILE: sources/notes.txt " + "=" * 20 + "\n"
                  "Meeting points\n1. coffee\n2. the menu code list\n8. second factor was never built\n")
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 'final.brief.md'
            p.write_text(bundle)
            chk = self_check([{'id': 'R1', 'text': 'x', 'source': 'notes.txt'}], [str(p)])
        self.assertEqual(chk['missing_numbers'], {})
        self.assertEqual(chk['advisory_numbers'], {'final.brief.md': [1, 2, 8]})
        logged = []
        require_numbered_coverage(chk, log=logged.append)
        self.assertTrue(logged and 'advisory' in logged[0])


if __name__ == '__main__':
    unittest.main()
