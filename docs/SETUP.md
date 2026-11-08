# Setup

## 1. Local workspace

Follow the root README installation and data commands. Use Python 3.12 and Node 22. Keep the API and web environment files separate and set matching local tokens. The Next.js server connects to the Python API at `ROLEREADY_API_URL`.

For Windows, use PowerShell for the app/data commands. GPU serving tools are best run separately on a compatible Linux GPU host or WSL environment. No paid service is required for the retrieval-only exploration mode.

## 2. Full question and scoring workflow

Connect **two** OpenAI-compatible chat-completion endpoints. They can be self-hosted or a chosen inference provider. Base URLs include `/v1`; do not append `/chat/completions` yourself.

```dotenv
ROLEREADY_QUESTION_MODE=llm
ROLEREADY_GENERATION_URL=http://127.0.0.1:8002/v1
ROLEREADY_GENERATION_MODEL=Qwen/Qwen3.5-4B
ROLEREADY_EVALUATION_URL=http://127.0.0.1:8003/v1
ROLEREADY_EVALUATION_MODEL=prometheus-eval/prometheus-7b-v2.0
```

Set the corresponding `_KEY` variables when the endpoint requires a token. Restart the API after changing settings. `/v1/capabilities` indicates configuration, not a verified model connection.

For a compatible GPU host with vLLM installed in **its own environment**, these are example serving commands. GPU memory, compatible CUDA/vLLM versions and context limits must be validated on the team's hardware; they have not been run in this CPU-only workspace.

```bash
vllm serve Qwen/Qwen3.5-4B --revision 851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a --host 127.0.0.1 --port 8002 --max-model-len 16384
vllm serve prometheus-eval/prometheus-7b-v2.0 --revision 66ffb1fc20beebfb60a3964a957d9011723116c5 --host 127.0.0.1 --port 8003 --max-model-len 8192
```

Run each command on suitable separate resources or allocate memory explicitly. The server must apply the model's chat template. Generation requests ask for JSON and disable Qwen thinking; the evaluator uses the Prometheus `[RESULT] 1–5` contract. If an inference provider does not support these options, adapt it deliberately and rerun contract/live tests. Never replace a failed request with sample output.

Primary documentation: [Qwen model card](https://huggingface.co/Qwen/Qwen3.5-4B), [Prometheus model card](https://huggingface.co/prometheus-eval/prometheus-7b-v2.0), [vLLM server documentation](https://docs.vllm.ai/en/latest/serving/openai_compatible_server/).

## 3. Voice

```bash
uv sync --frozen --extra dev --extra retrieval --extra voice
```

Set `ROLEREADY_VOICE_ENABLED=true` in `.env`, then restart the API. First use downloads the pinned Kokoro/Whisper model files. Kokoro uses the `af_heart` voice. The English spaCy model is pinned in the lockfile. PyAV is constrained below 19 because faster-whisper 1.2.1 calls an argument removed in PyAV 19.

Microphone recording requires HTTPS or localhost and user permission. Text answers remain available. Raw audio is not kept in session storage. The original transcript is saved alongside the corrected submitted answer. Check technical terms before grading.

## 4. Supabase

1. Create or select the team's Supabase project. Apply `supabase/migrations/202611080001_sessions.sql` once in its SQL editor/migration workflow.
2. Enable email/password authentication and configure the site URL and confirmation email settings.
3. Set API `.env`: `ROLEREADY_AUTH_MODE=supabase`, `ROLEREADY_SUPABASE_URL`, `ROLEREADY_SUPABASE_ANON_KEY`.
4. Set web `.env.local`: `ROLEREADY_AUTH_MODE=supabase`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
5. For a hosted environment, set `ROLEREADY_ENVIRONMENT=production` on both services and `ROLEREADY_WEB_ORIGIN=https://YOUR_APP_DOMAIN` on the web service. Keep the API behind the same-origin web proxy and configure HTTPS, request limits and rate limits at the hosting layer.
6. Verify with two different accounts that listing, reading, editing and deleting another user's session is denied. Live RLS verification is still required before deployment.

Use the publishable/anon key; no service-role secret is required or accepted in the browser. Raw CV/audio uploads are not retained, so the first release does not need a public storage bucket. Saved session content lives in private Postgres rows.

## 5. MLflow and DagsHub

Local runs use `.state/mlflow.db` and `.state/mlflow-artifacts`. The tracking client creates an experiment named `roleready`, records code revision/dirty state, dataset/model revisions, metrics and failures. API runs record only timings, outcome and model identifiers; CVs and answers are excluded.

To connect DagsHub, first create or connect a DagsHub repository for the team's GitHub project. Configure environment variables in the shell running the pipeline (the pipeline does not automatically load `.env`):

```powershell
$env:MLFLOW_TRACKING_URI = "https://dagshub.com/OWNER/REPOSITORY.mlflow"
$env:MLFLOW_TRACKING_USERNAME = "YOUR_USERNAME"
# Set MLFLOW_TRACKING_PASSWORD securely to a DagsHub token; do not paste it into Git.
uv run --no-sync roleready check-dagshub
uv run --no-sync roleready evaluate-retrieval
```

Use `export NAME=value` in Bash instead of PowerShell's `$env:NAME`. Existing local experiments are not automatically migrated; the next run goes to the configured tracker. [Official DagsHub MLflow instructions](https://dagshub.com/docs/integration_guide/mlflow_tracking/).

DVC remote storage is separate from MLflow. Once the DagsHub repository exists:

```bash
uv run --no-sync dvc remote add -d dagshub https://dagshub.com/OWNER/REPOSITORY.dvc
uv run --no-sync dvc remote modify dagshub --local auth basic
uv run --no-sync dvc remote modify dagshub --local user YOUR_USERNAME
# Set the remote password/token using DagsHub's documented local credential method.
uv run --no-sync dvc push
```

Keep credentials in `.dvc/config.local` or a secret manager. Verify a fresh clone with `dvc pull` before claiming remote reproducibility. The public source manifests can reproduce the data with `dvc repro` even before a remote is connected. [Official DagsHub DVC instructions](https://dagshub.com/docs/integration_guide/dvc/).

## 6. GitHub workflow

Create a focused branch, make the change, update `docs/PROGRESS.md`, run relevant checks, and commit the code plus small reports. Record failures and the corrective action. Open a PR and keep milestone commits when merging. GitHub Actions checks Python contracts, TypeScript, a production build and two browser workflows.

The working repository is **[Amin8382/RoleReady](https://github.com/Amin8382/RoleReady)**. It already has the correct name, and the user has administrator access. Use this repository for all branches, pull requests and any DagsHub mirror.

```bash
git remote set-url origin https://github.com/Amin8382/RoleReady.git
git remote -v
```

The GitHub app installation for **Amin8382** is now connected, and creation of `feat/import-verified-platform` succeeded. The earlier HTTP 403 was caused by the app being installed only under another account; user administrator rights alone did not grant the app repository access.

Use the branch-specific clone command in the README while the import is under review. Two newer draft PRs also exist; see [integration status](INTEGRATION_STATUS.md) for their branches and the reconciliation needed before merging. Live model, Supabase and DagsHub connections remain separate setup tasks.
