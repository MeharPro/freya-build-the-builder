"""Consent regressions from an observed multi-product over-recording failure."""
import unittest
import test_policy as fixtures


class ProductConsentTests(unittest.TestCase):
    def start(self):
        return fixtures.start([fixtures.CARD, fixtures.LOAN, fixtures.CAR], multi=True, notes=True)

    def test_date_without_product_scope_cannot_agree_all_products(self):
        policy, state = self.start()
        fixtures.ev(policy, state, 'offer', offer_kind='exact', offer_when='tomorrow', offer_for='none')
        self.assertTrue(all(state['state_' + p] == 'open' for p in ('p1', 'p2', 'p3')))
        self.assertEqual(state['route'], 'negotiate')
        self.assertEqual(state['stage'], 'one')

    def test_partial_confirmation_does_not_record_unconfirmed_products(self):
        for event in ('change', 'confirm_yes'):
            with self.subTest(event=event):
                policy, state = self.start()
                fixtures.ev(policy, state, 'offer', offer_kind='exact', offer_when='tomorrow', offer_for='all')
                self.assertEqual(state['route'], 'confirm')
                fixtures.ev(policy, state, event, offer_for='first', offer_when='tomorrow')
                self.assertEqual(state['state_p1'], 'agreed')
                self.assertEqual(state['state_p2'], 'open')
                self.assertEqual(state['state_p3'], 'open')
                self.assertEqual(state['route'], 'negotiate')
                self.assertNotEqual(state.get('route'), 'record')

    def test_acceptance_of_one_product_does_not_agree_every_product(self):
        policy, state = self.start()
        fixtures.ev(policy, state, 'accept', stance='accept', offer_for='first')
        self.assertEqual(state['state_p1'], 'agreed')
        self.assertEqual(state['state_p2'], 'open')
        self.assertEqual(state['state_p3'], 'open')
        self.assertEqual(state['route'], 'negotiate')

    def test_confirmation_extracts_fresh_product_scope(self):
        policy, _ = self.start()
        node = policy.confirm_node('Confirm the read-back.', 'yes or no', 'date', 'amount')
        fields = {e['name']: e for e in node['extraction_schema']}
        self.assertIn('offer_for', fields)
        self.assertIn('exclusions', fields['offer_for']['description'])
        self.assertIn('EVERY item', fields['confirm']['description'])


class PolicyBoundaryTests(unittest.TestCase):
    def test_explicit_nonpositive_offer_is_never_replaced_with_current_amount(self):
        for amount in ('0', '-5'):
            for event in ('offer', 'change'):
                with self.subTest(amount=amount, event=event):
                    policy, state = fixtures.start([fixtures.CARD])
                    if event == 'change':
                        fixtures.ev(policy, state, 'accept')
                    fixtures.ev(policy, state, event, offer_kind='exact', offer_when='tomorrow',
                                offer_amount=amount, offer_amount_present='yes')
                    self.assertIn('below_floor', state['offer_verdict'])
                    self.assertEqual(state['state_p1'], 'open')
                    self.assertNotEqual(state['route'], 'record')

    def test_amount_absence_does_not_reuse_stale_extraction(self):
        policy, state = fixtures.start([fixtures.CARD])
        fixtures.ev(policy, state, 'offer', offer_kind='exact', offer_when='tomorrow',
                    offer_amount='999', offer_amount_present='no')
        self.assertTrue(state['agreed_p1'].startswith('420'), state['agreed_p1'])

    def test_hardship_retains_explicit_zero_for_offer_guard(self):
        policy, state = fixtures.start([fixtures.CARD])
        fixtures.ev(policy, state, 'hardship', offer_kind='exact', offer_when='tomorrow',
                    offer_amount='0', offer_amount_present='yes')
        fixtures.ev(policy, state, 'hs_decline')
        self.assertIn('below_floor', state['offer_verdict'])
        self.assertEqual(state['state_p1'], 'open')

    def test_human_counter_survives_prepare_and_wrapup(self):
        policy, state = fixtures.start([fixtures.CARD])
        state['human_count'] = '1'
        fixtures.run(policy.prepare_code(fixtures.BODY, 'statement'), state)
        self.assertEqual(state['human_count'], '1')
        fixtures.ev(policy, state, 'wrap_human')
        self.assertEqual(state['route'], 'xfer_general')

    def test_stop_talking_in_wrapup_preserves_recorded_outcome(self):
        policy, state = fixtures.start([fixtures.CARD])
        state['state_p1'] = 'recorded'
        fixtures.ev(policy, state, 'wrap_notalk')
        self.assertEqual(state['route'], 'wrapup')
        fixtures.ev(policy, state, 'wrap_notalk')
        self.assertEqual(state['route'], 'fin')
        self.assertEqual(state['final_route'], policy.P['fin_keys']['promise'])
