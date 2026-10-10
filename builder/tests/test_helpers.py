"""Execute generated helper code against changed calendars and API fields."""
import copy
import datetime as dt
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'builder'))
import freyalib as fl
import multiproduct as mp


class HelperTests(unittest.TestCase):
    def test_calendar_skips_holidays_weekends_and_year_boundary(self):
        g = {}
        exec(fl.CAL_HELPERS(['2027-01-01']), g)
        self.assertEqual(g['addbd'](dt.date(2026, 12, 31), 1), dt.date(2027, 1, 4))
        self.assertEqual(g['addbd'](dt.date(2026, 12, 31), 0), dt.date(2026, 12, 31))

    def test_changed_workweek_is_used_and_invalid_calendars_rejected(self):
        g = {}
        exec(fl.CAL_HELPERS([], [0, 1, 2, 3, 4, 5]), g)
        self.assertEqual(g['addbd'](dt.date(2026, 10, 16), 1), dt.date(2026, 10, 17))
        for days in ([], [-1], [7]):
            with self.assertRaises(ValueError):
                fl.CAL_HELPERS([], days)
        with self.assertRaises(ValueError):
            fl.CAL_HELPERS(['2026-02-30'])

    def test_api_changes_do_not_inject_customer_id_or_drop_required_fields(self):
        api = {'servers': [{'url': 'https://bank.example'}], 'paths': {'/get_account': {'post': {
            'requestBody': {'content': {'application/json': {'schema': {'type': 'object',
                'properties': {'client_ref': {'type': 'string'}, 'mode': {'type': 'integer', 'enum': [1, 2]}},
                'required': ['client_ref', 'mode']}}}}}}}}
        tool = fl.api_tool(api, 'get_account', baked={'client_ref': '{{customer_id}}', 'mode': 1})
        props = tool['function']['parameters']['properties']['body']['properties']
        self.assertEqual(set(props), {'client_ref', 'mode'})
        with self.assertRaises(ValueError):
            fl.api_tool(api, 'get_account', omit=['client_ref'])
        with self.assertRaises(ValueError):
            fl.api_tool(api, 'get_account', baked={'mode': 3})

    def test_changed_failure_enum_compiles_and_preserves_text(self):
        reason = "service-unavailable/customer's-request"
        g = {'vars': {'pending_pid': 'loan_7', 'pids_csv': 'loan_7'}, 'result': {'data': {'ok': 'false'}}}
        code = mp.promise_post_code(max_fails=1, fail_reason=reason)
        exec(code, g)
        self.assertIn(reason, g['result']['data']['what_to_do_next'])
        self.assertNotIn('loan_7', g['vars'].get('rec_pids', ''))

    def test_product_retry_and_success_only_update_correct_product(self):
        state = {'pending_pid': 'p2', 'pids_csv': 'p1,p2,p3', 'rec_pids': 'p1', 'note_log': 'p3:refused'}
        code = mp.promise_post_code(max_fails=2)
        for value in (False, 'false'):
            g = {'vars': state, 'result': {'data': {'ok': value}}}
            exec(code, g)
            self.assertEqual(state['rec_pids'], 'p1')
            self.assertEqual(state['all_done'], 'no')
            self.assertIn('NOT recorded', g['result']['data']['what_to_do_next'])
        self.assertEqual(state['fail_p2'], 2)
        self.assertIn('service_error', g['result']['data']['what_to_do_next'])
        g['result'] = {'data': {'ok': 'True'}}
        exec(code, g)
        self.assertEqual(state['rec_pids'], 'p1,p2')
        self.assertEqual(state['all_done'], 'yes')
        exec(code, g)
        self.assertEqual(state['rec_pids'], 'p1,p2')

    def test_changed_schema_e_builds_all_seven_tools(self):
        api = json.loads((ROOT / 'tests/synthetic/brief-e.openapi.json').read_text())
        names = fl.tool_names(api)
        self.assertEqual(len(names), 7)
        for name in names:
            tool = fl.api_tool(api, name)
            actual = tool['function']['parameters']['properties']['body']['properties']
            self.assertEqual(set(actual), set(fl.tool_spec(api, name)['fields']))


if __name__ == '__main__':
    unittest.main()
