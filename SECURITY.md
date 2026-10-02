# Security policy

Please use [GitHub's private vulnerability report](https://github.com/Visualsectors/systematic-trading-toolkit/security/advisories/new)
to report suspected vulnerabilities. Do not open a public issue containing credentials, customer
data, exploit details, or licensed market-data samples.

The fixture quickstart is offline. API keys belong in the ignored `.env` file,
an environment variable, or the user's secret manager. Never put a key in an
LLM prompt, command-line argument, committed file, report, or log. This project
does not connect to brokers or place orders.

This is an experimental beta. Security fixes target the current `main` revision;
there is no promise of long-term support for older snapshots.
