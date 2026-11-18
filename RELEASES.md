# Automated publication

`publish-release.yml` publishes a prepared, qualified release using npm Trusted
Publishing. It accepts `release_tag` and `dry_run` inputs. Manual runs default to
verification only; the private upstream-release workflow dispatches it with
publication enabled after compatibility and platform checks pass. Publishing a
release manually on GitHub also triggers the workflow.

The workflow reads `release.json` from the exact target commit, checks all five
release assets, verifies the npm/ZIP inventories and provenance, and downloads
published npm bytes before advancing catalogs. Already published matching versions
are reused. Changed assets, conflicting npm integrity, unqualified metadata and
backwards tag updates fail rather than overwrite an existing release.

The catalog job promotes the prepared PR through the existing merge rules,
then the parent workflow waits for `verify-public-install.yml` and
`publish-registry.yml` as reusable workflows at that exact merged commit. Registry
retries reuse a matching active version; conflicting or retired entries are not
overwritten or reactivated. A merge
blocked by branch protection remains reviewable and can be retried with the same
tag. Never use an admin bypass merely to finish publication.

Configure an npm GitHub Actions Trusted Publisher for:

- Organization: `zeroclaw-labs`
- Repository: `zeroclaw-mcp-distribution`
- Workflow: `publish-release.yml`
- Environment: empty
- Allowed actions: **npm publish** and **npm dist-tag**

No npm token is stored in GitHub. The workflow uses Node 24 and npm 11.21.0 for
OIDC publishing and dist-tag operations. npm requires the first successful publish
within two days of creating the trusted-publisher entry. See the [npm setup and
permissions documentation](https://docs.npmjs.com/trusted-publishers/).

The existing alpha.6 draft can bootstrap this connection: run the workflow first
with `release_tag=v0.1.0-alpha.6`, `dry_run=true`; then run the same tag with
`dry_run=false`. This uses the already reviewed package without rebuilding it.
Existing release assets and older npm versions are retained.

The source repository's GitHub App stages new draft releases and catalog PRs and
dispatches this workflow after each newly qualified stable ZeroClaw release. That
App needs Contents, Pull requests and Actions write permissions on this repository.
Its private key stays in the private source repository; it is not stored here.
