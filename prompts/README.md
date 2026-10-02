# Grounded single-stock prompts

These files are a snapshot of the reviewed prompts that Visual Sectors' Alfred used on 1 October 2026. They are published as-is and are not kept in sync, so Alfred's live prompts may have changed since. They are published as documentation under [CC BY 4.0](../LICENSE-DOCS); application code generated from them remains covered by the repository's MIT license.

- `support-resistance-explainer-v1.md`
- `news-sentiment-explainer-v1.md`
- `narrative-cluster-v1.md`
- `options-reference-v1.md`

Each prompt consumes a closed evidence packet supplied by its host. It does not query a database, browse, fetch URLs, or execute SQL. A host is responsible for loading authoritative evidence through its own data connector, validating the prompt's structured output, and keeping credentials out of the model context.

The filenames carry the prompt contract version. Change the file and its pinned digest together; do not silently replace a released prompt in place.
