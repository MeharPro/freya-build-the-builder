"""Provider portability, Responses continuation and failure-boundary regressions."""
import asyncio
import copy
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'builder'))
from builder import build, model_provider as mp, openai_agent as agent
import rules


class Log:
    def __init__(self):
        self.records = []
    def line(self, value):
        self.records.append(value)
    def raw(self, value):
        self.records.append(copy.deepcopy(value))


def completed(text='done', output=None):
    return {'status': 'completed', 'id': 'response-fixture', 'usage': {'input_tokens': 7, 'output_tokens': 3},
            'output': output if output is not None else [
                {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': text}]}]}


class OpenAITests(unittest.TestCase):
    def test_credentials_select_provider_and_explicit_choice_wins(self):
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'fixture'}, clear=True):
            self.assertEqual(mp.provider(), 'openai')
            self.assertEqual(mp.model_for('audit'), mp.DEFAULT_OPENAI_MODEL)
            os.environ['ANTHROPIC_API_KEY'] = 'fixture'
            self.assertEqual(mp.provider(), 'claude')
            os.environ['BUILDER_PROVIDER'] = 'openai'
            self.assertEqual(mp.provider(), 'openai')
            os.environ['AUDIT_MODEL'] = 'explicit-model'
            self.assertEqual(mp.model_for('audit'), 'explicit-model')

    def test_openai_preflight_never_imports_claude(self):
        args = build.parse_args(['briefs/brief-a.md', 'tools/openapi.json'])
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'fixture', 'FREYA_API_KEY': 'fixture',
                                    'FREYA_BANK_TEAM_KEY': 'fixture-team-key-123'}, clear=True), \
             patch.dict(sys.modules, {'claude_agent_sdk': None}):
            build.preflight(args)

    def test_strict_schema_restores_nested_optional_fields_without_mutating_original(self):
        schema = {'type': 'object', 'properties': {'nested': {'type': 'object',
                  'properties': {'present': {'type': 'boolean'}, 'optional': {'type': 'string'}},
                  'required': ['present']}}, 'required': ['nested']}
        before = copy.deepcopy(schema)
        strict = mp.strict_schema(schema)
        self.assertEqual(schema, before)
        self.assertFalse(strict['additionalProperties'])
        self.assertIn('optional', strict['properties']['nested']['required'])
        value = mp.restore_optional({'nested': {'present': False, 'optional': None}}, schema)
        self.assertEqual(value, {'nested': {'present': False}})
        mp.validate_json(value, schema)
        with self.assertRaises(ValueError):
            mp.validate_json({'nested': {}}, schema)

    def test_all_current_helper_schemas_can_be_normalized(self):
        import audit, cases
        for module in (rules, audit, cases):
            for name, schema in vars(module).items():
                if name.endswith('SCHEMA') and isinstance(schema, dict):
                    normalized = mp.strict_schema(schema)
                    self.assertEqual(normalized['type'], 'object', name)

    def test_rules_uses_openai_without_claude_and_records_unknown_cost(self):
        import model_provider
        schema = {'type': 'object', 'properties': {'ok': {'type': 'boolean'}}, 'required': ['ok']}
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'fixture'}, clear=True), \
             patch.dict(sys.modules, {'claude_agent_sdk': None}), \
             patch.object(model_provider, 'request_response', return_value=completed('{"ok": true}')) as api:
            result, info = asyncio.run(rules.ask_json_async('check', 'system', schema, 'test', log=lambda _: None))
        self.assertEqual(result, {'ok': True})
        self.assertIsNone(info['cost_usd'])
        self.assertEqual(info['usage']['input_tokens'], 7)
        self.assertEqual(api.call_args.args[0]['model'], mp.DEFAULT_OPENAI_MODEL)

    def test_incomplete_refused_and_invalid_responses_fail_closed(self):
        for response in ({'status': 'incomplete', 'incomplete_details': {'reason': 'max_output_tokens'}},
                         completed(output=[{'type': 'message', 'content': [{'type': 'refusal'}]}])):
            with self.assertRaises(RuntimeError):
                mp.response_text(response)
        with patch.object(mp, 'request_response', return_value=completed('{}')) as api:
            with self.assertRaisesRegex(RuntimeError, 'two attempts'):
                asyncio.run(mp.ask_json_openai('check', '', {'type': 'object', 'required': ['ok']},
                                              'test', 'fixture-model', lambda _: None))
            self.assertEqual(api.call_count, 2)

    def test_tool_roundtrip_preserves_reasoning_and_call_id(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            skill = root / '.claude/skills/build-phone-agent/SKILL.md'
            skill.parent.mkdir(parents=True)
            skill.write_text('fixture')
            (root / 'brief.md').write_text('task data')
            reasoning = {'type': 'reasoning', 'id': 'r', 'summary': [], 'encrypted_content': 'opaque'}
            call = {'type': 'function_call', 'id': 'f', 'call_id': 'call-1', 'name': 'read_file',
                    'arguments': json.dumps({'path': 'brief.md', 'start_line': 1, 'end_line': 2})}
            sent = []
            def api(payload, timeout):
                sent.append(copy.deepcopy(payload))
                return completed(output=[reasoning, call]) if len(sent) == 1 else completed()
            with patch.object(agent, 'request_response', side_effect=api):
                asyncio.run(agent.run_agent(root, 'build', 'slot', Log(), [root / 'brief.md'], 1, lambda x: x))
            self.assertIn(reasoning, sent[1]['input'])
            self.assertIn(call, sent[1]['input'])
            self.assertEqual(sent[1]['input'][-1], {'type': 'function_call_output', 'call_id': 'call-1', 'output': 'task data'})
            self.assertFalse(sent[1]['store'])

    def test_tools_reject_source_writes_credentials_and_escaping_symlinks(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            local = agent.LocalTools(root, 'slot', [], Log(), time.monotonic() + 1, lambda x: x)
            for path in ('builder/build.py', 'out/slot.rules.json', 'out/other.workflow.json', '../escape'):
                with self.assertRaises(ValueError):
                    local.path(path, write=True)
            for path in ('env.sh', '.env', 'env.backup.sh', '.git/config'):
                with self.assertRaises(ValueError):
                    local.path(path)
            (root / 'out').mkdir()
            (root / 'out/gen_slot.py').symlink_to(root / 'env.sh')
            with self.assertRaises(ValueError):
                local.path('out/gen_slot.py', write=True)

    def test_cancelled_command_is_terminated(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as folder:
                local = agent.LocalTools(folder, 'slot', [], Log(), time.monotonic() + 5, lambda x: x)
                task = asyncio.create_task(local.call('run_command', {'command': 'sleep 30', 'timeout_seconds': 30}))
                await asyncio.sleep(.05)
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await asyncio.wait_for(task, timeout=1)
        asyncio.run(scenario())

    def test_command_timeout_retains_partial_output(self):
        async def scenario():
            with tempfile.TemporaryDirectory() as folder:
                local = agent.LocalTools(folder, 'slot', [], Log(), time.monotonic() + 5, lambda x: x)
                result = json.loads(await local.call('run_command', {
                    'command': "echo started; echo diagnostic >&2; sleep 30", 'timeout_seconds': 1}))
                self.assertTrue(result['timed_out'])
                self.assertNotEqual(result['returncode'], 0)
                self.assertIn('started', result['stdout'])
                self.assertIn('diagnostic', result['stderr'])
        asyncio.run(scenario())

    def test_nested_model_calls_are_visible_in_plain_trace(self):
        trace = Log()
        agent.promote_child_model_calls(trace, json.dumps({
            'returncode': 124, 'timed_out': True,
            'stdout': 'PASS PUB-01\n',
            'stderr': 'model call: gpt-5-mini | purpose: practice customer\n'
                      'model call result: gpt-5-mini | usage={}\n',
        }))
        self.assertEqual(trace.records, [
            'model call: gpt-5-mini | purpose: practice customer',
            'model call result: gpt-5-mini | usage={}',
        ])

    def test_driven_smoke_uses_openai_without_claude(self):
        from builder import smoke
        with patch.dict(os.environ, {'OPENAI_API_KEY': 'fixture'}, clear=True), \
             patch.dict(sys.modules, {'claude_agent_sdk': None}), \
             patch.object(mp, 'request_response', return_value=completed('Yes, speaking.')) as api:
            self.assertEqual(smoke.ask_customer('persona', 'hello', 'fixture-model'), 'Yes, speaking.')
            self.assertEqual(api.call_args.args[0]['model'], 'fixture-model')

    def test_unknown_cost_survives_aggregation(self):
        self.assertIsNone(mp.cost_round(mp.cost_sum(1.2, None)))
        self.assertIn('unavailable', mp.cost_label(None))


if __name__ == '__main__':
    unittest.main()
