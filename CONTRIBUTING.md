# Contributing

Add or edit `software/<id>.json` for external software; keep the filename and stable software identifier equal. Use a readable product identifier. Keep all declared platforms in the same file and retain the complete platform matrix during updates. A consumer's own products stay in its independent release process and do not require catalog entries.

Provide the official homepage, public release source, precise asset-selection rules and evidence of platform/architecture identity. Use public HTTPS URLs. A GitHub locator identifies the software's public upstream repository. Installation scripts, private feeds, consumer settings and credentials do not belong in a manifest.

List software with a genuinely free usable edition. A paid license with a temporary trial does not qualify. A product offering optional paid services or features can qualify when the selected edition is free. A reference is pending package integration, not a completed downloadable entry; source archives, store pages and project homepages are not installable release assets.

Maintain the summary, description, usage instructions and FAQ alongside source rules. Select a category from `categories.json`; edit that file when a new general category is needed. An official documentation link is optional. Keep guidance useful across consumers and versions, without a particular site's package availability, private image references or deployment instructions.

Retain the complete icon and screenshot definitions. Use original public URLs and SHA256, or a hashed inline SVG for an icon; an archive icon also names its exact archive entry. Label generated name marks accurately. Each screenshot includes a caption, source page, permission evidence, provenance and confirmed review. Empty `screenshots` explicitly removes previous screenshots on synchronization. Consumers reuse unchanged media by original hash and own upload/reference lifecycles.

Run `software-registry --catalog software validate` and `python -m unittest discover -s tests`. Open a PR with official identity, license/redistribution evidence and one successful discovery plan. Use `reference` for an official link with no configured package release; do not invent a release or imply that package review is complete.

First review checks identity, source ownership, stable/beta selection, package architecture and source-versus-installer selection. Changing the discovery source or attachment rules requires a new source review. An ordinary update with unchanged rules is discovered and checksum-verified by the tools; it does not need repeated manual inspection of every binary or every consumer page.

Release plans are generated execution outputs, not a second hand-maintained catalog. A consumer accepts a reviewed definition, freezes one plan, verifies it, and records its own publishing result. If a checksum changes for the same version, a package is missing, or source metadata becomes ambiguous, stop and report the mismatch rather than silently changing the platform matrix.

Contributor checks run on hosted runners without publishing secrets. Maintainers review changes to tooling and workflows before a trusted consumer executes them. Source definitions remain declarative; arbitrary shell or Python hooks are not accepted.
