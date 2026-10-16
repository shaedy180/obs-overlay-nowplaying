# Coding agent instructions

Read this root `AGENTS.md` before changing the repository. This is the sole agent instruction document; `README.md` is the sole project manual. Preserve legally required licenses and third-party attribution.

## Repository and Git workflow

Windows OBS media-session overlay, local HTTP server and desktop tray application. Preserve loopback binding, settings schema migration, per-user data, checksum-verified updates with executable rollback, single-instance behavior, GSMTC selection and existing diagnostics/tests.

The protected default branch is `main`. The only other permanent branch is `working-branch`. Fetch before work and check for an existing PR from `working-branch` to `main`; continue or coordinate that PR rather than competing with it. Synchronize from `main` with a fast-forward before coding. Commit and push exclusively to `working-branch`, and open PRs exclusively into `main`. Never create additional branches, push directly to `main`, force-push, delete `working-branch`, bypass protections or required approvals. Disable dependency bots that require extra branches. Use tags for versions and recovery references. Merge only after required CI and applicable reviews pass, using a merge commit; then fast-forward and push `working-branch` to the merged `main` without a force push. Keep automatic branch deletion disabled.

### Required CI, merge and release sequence

1. Read this file and the repository-specific build, release and recovery instructions in `README.md`. Fetch first, preserve unrelated work, and continue an existing `working-branch` to `main` PR when one exists. Follow the branch and review rules above.
2. Commit and push changes to `working-branch`, then open or update its PR into `main`. Open a draft PR early for automatic validation. A working-branch push without a PR starts no CI; use the existing manual workflow only when a pre-PR check is needed.
3. Wait for the complete PR validation and every required check, including **CI provenance**, on the latest exact PR head. A new PR update cancels obsolete PR runs. Fix failures; never remove tests, skip required checks, bypass protection or add duplicate working-branch push CI to obtain a green result.
4. Keep the PR current with `main` and merge only after all required checks and applicable reviews pass. Use a merge commit. On `main`, the small **CI provenance** gate must verify the latest successful PR run, its current unexpired receipt, and identical tested/actual Git trees and both merge parents. The full application suite is deliberately not repeated after merge; do not reintroduce that duplicate run.
5. Wait for the successful main gate and any repository-specific release artifact/image jobs on the exact merged SHA. A successful merge or PR alone is not proof that a release was published or deployed. Missing, failed, stale or mismatched evidence blocks publication. Never bypass the gate: update and revalidate the PR before merging; for an expired receipt, rerun the complete original PR workflow and then the main gate.
6. Production deployment is a separate explicitly authorized operation. Follow this repository's canonical deploy workflow, protected environment, immutable full SHA, central controller, health/revision checks and recovery procedure. A commit, PR or merge instruction by itself does not authorize a production rollout. Plugins, mods, desktop applications and other non-service repositories follow their documented packaging/installation process instead of a VPS deployment. Keep tag/release checks and safeguards intact.
7. After merge, fast-forward and push `working-branch` to the merged `main` without force. This synchronization starts no additional CI. Confirm both branches, required checks and relevant release results, and report any remaining failure or pending authorization accurately.

## Quality, compatibility and verification

Follow existing conventions and keep changes small and maintainable. Preserve public APIs, authentication, authorization, storage formats and integrations. Avoid unnecessary dependencies, abstractions and duplicate implementations. Establish actual consumers before removing obsolete code; missing search results alone are insufficient. Preserve useful regression tests. Run appropriate builds, tests, security checks and integration/migration validation before submitting; fix introduced failures without weakening gates. Do not claim successful CI or deployment without evidence for the exact revision. Stage only intentional paths and preserve unrelated user changes.

## Releases, production and security

Use the canonical workflows documented in the README. Publish immutable release artifacts tied to Git commits. Production services use the existing central deployment controller, health and revision checks, backups and verified rollback. Plugins and desktop/mod projects use their supported installation mechanisms. Never make uncontrolled production changes, restart services casually, alter game/economy behavior as cleanup, or delete databases, volumes, migrations, user data, backups or session state. Never commit credentials or expose sensitive values in logs or reports. Use least privilege and preserve security controls and external contracts.

## Documentation and completion

Keep current architecture, runtime requirements, configuration, testing, release/deployment and recovery information in `README.md`, linking this file. Update this file when development rules change. Consolidate valid repository-specific instructions here; do not create nested or competing instruction files, extra Markdown plans, status reports or manuals. Keep audit evidence outside the source tree.

Done means implemented changes, appropriate tests and CI passing, production compatibility verified where relevant, both documents current, PR merged, `working-branch` fast-forwarded to `main`, effective protection verified and exactly these two branches present. Report any unmet condition accurately.
