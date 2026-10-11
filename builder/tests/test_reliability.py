"""Regression tests for failures that must never produce a submission."""
import asyncio
import contextlib
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from builder import build
from builder.reliability import (Budget, BuildFailure, archive_previous, run_process,
                                 validate_artifact, validate_audit, workspace_lock, write_manifest)


class ReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, path, value):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(value))
        return p

    def test_budget_rejects_invalid_and_caps_every_step(self):
        for value in (0, -1, 31, float('nan'), float('inf')):
            with self.assertRaises(ValueError):
                Budget(value)
        now = [0]
        b = Budget(1, clock=lambda: now[0])
        self.assertEqual(b.timeout(120, reserve=10), 50)
        now[0] = 60
        with self.assertRaises(BuildFailure):
            b.timeout(120)

    def test_source_freeze_rejects_edits_removal_and_new_helpers(self):
        source = self.write('builder/helper.py', 'original')
        expected = build.source_snapshot(self.root)
        build.require_unchanged_source(self.root, expected)
        source.write_text('changed')
        with self.assertRaises(BuildFailure):
            build.require_unchanged_source(self.root, expected)
        source.unlink()
        with self.assertRaises(BuildFailure):
            build.require_unchanged_source(self.root, expected)
        self.write('builder/helper.py', 'original')
        self.write('builder/new_helper.py', 'new policy')
        with self.assertRaises(BuildFailure):
            build.require_unchanged_source(self.root, expected)

    def test_process_timeout_is_not_success(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            run_process([sys.executable, '-c', 'import time; time.sleep(5)'], self.root, .05)

    def test_timeout_preserves_model_call_and_test_output(self):
        with self.assertRaises(subprocess.TimeoutExpired) as caught:
            run_process([sys.executable, '-u', '-c',
                         "import sys,time; print('test started'); print('model call: fixture',file=sys.stderr); time.sleep(5)"], self.root, .2)
        self.assertIn('test started', caught.exception.output)
        self.assertIn('model call: fixture', caught.exception.stderr)

    def test_archive_keeps_previous_artifacts_and_removes_stale_candidates(self):
        for p in ('out/x.workflow.json', 'out/gen_x.py', 'out/x.rules.json', 'submission/x.workflow.json', 'traces/x.log'):
            self.write(p, {'old': True})
        archive = archive_previous(self.root, 'x', 'run-1')
        self.assertFalse((self.root / 'out/x.workflow.json').exists())
        self.assertFalse((self.root / 'submission/x.workflow.json').exists())
        self.assertEqual(json.loads((archive / 'submission/x.workflow.json').read_text()), {'old': True})

    def test_workspace_lock_rejects_concurrent_build(self):
        with workspace_lock(self.root):
            with self.assertRaises(BuildFailure):
                with workspace_lock(self.root):
                    self.fail('must not enter second lock')
        with workspace_lock(self.root):
            pass

    def test_manifest_hash_changes_with_artifact(self):
        source = self.write('source.md', 'brief')
        artifact = self.write('export.json', {'a': 1})
        m = write_manifest(self.root / 'manifest.json', [source], [artifact], 'run', 'start', 1, True)
        artifact.write_text('changed')
        from builder.reliability import sha256
        self.assertNotEqual(m['artifacts'][0]['sha256'], sha256(artifact))

    def test_audit_checks_active_rule_rows_not_claimed_summary(self):
        rules = self.write('rules.json', [{'id': 'R1', 'in_force': True}, {'id': 'R2', 'in_force': False}])
        for rows in ([], [{'id': 'R1', 'status': 'missing'}], [{'id': 'R1', 'status': 'partial'}],
                     [{'id': 'R1', 'status': 'implemented', 'evidence_found': False}]):
            report = self.write('audit.json', {'summary': {'implemented': 100}, 'rules': rows})
            with self.assertRaises(BuildFailure):
                validate_audit(report, rules)
        report = self.write('audit.json', {'rules': [{'id': 'R1', 'status': 'implemented', 'evidence_found': True}]})
        validate_audit(report, rules)

    def test_artifact_gate_rejects_test_variables_and_initial_code(self):
        wf = json.loads((ROOT / 'out/brief-a_v2.notv.workflow.json').read_text())
        p = self.write('workflow.json', wf)
        validate_artifact(p, ROOT / 'tools/openapi.json')
        wf['test_variables'] = {'customer_id': 'test'}
        p.write_text(json.dumps(wf))
        with self.assertRaisesRegex(BuildFailure, 'test_variables'):
            validate_artifact(p, ROOT / 'tools/openapi.json')
        del wf['test_variables']
        wf['initial_node'] = 'setup'
        p.write_text(json.dumps(wf))
        with self.assertRaisesRegex(BuildFailure, 'Initial node'):
            validate_artifact(p, ROOT / 'tools/openapi.json')

    def test_artifact_gate_rejects_network_calls_in_code(self):
        wf = json.loads((ROOT / 'out/brief-a_v2.notv.workflow.json').read_text())
        node = next(n for n in wf['nodes'].values() if n.get('node_type') == 'code')
        # Code functions are represented through the code_exec tool, as Freya executes them.
        target = node['pre_actions'][0]['function']['parameters']['properties']['code']
        target['default'] = "import urllib.request\ntry:\n    urllib.request.urlopen('https://other.example')\nexcept Exception:\n    pass\n"
        p = self.write('network.workflow.json', wf)
        with self.assertRaisesRegex(BuildFailure, 'network or process client'):
            validate_artifact(p, ROOT / 'tools/openapi.json')

    def test_platform_optional_defaults_do_not_change_export_bytes(self):
        wf = json.loads((ROOT / 'out/brief-a_v2.notv.workflow.json').read_text())
        wf['nodes'][wf['initial_node']]['max_turn_transition'] = None
        wf['agent_config'] = {'llmConfig': {'provider': 'experimental-5', 'model': 'experimental-5',
                                          'apiKey': None, 'baseUrl': None}}
        p = self.write('export.json', {'workflow': wf})
        original = p.read_bytes()
        with self.assertRaisesRegex(BuildFailure, 'null value'):
            validate_artifact(p, ROOT / 'tools/openapi.json')
        data = validate_artifact(p, ROOT / 'tools/openapi.json', platform_export=True)
        self.assertEqual(p.read_bytes(), original)
        self.assertIsNone(data['workflow']['agent_config']['llmConfig']['apiKey'])

    def test_platform_mode_still_rejects_null_tool_fields_and_model(self):
        original = json.loads((ROOT / 'out/brief-a_v2.notv.workflow.json').read_text())
        for kind in ('tool', 'model'):
            with self.subTest(kind=kind):
                wf = copy.deepcopy(original)
                if kind == 'tool':
                    node = next(n for n in wf['nodes'].values() if n.get('tools'))
                    node['tools'][0]['function']['description'] = None
                else:
                    wf['agent_config'] = {'llmConfig': {'provider': 'experimental-5', 'model': None}}
                p = self.write(kind + '.export.json', {'workflow': wf})
                with self.assertRaisesRegex(BuildFailure, 'null value'):
                    validate_artifact(p, ROOT / 'tools/openapi.json', platform_export=True)

    def test_cli_rejects_unknown_flags_bad_runner_and_unbounded_time(self):
        inputs = [str(ROOT / 'briefs/brief-a.md'), str(ROOT / 'tools/openapi.json')]
        for flags in (['--typo'], ['--runner', 'unknown'], ['--minutes', '31'], ['--minutes', 'nan'], ['--no-rules']):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as e:
                build.parse_args(inputs + flags)
            self.assertEqual(e.exception.code, 2)

    def test_scrub_hides_environment_secrets_including_short_team_key(self):
        with patch.dict(os.environ, {'FREYA_BANK_TEAM_KEY': 'tiny', 'FREYA_API_KEY': 'fak_' + 'x' * 25}):
            result = build.scrub('tiny fak_' + 'x' * 25)
            self.assertNotIn('tiny', result)
            self.assertNotIn('x' * 25, result)

    def test_failed_model_does_not_export_old_workflow(self):
        self.write('submission/x.workflow.json', {'old': True})
        self.write('out/x.workflow.json', {'old': True})
        brief = self.write('x.md', 'input')
        api = self.write('api.json', {})
        args = build.parse_args([str(brief), str(api), '--no-rules', '--no-audit'])
        async def fail(*args, **kwargs):
            raise RuntimeError('model unavailable')
        with patch.object(build, 'ROOT', self.root), patch.object(build, 'run_claude', fail), \
             patch.object(build, 'required_step') as helper, contextlib.redirect_stdout(io.StringIO()):
            code = asyncio.run(build.execute_build(args))
        self.assertEqual(code, 1)
        helper.assert_not_called()
        self.assertFalse((self.root / 'submission/x.workflow.json').exists())
        self.assertIn('status=failed', (self.root / 'traces/x.log').read_text())
        self.assertTrue(list((self.root / 'build-history').glob('*/submission/x.workflow.json')))

    def run_pipeline(self, fail_stage=None, audit_statuses=None, tamper_rules=False, time_slice=False):
        brief = self.write('x.md', 'input')
        api = self.write('api.json', json.loads((ROOT / 'tools/openapi.json').read_text()))
        args = build.parse_args([str(brief), str(api)])
        fixture = json.loads((ROOT / 'out/brief-a_v2.notv.workflow.json').read_text())
        calls = []
        audit_statuses = list(audit_statuses or ['implemented'])
        async def generate(*args, **kwargs):
            self.write('out/x.workflow.json', fixture)
            (self.root / 'out/gen_x.py').write_text('# Generated during this run\n')
            if kwargs.get('repair_feedback'):
                self.assertTrue(Path(kwargs['repair_feedback']).exists())
                self.assertFalse((self.root / 'submission/x.workflow.json').exists())
            if tamper_rules:
                self.write('out/x.rules.json', [{'id': 'R1', 'in_force': False}])
            if time_slice:
                raise asyncio.TimeoutError()

        def step(trace, budget, name, cmd, maximum, reserve=0):
            calls.append(name)
            if fail_stage == name:
                raise BuildFailure(name + ' failed')
            if name == 'rules':
                self.write('out/x.rules.json', [{'id': 'R1', 'in_force': True}])
            if name == 'export':
                self.write('submission/x.workflow.json', {'workflow': fixture})
            if name == 'audit':
                self.write('out/x.audit.json', {'rules': [{'id': 'R1', 'status': audit_statuses[min(calls.count('audit')-1, len(audit_statuses)-1)], 'evidence_found': True}]})
            return ''
        with patch.object(build, 'ROOT', self.root), patch.object(build, 'run_claude', generate), \
             patch.object(build, 'required_step', step), contextlib.redirect_stdout(io.StringIO()):
            code = asyncio.run(build.execute_build(args))
        return code, calls

    def test_audit_repair_republishes_and_preserves_failed_attempt(self):
        code, calls = self.run_pipeline(audit_statuses=['partial', 'implemented'])
        self.assertEqual(code, 0)
        self.assertEqual(calls.count('publish'), 2)
        self.assertEqual(calls.count('audit'), 2)
        saved = list((self.root / 'build-history').glob('*/attempt-1/x.audit.json'))
        self.assertEqual(len(saved), 1)
        self.assertEqual(json.loads(saved[0].read_text())['rules'][0]['status'], 'partial')

    def test_unresolved_audit_stops_after_two_repairs(self):
        code, calls = self.run_pipeline(audit_statuses=['partial'])
        self.assertEqual(code, 1)
        self.assertEqual(calls.count('audit'), 3)
        self.assertFalse((self.root / 'submission/x.workflow.json').exists())

    def test_inventory_tampering_rejected_before_publication(self):
        code, calls = self.run_pipeline(tamper_rules=True)
        self.assertEqual(code, 1)
        self.assertNotIn('publish', calls)
        self.assertIn('rule inventory', (self.root / 'traces/x.log').read_text())

    def test_saved_candidate_after_time_slice_still_requires_audit(self):
        code, calls = self.run_pipeline(time_slice=True)
        self.assertEqual(code, 0)
        self.assertEqual(calls[-1], 'audit')

    def test_full_success_writes_manifest_after_final_trace(self):
        code, calls = self.run_pipeline()
        self.assertEqual(code, 0)
        self.assertEqual(calls, ['rules', 'lint', 'publish', 'export', 'audit'])
        manifest = json.loads((self.root / 'submission/x.manifest.json').read_text())
        from builder.reliability import sha256
        for artifact in manifest['artifacts']:
            self.assertEqual(artifact['sha256'], sha256(artifact['path']))
        self.assertTrue(manifest['audited'])

    def test_publish_failure_never_reaches_export(self):
        code, calls = self.run_pipeline('publish')
        self.assertEqual(code, 1)
        self.assertNotIn('export', calls)
        self.assertFalse((self.root / 'submission/x.workflow.json').exists())

    def test_audit_failure_moves_export_out_of_submission(self):
        code, calls = self.run_pipeline('audit')
        self.assertEqual(code, 1)
        self.assertTrue((self.root / 'out/x.rejected-export.json').exists())
        self.assertFalse((self.root / 'submission/x.workflow.json').exists())
        self.assertFalse((self.root / 'submission/x.manifest.json').exists())

    def test_rules_failure_never_reaches_model_or_publish(self):
        code, calls = self.run_pipeline('rules')
        self.assertEqual(code, 1)
        self.assertEqual(calls, ['rules'])
        self.assertFalse((self.root / 'out/gen_x.py').exists())


if __name__ == '__main__':
    unittest.main()
