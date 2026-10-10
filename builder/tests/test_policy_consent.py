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
