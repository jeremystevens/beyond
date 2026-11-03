"""Supported word problems use exact safe calculations; unsupported prose is untouched."""
import unittest
from unittest.mock import patch
from app import word_math
from app.tools import calculator

TIME = ('A recording device has 1.5 hours of recording space left. Two recordings each last 35 minutes. '
        'How many minutes of space remain after both recordings? Briefly show the arithmetic.')
BUDGET = ('For this fictional planning exercise, a repair costs $220 and a replacement costs $420. '
          'My budget is $500 and both options finish on day 5. For each option state whether it fits '
          'the budget, the amount remaining or over budget, and the finish day.')
UPDATE = ('Correction: my budget is now $350. All other facts are unchanged. Re-evaluate both options '
          'and keep their finish days in your answer.')


def ask(text, history=()):
    return word_math.solve([*history, {'role': 'user', 'content': text}])


class WordMathTests(unittest.TestCase):
    def test_reported_time_has_one_consistent_result_and_actual_calculations(self):
        with patch.object(calculator, 'evaluate', wraps=calculator.evaluate) as evaluate:
            result = ask(TIME)
        self.assertEqual(result.family, 'time')
        self.assertTrue(result.text.startswith('20 minutes remain:'))
        self.assertIn('90 minutes available', result.text)
        self.assertIn('2 × 35 minutes', result.text)
        self.assertTrue(result.text.endswith('= 20 minutes.'))
        self.assertEqual(evaluate.call_count, len(result.checks))
        self.assertTrue(result.checks)

    def test_unseen_time_units_and_non_fitting_work(self):
        for text, expected in [
            ('A recorder has 2 hours remaining. Three sessions each take 25 minutes. How many minutes remain?', '45 minutes remain:'),
            ('A recorder has 10 minutes left. Two clips each last 45 seconds. How many seconds remain?', '510 seconds remain:'),
            ('A recorder has 1 hour left. Three recordings each last 25 minutes. How many minutes remain?', 'The recordings do not fit:'),
        ]:
            with self.subTest(text=text):
                self.assertTrue(ask(text).text.startswith(expected))

    def test_budget_and_updated_budget_ignore_assistant_arithmetic(self):
        result = ask(BUDGET)
        self.assertIn('Repair: fits; $280.00 remains', result.text)
        self.assertIn('Replacement: fits; $80.00 remains', result.text)
        history = [{'role': 'user', 'content': BUDGET},
                   {'role': 'assistant', 'content': 'Wrong: repair leaves $180; replacement is $20 over.'}]
        updated = ask(UPDATE, history)
        self.assertIn('Repair: fits; $130.00 remains', updated.text)
        self.assertIn('Replacement: does not fit; $70.00 over budget', updated.text)
        self.assertEqual(updated.text.count('Finishes on day 5.'), 2)
        self.assertNotIn('$20.00', updated.text)
        changed_day = ask('Correction: my budget is now $350. Both options finish on day 6. Re-evaluate whether each fits.', history)
        self.assertEqual(changed_day.text.count('Finishes on day 6.'), 2)

    def test_unseen_decimal_budgets_labels_currencies_and_boundaries(self):
        for currency in ('$','€','£'):
            for budget, a, b, left_a, left_b in [('100.10', '33.35', '100.10', '66.75', '0.00'), ('50', '55.25', '40.75', '5.25', '9.25')]:
                q = (f'A rental costs {currency}{a} and a purchase costs {currency}{b}. '
                     f'My budget is {currency}{budget}. State whether each option fits and how much remains or is over budget.')
                result = ask(q)
                self.assertEqual(result.family, 'budget')
                self.assertIn(currency + left_a, result.text)
                self.assertIn(currency + left_b, result.text)
                for check in result.checks:
                    self.assertEqual(calculator.evaluate(check['expression']), check['result'])
        self.assertIn('£0.00 remains', ask('A rental costs £10 and a purchase costs £20. With a £10 budget, state whether each option fits and how much remains.').text)

    def test_explicit_same_message_budget_correction_and_prose(self):
        q = ('A repair costs $250 and a replacement costs $550. My budget was $600, but it is now $400. '
             'For each option state whether it fits and how much remains or is over budget. No bullet points.')
        result = ask(q)
        self.assertIn('$150.00 remains', result.text)
        self.assertIn('$150.00 over budget', result.text)
        self.assertFalse(result.text.startswith('- '))

    def test_budget_context_does_not_cross_an_unrelated_user_turn(self):
        history = [{'role':'user','content':BUDGET}, {'role':'user','content':'Tell me about rainbows.'}]
        self.assertIsNone(ask(UPDATE, history))
        self.assertIsNone(ask(UPDATE, [{'role':'assistant','content':BUDGET}]))

    def test_capacity_whole_items_and_exact_decimal_scaling(self):
        q = ('A shelf supports at most 20 kg. It already holds 12 kg. Each new box weighs 3 kg. '
             'What is the maximum number of whole boxes I can add without exceeding the limit?')
        result = ask(q)
        self.assertTrue(result.text.startswith('2 whole boxes'))
        self.assertIn('= 18 kg', result.text)
        self.assertIn('3 would total 21 kg', result.text)
        for limit, current, size, count in [('0.3','0.1','0.1',2),('12.5','2','3.5',3)]:
            q = f'A shelf supports {limit} kg. It already holds {current} kg. Each crate weighs {size} kg. How many whole crates can I add?'
            self.assertTrue(ask(q).text.startswith(f'{count} whole crates'))
        q = 'A shelf supports 1 kg. It already holds 250 g. Each box weighs 125 g. How many whole boxes can I add?'
        self.assertTrue(ask(q).text.startswith('6 whole boxes'))

    def test_pack_comparisons_round_up_costs_not_unit_prices(self):
        q = ('I need at least 9 clips. Store A sells sealed packs of 5 for $6. '
             'Store B sells packs of 8 for $9. Packs cannot be split. Which store has the lowest total cost?')
        result = ask(q)
        self.assertTrue(result.text.startswith('Store A has the lowest total: $12.00.'))
        self.assertIn('Store B: 2 whole packs provide 16 items for $18.00', result.text)
        q = ('I need at least 7 pens. Shop North sells packs of 3 pens for £2.50. '
             'Shop South sells packs of 4 pens for £3. Packs cannot be split. Which shop has the lowest cost?')
        self.assertTrue(ask(q).text.startswith('Shop South has the lowest total: £6.00.'))
        self.assertIn('Shop North: 3 whole packs provide 9 items for £7.50', ask(q).text)

    def test_exact_pack_quantity_is_not_silently_changed_to_at_least(self):
        q = ('I need exactly 7 pens. Shop North sells packs of 3 for $2. '
             'Shop South sells packs of 4 for $3. Packs cannot be split. Which shop has the lowest cost?')
        self.assertIn('No store can meet the exact quantity', ask(q).text)

    def test_checkout_decimal_money_and_insufficient_payment(self):
        q = ('I pay $10 for three items costing $2.40 each and one item costing $1.75. '
             'There is no tax or other charge. How much change should I receive?')
        result = ask(q)
        self.assertTrue(result.text.startswith('You receive $1.05 in change:'))
        self.assertIn('$7.20 + $1.75 = $8.95', result.text)
        q = ('I paid €5 for two notebooks at €3.25 each and one pen at €0.50. '
             'There is no tax or other charge. How much change do I get?')
        self.assertTrue(ask(q).text.startswith('The payment is €2.00 short:'))

    def test_ambiguous_or_unsupported_requests_are_not_claimed_verified(self):
        bad = [
            'I have 3 dogs and 2 cats. Tell me about caring for them.',
            'Write a story: a repair costs $220 and a replacement costs $420. Budget is $500. Which fits?',
            'Reference: a repair costs $220 and a replacement costs $420. Budget is $500. Which fits?',
            'A repair costs $220 and a replacement costs $420. Budget is $500. Can I afford both together?',
            'A repair costs $220 and a replacement costs €420. Budget is $500. Which fits?',
            'A repair costs $220 and a replacement costs $420 plus $30 shipping. Budget is $500. Which fits?',
            'A repair costs about $220 and a replacement costs $420. Budget is $500. Which fits?',
            'A repair costs $220 and a replacement costs $420. Budget is $500. Which should I choose?',
            'I pay $10 for three items at $2.40. Tax is 10%. How much change?',
            'I pay $10 for three items at $2.40. How much change?',
            'A shelf supports 20 kg. It already holds 12 kg. Each box weighs 0 kg. How many boxes can I add?',
            'A recorder has 2 hours left. Two recordings last 30 minutes and another takes the same time. How many minutes remain?',
            'Calculate __import__("os").system("echo nope")',
            'A repair does not cost $220 and a replacement costs $420. Budget is $500. Which fits?',
            'A repair costs $220 and a replacement costs $420 at half price. Budget is $500. Which fits?',
            'A shelf does not support 20 kg. It already holds 12 kg. Each box weighs 3 kg. How many whole boxes can I add?',
            'A recorder does not have 2 hours left. Two recordings last 30 minutes. How many minutes remain?',
            "I didn't pay $10 for three items costing $2.40. There is no tax. How much change?",
            'I pay $10 for three items costing $2.40 and returned one of them. There is no tax. How much change?',
            'A repair costs $220 and a replacement costs $420. My budget is now $500. I am giving you context.',
            'A recorder has 2 hours left. Two recordings each last 30 minutes. How many minutes does one recording take?',
            'A recorder has 2 hours left. Two recordings each last 30 minutes. How many minutes remain after the first recording?',
            'I pay $10 for three items costing $2.40. There is no tax. Change the subject.',
            'A recorder has 2 hours left. Two recordings each last 30 minutes. How many minutes remain before any recordings?',
            'I pay $10 for three items costing $2.40 per pair. There is no tax. How much change?',
            'I pay $10 for three items costing $2.40 and return one. There is no tax. How much change?',
            'I need at least 9 pens. Store A sells packs of 5 for $6 per item. Store B sells packs of 8 for $9. Packs cannot be split. Which has the lowest total cost?',
            'A shelf cannot support 20 kg. It already holds 12 kg. Each box weighs 3 kg. How many whole boxes can I add?',
        ]
        for text in bad:
            with self.subTest(text=text):
                self.assertIsNone(ask(text))

    def test_saved_facts_and_other_roles_do_not_supply_missing_operands(self):
        self.assertIsNone(word_math.solve([]))
        self.assertIsNone(word_math.solve([{'role':'assistant','content':TIME}]))
        self.assertIsNone(ask('How much change do I receive?'))


if __name__ == '__main__':
    unittest.main()
