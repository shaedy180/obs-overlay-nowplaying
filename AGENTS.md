# Coding agent instructions

Read this root `AGENTS.md` before changing the repository. This is the sole agent instruction document; `README.md` is the sole project manual. Preserve legally required licenses and third-party attribution.

## Repository and Git workflow

Windows OBS media-session overlay, local HTTP server and desktop tray application. Preserve loopback binding, settings schema migration, per-user data, checksum-verified updates with executable rollback, single-instance behavior, GSMTC selection and existing diagnostics/tests.

The protected default branch is `main`. The only other permanent branch is `working-branch`. Fetch before work and check for an existing PR from `working-branch` to `main`; continue or coordinate that PR rather than competing with it. Synchronize from `main` with a fast-forward before coding. Commit and push exclusively to `working-branch`, and open PRs exclusively into `main`. Never create additional branches, push directly to `main`, force-push, delete `working-branch`, bypass protections or required approvals. Disable dependency bots that require extra branches. Use tags for versions and recovery references. Merge only after required CI and applicable reviews pass, using a merge commit; then fast-forward and push `working-branch` to the merged `main` without a force push. Keep automatic branch deletion disabled.

## Quality, compatibility and verification

Follow existing conventions and keep changes small and maintainable. Preserve public APIs, authentication, authorization, storage formats and integrations. Avoid unnecessary dependencies, abstractions and duplicate implementations. Establish actual consumers before removing obsolete code; missing search results alone are insufficient. Preserve useful regression tests. Run appropriate builds, tests, security checks and integration/migration validation before submitting; fix introduced failures without weakening gates. Do not claim successful CI or deployment without evidence for the exact revision. Stage only intentional paths and preserve unrelated user changes.

## Releases, production and security

Use the canonical workflows documented in the README. Publish immutable release artifacts tied to Git commits. Production services use the existing central deployment controller, health and revision checks, backups and verified rollback. Plugins and desktop/mod projects use their supported installation mechanisms. Never make uncontrolled production changes, restart services casually, alter game/economy behavior as cleanup, or delete databases, volumes, migrations, user data, backups or session state. Never commit credentials or expose sensitive values in logs or reports. Use least privilege and preserve security controls and external contracts.

## Documentation and completion

Keep current architecture, runtime requirements, configuration, testing, release/deployment and recovery information in `README.md`, linking this file. Update this file when development rules change. Consolidate valid repository-specific instructions here; do not create nested or competing instruction files, extra Markdown plans, status reports or manuals. Keep audit evidence outside the source tree.

Done means implemented changes, appropriate tests and CI passing, production compatibility verified where relevant, both documents current, PR merged, `working-branch` fast-forwarded to `main`, effective protection verified and exactly these two branches present. Report any unmet condition accurately.
