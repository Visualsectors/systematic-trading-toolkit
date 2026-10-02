# Plan output fields

`status=ready` means dated geometry is available, not that a trade is recommended or that its reward exceeds its risk. If the unrounded reward-to-reassessment ratio is below 1R, the plan carries `reward_risk_warning=reward_below_risk` and a human-readable warning in `notes`. At or above 1R, or without a calculable ratio, the warning is null. Long and short scenarios follow the same rule.

`width_atr` and `stop_distance_atr` are rounded to two decimal places in JSON output. JSON numbers do not retain trailing zeros: `0.50` appears as `0.5`. The internal geometry and risk calculations retain their original precision. Markdown already formats these values with two decimal places.

A zone's `member_count` counts distinct exact price levels, not approach rows. Two approaches or two families at the same exact price count once. Unrounded distinct prices remain distinct. All observations are retained in `members`, and their approach/family evidence and conflict checks remain unchanged; `len(members)` gives the source-observation count.

These are offline regression fixes for Rustam's review of main `f740e0d`. No live account, API call, merge or deployment is part of this change.
