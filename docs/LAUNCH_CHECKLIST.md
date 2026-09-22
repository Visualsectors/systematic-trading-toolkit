# Visual Sectors launch checklist

The code can be tested now. The following owner inputs are required before a public launch or live API connection.

## Required from Visual Sectors

- [ ] Confirm the public repository name and URL: `Visualsectors/systematic-trading-toolkit`.
- [ ] Confirm Apache-2.0 for public code and documentation after legal review.
- [ ] Provide the public security/contact address and replace the generic website direction in `SECURITY.md`.
- [ ] Approve the investment-research disclaimer for target launch jurisdictions.
- [ ] Provide the API base URL, authentication flow, free quota, paid quota, retry limits, delay, supported market coverage, and uptime/support expectations.
- [ ] Provide a field-by-field live API dictionary, units, timestamps, adjustment policy, and missing-value behavior.
- [ ] Obtain written confirmation of rights for display, caching, derived analysis, LLM use, adviser use, managed-account use, and prohibition of raw-value redistribution.
- [ ] Decide whether end users may persist derived outputs and for how long.
- [ ] Supply a redistributable or fully synthetic API example payload; never commit licensed production values.
- [ ] Confirm which proprietary indicators are exposed as values and documentation while their generation remains private.
- [ ] Choose the public support route, contribution policy, and vulnerability-response SLA.

## Repository controls

- [ ] Create the repository as private first, enable secret scanning and push protection, then review before making it public.
- [ ] Require pull requests, passing CI, review, and no unresolved conversations on the default branch.
- [ ] Add CODEOWNERS for financial logic, provider integrations, and security-sensitive files.
- [ ] Pin CI actions by immutable commit and schedule dependency/security review.
- [ ] Publish signed/tagged releases with a changelog and retained QA evidence.
- [ ] Run a clean-room scan to confirm no private source, secrets, customer data, licensed samples, or proprietary generation logic entered the public history.

## Acceptance evidence

- [ ] Clean Python 3.12 and 3.13 installs pass unit tests and `compileall`.
- [ ] The offline demo generates all six outcomes without credentials or network access.
- [ ] Re-running unchanged monitoring state emits no duplicate events.
- [ ] Provider failure retains active risks and emits no all-clear.
- [ ] A point-in-time dataset replay produces byte-equivalent JSON output.
- [ ] Legal, security, and a domain reviewer approve the release candidate.

The Visual Sectors API adapter should begin only after the contract and data-rights items above are complete. The deterministic core does not depend on that adapter, so public code review can proceed in parallel.
