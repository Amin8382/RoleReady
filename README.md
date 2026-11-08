# RoleReady

Resume-to-job interview preparation MVP, implemented in Next.js, React and TypeScript.

## Run locally

Requires Node.js 20+.

```bash
npm install
npm run dev
```

Open http://localhost:3000. Also run `npm run typecheck` and `npm run build` before deployment.

## Features implemented

- Responsive four-stage experience: profile, gap analysis, seven-question interview and feedback
- Resume text entry or PDF, DOCX, TXT upload (5 MB maximum)
- Transparent curated skill-keyword overlap (not proof of ability)
- Role- and gap-aware interview question prompts
- Simple **demo-only** heuristic feedback, clearly labeled as non-AI
- Downloadable Markdown cheat sheet (PDF export not implemented)

## Limitations and privacy

This is a runnable-code MVP, **not yet verified by a local build or automated tests**. No live model integrations, recording, Whisper transcription, Supabase, Stripe, RAG or PDF export have been implemented.

Uploaded files are parsed server-side for text extraction without intentional persistence. Resume and job text are held in browser component state. Do not upload sensitive information to publicly deployed instances without production-grade security, authentication and retention controls. Scanned PDFs cannot be read without OCR.

## Next steps

1. Install dependencies, typecheck, test and fix any runtime issues.
2. Integrate a real multi-model pipeline: role analysis, grounded question selection, speech transcription and answer assessment.
3. Add Supabase auth, secure storage, robust evaluation and PDF export.
4. Add CI, tests, accessibility checks, deployment controls and (if needed) billing.

## Project branch

Development implementation: `feat/role-ready-mvp`. The default `main` branch remains preserved until review.
