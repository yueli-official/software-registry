# Agent instructions

## Scope and ownership

- Maintain a public registry of external software and generic discovery/verification tools. A consumer's own products stay in its independent release process.
- Keep one `software/<id>.json` per product, including all declared platforms and architectures. Adopt or improve entries individually; complete catalog migration is not a prerequisite.
- Read [CONTRIBUTING.md](CONTRIBUTING.md) for manifest changes and [docs/design.md](docs/design.md) for tooling or consumer-boundary changes. Schema and CLI help own field and command details.

## Public data and privacy

- Public files own external software identity, descriptions, usage instructions, FAQ, documentation links, category names, icon/screenshot sources and declarative package rules. Keep the complete entry together and preserve original image hashes, captions, permissions and provenance.
- Keep consumer identities, site domains, internal repository names, infrastructure, deployment configuration, credentials, account data, private software IDs, consumer-specific editorial notes and machine paths outside this repository. Examples, tests and agent instructions obey the same boundary; use neutral fixtures.
- Keep release plans, downloaded originals, execution receipts, traces and audit reports in an explicit private task/state directory. Select that directory before running a command; never upload the surrounding task directory as source.
- Build exports from an explicit source-file allowlist. Inspect every included file, archive member and relevant Git history for secrets, internal references and unrelated data before publication. An ignore rule or successful secret scan alone does not establish privacy.
- Use credentials only through the consumer's private configuration or transient environment. Redact diagnostics and report error categories; never print tokens, signed URLs or complete environment dumps.
- Keep private collaboration profiles and local orchestration contracts in their private environment. Read an operator-provided contract when doing local cross-repository integration; do not copy its content or location into public files.

## Source review and execution

- Definitions remain declarative. Do not execute upstream installation hooks or accept arbitrary shell/Python hooks in manifests.
- First review verifies official identity, source ownership, channel selection and the declared package matrix. Review changed source or attachment rules once; ordinary updates with unchanged rules use automated discovery and byte checks.
- Stop on ambiguous assets, missing slots, inconsistent platform versions, changed checksums for a fixed release, or unavailable required signature verification. Preserve evidence and report the specific mismatch.
- Public tooling reads upstream data and verifies downloads. Consumer enrollment, redistribution decisions, publishing APIs and schedules belong to private adapters. Preview is the default for consumer integration; production writes require the user's release authorization.
- Image definitions use original public sources or hashed inline SVGs. Consumers resolve them through their media service, reuse confirmed receipts and synchronize references when images change or are removed. Asset IDs, media delivery URLs and upload outcomes stay private; do not insert them into catalog Markdown.
- Compare desired managed fields with live values before writing. Track text, original image bytes, screenshot presentation and package rules separately; a changed overall definition must not cause unrelated updates. Reuse confirmed media by original SHA256; caption, order or source-URL changes alone do not require an upload.
- Save a private baseline only after confirmed success. Preserve online editorial changes and stop conflicting writes. Missing receipts mean missing evidence: reconcile existing media before uploading replacements. Unchanged runs must not rewrite business data or unchanged receipts; unchanged package rules still require upstream version discovery.
- PR checks run with read-only permissions and no publishing credentials. Changes to tooling/workflows need maintainer review before trusted consumers execute them.

## Validation and task artifacts

- Run checks matching the change: schema validation for manifests, focused tests for affected tooling, and a representative real discovery/verification probe for source or consumer integration. Documentation-only edits need content/privacy review, not redundant full suites.
- Distinguish discovery, byte verification, publishing preview and actual production publication in reports. Passing one layer does not prove another; include the software/version and tested slots for live probes.
- Put temporary dependencies and build/test output in an ignored task directory or operator-specified external task root, outside system temporary folders. Run background helpers without visible windows where supported.
- At handoff, stop owned helpers and remove only verified, regenerable task artifacts. Preserve source changes, original downloads, unresolved receipts and delivery evidence; report what was cleaned and retained.
- Keep `flightdeck/` local and ignored if used. Never commit private work records.

## Git and release authorization

- Creating a repository, implementing changes or testing authorizes local edits only. Obtain explicit authorization separately for commit and push, scoped to this repository and branch; a consumer repository's authorization does not transfer here.
- Remote creation, PRs, tags, Releases and production publishing also need explicit authorization. When authorization is absent, leave changes uncommitted and report their state without blocking unrelated local work.
- Select the code license with the maintainer before public distribution. Listed software retains its own license; a public source does not itself grant binary or artwork redistribution rights.
