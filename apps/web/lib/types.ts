export type Finding = { title: string; detail: string; status: "supported" | "not_evidenced"; job_quote: string; cv_quote: string | null };
export type Question = { id: string; text: string; skill: string; difficulty: number; category: string; reason: string; tip: string; reference_criteria: string[]; reference_answer: string; source_ids: string[] };
export type Evaluation = { score: number; feedback: string; rubric_version: string; evaluator: string };
export type Answer = { transcript: string; original_transcript: string | null; evaluation: Evaluation };
export type Report = { role: string; average_score: number; rubric_version: string; notice: string; priorities: string[]; items: { question_id: string; question: string; skill: string; score: number; feedback: string; practice_points: string[]; reference_answer: string }[] };
export type PracticeSession = {
  id: string; version: number; created_at: string; mode: "llm" | "retrieval";
  inputs: { cv_text: string; job_description: string; role: string; experience_level: string };
  analysis: { summary: string; findings: Finding[]; questions: Question[] };
  answers: Record<string, Answer>; drafts: Record<string, { original_transcript: string }>; report: Report | null;
};
export type SessionSummary = { id: string; role: string; created_at: string; answered: number; has_report: boolean; mode: string };
export type Capabilities = { auth_mode: "local" | "supabase"; question_mode: "llm" | "retrieval"; generator_configured: boolean; evaluator_configured: boolean; voice_enabled: boolean; retriever: string; bank_prepared: boolean; index_prepared: boolean };
