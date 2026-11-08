# Contributing to RoleReady

Project contributors:
- **Mohamed Amin Guesmi** — AI, datasets, retrieval, Qwen generation, LoRA comparison and question quality evaluation
- **Oussema Ferchichi** — FastAPI, sessions, security and Prometheus rubric scoring
- **Khaled Briki** — Next.js, microphone workflow, Whisper/Kokoro integrations, reporting and PDF output

Use one repository, small branches (feat/amin-*, feat/oussema-*, feat/khaled-*), descriptive commit messages, and reviewed pull requests. Do not push directly to main for features. GitHub accounts for Oussema and Khaled have not been confirmed, so code-owner enforcement should only be configured after confirming their usernames.

Run before requesting review:
- Frontend: npm install; npm run typecheck; npm run build
- Backend: cd backend; pip install -r requirements-dev.txt; python -m pytest -q
- AI: cd ai; pip install -e ".[test]"; python -m pytest -q

Never commit personal resumes, recordings, model/API keys, .env files, large model weights, raw datasets with unverified licenses, or generated reports containing candidate details. Record source URLs, licenses, snapshot hashes and train/test separation for every external dataset. Always identify whether outputs are baseline, demo, or real model results. Review docs/TEAM_IMPLEMENTATION.md and the project plan for scope.

CI checks the three components independently. A passing unit test does not imply model-quality validation or secure production readiness.
