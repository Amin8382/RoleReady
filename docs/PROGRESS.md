# Progress and experiment log

## 2026-11-08 M0 Clean rebuild authorised

- Confirmed English scope, the seven-question workflow and the three-member work split.
- Inspected both old frontend variants. The root app silently substituted sample analysis, transcripts and scores; PDF upload did not extract actual text.
- **Failure:** the old `npm ci` failed with `ERESOLVE`: ESLint 9 conflicted with the Next.js 14 ESLint package. No dependencies were forced into an incompatible installation.
- **Decision:** the user explicitly requested removal of all old application files and a clean RoleReady rebuild. Removed those tracked files on `feat/roleready-platform`; Git history is preserved.
- Imported prior model research, eight-case exploratory generation outputs and pinned dataset source metadata. Research results are not a production benchmark.
- **Access limitation:** GitHub API reports push permission but no admin permission. The settings page says the account cannot access repository options. Repository rename requires the owner.
- Environment available for validation: CPU only, approximately 9.7 GiB RAM. No Supabase, model API or DagsHub credentials were configured.
- Next milestone: reproducible data preparation, DVC stages, retrieval comparison and MLflow runs.
