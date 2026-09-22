# Contributing

Use Python 3.12 or newer. Keep the core dependency-free, deterministic, and
usable without credentials. New providers may add optional dependencies, but a
missing optional dependency must not break fixture mode.

Before opening a change:

```bash
python -m unittest discover -s tests -v
python -m compileall -q src tests
python -m visualsectors_toolkit demo --output toolkit-report.md
```

Requirements for changes:

- Add reference tests for financial arithmetic and temporal behavior.
- Preserve missing values as missing; never coerce them to zero or neutral.
- Pass decision time, data and identifiers as inputs. Core logic must not read
  a clock, environment, network, filesystem or random source.
- Call a historical rate a historical rate—not a probability or forecast.
- Do not commit credentials, licensed market data, generated reports, or
  proprietary indicator-generation methods.
- Document provider fields, units, timing and redistribution rights.

By contributing, you agree that your contribution is licensed under the
Apache License 2.0 included in this repository.
