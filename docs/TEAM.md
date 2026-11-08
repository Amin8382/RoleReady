# Team ownership

| Owner | Deliverables |
| --- | --- |
| Mohamed Amin Guesmi | Dataset provenance and cleaning; retrieval; Qwen prompts; paired fine-tuning data; LoRA comparison; generation evaluation |
| Oussema Ferchichi | FastAPI contracts; session persistence; Supabase authentication and isolation; Prometheus scoring; API tests |
| Khaled Briki | Next.js interface; recording and transcript correction; Whisper/Kokoro adapters; feedback views and PDF download |

All three review examples, label held-out cases, review changes and rehearse the full demonstration. Every meaningful change updates `PROGRESS.md`; each experiment records the code revision and input dataset hash.

## First handoff

| Person | Next concrete task | Done when |
| --- | --- | --- |
| Mohamed Amin Guesmi | Connect Qwen, review the eight retrieval labels and add realistic held-out CV/job cases | A real session returns seven relevant, distinct questions with verifiable evidence; failed cases and parameters are logged |
| Oussema Ferchichi | Connect Prometheus and a Supabase project; apply the migration | Human-reviewed answers receive valid rubric feedback; two accounts cannot access one another's sessions |
| Khaled Briki | Test real microphone input, transcript correction and PDFs on desktop/mobile | Technical terms can be corrected before grading; all seven answers survive a reload; PDF opens cleanly |

Shared milestone: complete one real seven-answer session using both live reasoning models and the local voice models. Then freeze an evaluation set, calibrate scoring and connect DagsHub. No one should label the product production-ready or the model “best” before those checks.
