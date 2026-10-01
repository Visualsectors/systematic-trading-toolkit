# Supported grammar and defaults

| Phrase | Executed condition |
| --- | --- |
| oversold / overbought | RSI14 <= 30 / >= 70; disclosed defaults |
| above the 200 / above SMA200 | price > SMA200 |
| golden cross state | SMA50 > SMA200; not a cross event |
| uptrend | price > SMA50 > SMA200; disclosed structural default |
| price above $10 | price > 10; user number required |
| average dollar volume above $5m | 20-session average dollar volume > 5,000,000 |
| liquid | average dollar volume >= 5,000,000; disclosed dollar default, not share-volume |
| low P/E | 0 < P/E <= 15; disclosed heuristic, no valuation conclusion |
| pullback to the 20 within 0.5 ATR | abs(price - SMA20)/ATR14 <= 0.5; user distance required |
| at support | nearest eligible served support-band edge <= 1.5 ATR |

Join with “and” or “with.” Every leftover condition refuses the whole request. No model-generated code, eval, SQL, guessed periods or silent substitutes. OR/NOT, alternate RSI periods, explicit alternate RSI/P-E cutoffs and arbitrary comparator grammars are not implemented; clarify or use the Python API. Named presets keep their existing, different thresholds.

Williams %R(14) = fast %K(14) - 100 on identical high/low/close data with nonzero range. Thus %R < -80 is exactly fast %K < 20. Slow %K(14,3) equals fast %D(14,1,3) with matching SMA smoothing. Their fields are not wired into this grammar; they are not interchangeable with RSI. Sources: [Williams %R](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/williams-r), [Stochastic](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/stochastic-oscillator-fast-slow-and-full).

The derived 190-phrase vocabulary records ambiguity, requirements and source URLs, not executable capability. Current snapshot fields lack share-volume RVOL, float, IV rank, market caps, crossing-event histories and many window-specific values. Even dataset.v2 history does not automatically wire those phrases into the compiler. Request a measurable field/period/threshold; never invent one to make a request pass.
