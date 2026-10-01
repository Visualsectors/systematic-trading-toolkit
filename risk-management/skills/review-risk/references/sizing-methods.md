# Sizing methods

The toolkit has two sizing methods, both defined in the toolkit's sizing.py. They answer different questions and are never blended. Run the command; never recompute a size by hand.

## The user owns every input

- Run a method only when the user has supplied every input it needs. If one is missing, name it and stop.
- Never propose, default, round or correct capital, a risk fraction, an allocation cap, an entry, an invalidation price or a holdings count. Never infer capital from a quantity or from a position's value.
- If the user chooses the plan's `invalidation_price` as their `--stop`, record that it was their choice.
- The CLI asks for confirmation when the risk fraction exceeds 0.05 or the allocation cap exceeds 0.50. Pass `--yes` only after the user confirms that scenario in their own words.
- Report the method name, every input, every output field and the warnings. The result is arithmetic on the user's inputs, not a judgement that the size suits them.

## `stop_risk/v1`

How many whole shares fit a planned loss and an allocation cap?

`vstoolkit size-stop --capital <c> --risk-fraction <r> --entry <e> --stop <s> --max-allocation <a> --side <long-or-short>`

| Input | Rule |
| --- | --- |
| `--capital` | Portfolio capital, greater than zero. |
| `--risk-fraction` | Fraction of capital at risk, greater than 0 and at most 1; `0.01` means 1%. |
| `--entry` | Planned entry price per share, greater than zero. |
| `--stop` | The scenario invalidation price per share: below entry for a long, above entry for a short. |
| `--max-allocation` | Maximum fraction of capital in the position, greater than 0 and at most 1. |
| `--side` | `long` (the default) or `short`. |

The risk budget is capital × risk fraction, and the allocation cap is capital × max allocation. Risk-limited shares are the risk budget divided by the per-share distance between entry and invalidation, rounded down. Allocation-limited shares are the allocation cap divided by entry, rounded down. The size is the smaller of the two, and the command refuses when the inputs cannot fund one share.

Output: `shares`, `entry`, `stop`, `notional`, `planned_loss_at_stop`, `risk_budget`, `allocation_cap`, `risk_limited_shares`, `allocation_limited_shares` and `binding_constraint` (`risk_budget`, `allocation_cap` or `both`). Money is rounded to the cent. Repeat its three warnings: the planned loss excludes commissions, slippage, taxes and borrow costs; a gap through the invalidation price can lose more than planned; the result is arithmetic, not a suitability assessment or an order.

`vstoolkit plan` also runs this method, taking the entry band's near edge as entry and its `invalidation_price` as the invalidation. When the user passes no `--capital`, `--risk-fraction` or `--max-allocation`, it uses example defaults of 100000, 0.005 and 0.10. Those are not the user's inputs: do not report that size unless the user chose all three.

## `portfolio_slots/v1`

How does a batch of picks share the portfolio slots it occupies?

`vstoolkit size-portfolio --tickers <A,B> --portfolio <p> --intended-holdings <n>`, with `--data <dataset.json>` or `--offline` as for the other commands.

| Input | Rule |
| --- | --- |
| `--tickers` | Comma-separated, unique, and no more than the intended holdings. |
| `--portfolio` | Portfolio capital, greater than zero. |
| `--intended-holdings` | A positive whole number of names the portfolio will hold. |
| Close and volatility | Read from the data source for each ticker (`volatility_20d_pct`). |

One slot is the portfolio divided by intended holdings, to the cent, and the batch budget is the number of picks times the slot. When every priced pick has a volatility, priced picks share their slots by normalized inverse volatility (`tilt: tilted`). If any priced pick lacks one, every priced pick gets an equal slot (`equal`) and a note names the missing ones. Shares round down. A pick with no close is `no_price`, and its slot stays unallocated. A target below one share buys one (`min_share`) unless one share costs more than the whole batch budget (`too_expensive`). A second pass then trims other picks, or drops a minimum, so deployment never exceeds the batch budget. Leftover is reported as `unallocated`, never redeployed.

Output: `slot`, `batch_budget`, and per position `allocation_amount`, `shares`, `notional`, `tilt`, `batch_share`, `portfolio_share` and `note`, plus `gross_long`, `gross_short`, `net`, `deployed`, `unallocated`, `deployed_fraction_of_portfolio` and `notes`. The command sizes every pick as long. The batch budget is the binding limit. Volatility is backward-looking and depends on the provider's definition.

## Never blend

Do not feed one method's output into the other, average them, or present one as a check on the other. If the user asks for both, run both, label each by its method name, and keep them separate.
