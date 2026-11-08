# RoleReady working rules

- Product scope is English interview preparation. Seven questions per session.
- Read `docs/PROGRESS.md`, `docs/DECISIONS.md` and the relevant source before changing code.
- Record every meaningful change, failed experiment and milestone in the progress log. Explain decisions and corrective action. Never fabricate results.
- Commit and push coherent milestones to the active branch. Use a pull request for integration. Do not squash away the milestone history unless the user requests it.
- Do not commit secrets, user CVs, recordings, private transcripts, model weights, `.venv`, `node_modules`, local databases or MLflow stores.
- Pin data revisions and verify checksums. Keep evaluation records out of training/retrieval.
- No silent fake scores, transcripts, invented candidate experience or successful fallback responses on service failure.
- For Next.js changes, read the matching installed documentation in `node_modules/next/dist/docs` when available. Otherwise use official version-matched documentation.
- Run relevant Python tests, data checks, TypeScript checks and production build before marking the milestone complete. Track missing external credentials as unverified integrations.
- Store generated repository artifacts in Git or DVC, not a second document store.
