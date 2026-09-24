# Security policy

Please report suspected vulnerabilities privately to the security contact on
visualsectors.com. Do not open a public issue containing credentials, customer
data, exploit details, or licensed market-data samples.

The fixture quickstart is offline. API keys belong in the ignored `.env` file,
an environment variable, or the user's secret manager. Never put a key in an
LLM prompt, command-line argument, committed file, report, or log. This project
does not connect to brokers or place orders.

Supported security fixes target the latest released minor version.
