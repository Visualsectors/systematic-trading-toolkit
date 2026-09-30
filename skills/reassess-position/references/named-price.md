# Named entry, cost basis or strike

`vstoolkit measure --ticker AAPL --price 200 --kind strike` uses latest eligible dated **served level prices**, not generated targets or zone-edge estimates. Distances are signed (above positive, below negative): level minus named price, divided by named price for percent and ATR14 for ATR units. A strike's extra distance is strike minus latest close divided by ATR14.

Nearest above and below are independent of the provider's Support/Resistance label. Exactly-at-price levels are separate. Preserve date, side, type and evidence ID. Missing ATR, level or historical rate is null; do not impute it. Rates use “held on N% of past tests,” with the provider's hindsight/recomputation limitations. A missing rate does not mean zero.

Never select an exit, strike or holding action. End exactly with `closing` from the command. State freshness and coverage gaps before that sentence. A monitor breach refers to the saved original rule, not a newly recalculated boundary.
