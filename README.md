# RoleReady

English interview preparation from a CV and a target job description: evidence-based preparation priorities, seven questions, voice practice, feedback and a PDF preparation sheet.

Team: Mohamed Amin Guesmi (AI/data), Oussema Ferchichi (API/scoring), Khaled Briki (web/voice).

## Clean rebuild

The team approved replacing the previous application on 8 November 2026. This repository is the record of the rebuild. The old application is recoverable from Git history. No generated scores are substituted when a model fails.

| Location | Purpose |
| --- | --- |
| `apps/web` | Next.js and TypeScript interface |
| `services/api/src/roleready` | FastAPI service, session storage and model adapters |
| `configs` | Pinned dataset sources and model configuration |
| `data` | DVC-managed downloads and prepared records; no candidate CVs in Git |
| `reports` | Reproducible public-data metrics and experiment summaries |
| `tests` | Data, API, isolation and model-contract tests |
| `docs` | Decisions, progress, failures, setup and team responsibilities |

Implementation and verified commands are recorded as milestones in [the progress log](docs/PROGRESS.md). Model research and its limitations are preserved in [the research notes](docs/research/README.md).

## Working agreement

Every meaningful change is committed. Each milestone records what changed, what was tested, what failed and what remains. Experiments log parameters, dataset/model versions, metrics and outcomes to MLflow. Git contains code and reports; DVC tracks larger data; credentials and candidate content stay out of both public Git and experiment logs.

The GitHub account can push code but cannot rename this repository. The owner must rename `interview_wingman` to `roleready` in repository settings. No new owner or duplicate repository is created automatically.
