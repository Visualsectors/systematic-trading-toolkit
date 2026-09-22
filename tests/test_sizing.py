import unittest

from visualsectors_toolkit.sizing import SizingPick, size_by_portfolio_slots, size_by_stop_risk


class StopRiskSizingTests(unittest.TestCase):
    def test_reference_arithmetic(self):
        result = size_by_stop_risk(
            capital=100_000, risk_fraction=0.005, entry=100, stop=95,
            max_allocation_fraction=0.10,
        )
        self.assertEqual(result.shares, 100)
        self.assertEqual(result.notional, 10_000)
        self.assertEqual(result.planned_loss_at_stop, 500)
        self.assertEqual(result.binding_constraint, "both")

    def test_long_stop_must_be_below_entry(self):
        with self.assertRaisesRegex(ValueError, "long stop"):
            size_by_stop_risk(
                capital=100_000, risk_fraction=0.01, entry=100, stop=101,
                max_allocation_fraction=0.20,
            )


class PortfolioSlotSizingTests(unittest.TestCase):
    def test_one_pick_gets_one_slot_not_whole_portfolio(self):
        result = size_by_portfolio_slots(
            portfolio=100_000, intended_holdings=10,
            picks=(SizingPick("ONE", 100, 20),),
        )
        self.assertEqual(result.batch_budget, 10_000)
        self.assertEqual(result.positions[0].shares, 100)

    def test_missing_volatility_forces_equal_slots_for_batch(self):
        result = size_by_portfolio_slots(
            portfolio=100_000, intended_holdings=10,
            picks=(SizingPick("ONE", 100, 20), SizingPick("TWO", 50, None)),
        )
        self.assertEqual([item.target for item in result.positions], [10_000, 10_000])
        self.assertTrue(result.notes)

    def test_minimum_share_and_too_expensive_are_explicit(self):
        minimum = size_by_portfolio_slots(
            portfolio=1_000, intended_holdings=10,
            picks=(SizingPick("ONE", 150, 20), SizingPick("TWO", 50, 20)),
        )
        self.assertEqual(minimum.positions[0].tilt, "min_share")
        expensive = size_by_portfolio_slots(
            portfolio=1_000, intended_holdings=10,
            picks=(SizingPick("ONE", 1_500, 20),),
        )
        self.assertEqual(expensive.positions[0].tilt, "too_expensive")
        self.assertEqual(expensive.positions[0].shares, 0)


if __name__ == "__main__":
    unittest.main()
