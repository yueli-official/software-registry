# Software Registry

A community-editable catalog of third-party software and a small Python tool for preparing reproducible release plans. Each software has one JSON definition containing its description, usage instructions, FAQ, category, image sources and package rules. Packages for different systems and architectures stay in that definition.

The catalog focuses on external software. A consumer's own products can keep their independent release process without a catalog entry. Consumers can adopt individual definitions; catalog-wide adoption is not required.

The tools read upstream metadata and verify original downloads. Consumers publish those plans through their own adapters. Catalog definitions contain no consumer endpoints, credentials, storage locations or execution receipts.

## Run

Python 3.12 or later:

```sh
python -m pip install .
software-registry --catalog software validate
software-registry --catalog software list
software-registry --catalog software plan 7zip --output /path/to/private-state/release-plan.json
software-registry --catalog software verify --plan /path/to/private-state/release-plan.json --state-directory /path/to/private-state/originals --output /path/to/private-state/verified-plan.json
```

`plan` resolves exact source evidence and package metadata without publishing or downloading packages. `verify` checks original bytes against available source checksums and calculates SHA256. The output distinguishes an independent upstream checksum from a checksum calculated after a TLS download. A source requiring a detached signature needs a trusted signature verifier supplied through the Python API; verification stops when that verifier is absent.

The first package provides the version. Supplemental sources must resolve the same version; a missing platform or ambiguous attachment stops the plan. Stable and beta channels are explicit. Official-reference definitions contain no invented packages or versions.

PR validation runs offline schema and unit checks. The manually triggered discovery workflow emits a release plan using read-only GitHub permissions. Consumers decide whether a reviewed plan is published manually or automatically. No schedule is enabled by this repository.

## Files

- `software/<id>.json`: public identity, homepage/documentation, summary, description, usage instructions, FAQ, category, icon, screenshots and package rules.
- `categories.json`: readable category keys and names; software definitions refer to these keys.
- `schemas/software.schema.json`: strict manifest contract; unknown fields are rejected.
- `src/software_registry/`: catalog loading, bounded source discovery and byte verification.
- `tests/`: source ambiguity, platform/channel consistency, private field exclusion and verification failures.
- [CONTRIBUTING.md](CONTRIBUTING.md): first review and normal update workflow.
- [AGENTS.md](AGENTS.md): scope, privacy boundaries and instructions for coding agents.
- [Design](docs/design.md): public definitions and private consumer responsibilities.
- [Registry research](docs/registry-research.md): observations from mature registries and cited primary sources.
- [Change detection](docs/change-detection-research.md): update only changed fields or image bytes and preserve confirmed media references.

The registry tooling is licensed under [Apache-2.0](LICENSE). Listed software, artwork and third-party material retain their original licenses. An installation or source repository's license does not automatically authorize mirroring its binaries or artwork. Consumers enforce their own redistribution policy; this repository does not grant rights to the listed software.

Descriptions and instructions contain reusable software content. Images have separate original-source definitions and fixed hashes; screenshots also retain captions, permission evidence and provenance. A consumer resolves those images through its own media service and renders the description with its delivery references. Those runtime media references never enter the public catalog. Content-only synchronization does not require a package update.
