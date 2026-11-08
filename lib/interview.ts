export type Profile = { resume: string; job: string; role: string };
export type Gap = { matched: string[]; missing: string[]; coverage: number; keywords: string[] };
const SKILLS = ['python','sql','typescript','javascript','react','next.js','node.js','fastapi','pytorch','tensorflow','machine learning','deep learning','nlp','rag','llm','docker','kubernetes','aws','azure','gcp','postgresql','supabase','git','ci/cd','rest api','data analysis','communication','leadership','agile','testing','statistics','data visualization','power bi','spark','scikit-learn','pandas','transformers','fine-tuning','vector database','faiss'];
const has = (text: string, term: string) => new RegExp('(^|[^a-z0-9])' + term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '([^a-z0-9]|$)', 'i').test(text);
export function analyze(profile: Profile): Gap {
  const keywords = SKILLS.filter(s => has(profile.job,s));
  const matched = keywords.filter(s => has(profile.resume,s));
  const missing = keywords.filter(s => !has(profile.resume,s));
  return { matched, missing, keywords, coverage: keywords.length ? Math.round((matched.length / keywords.length) * 100) : 0 };
}
export function questions(profile: Profile, gap: Gap): string[] {
  const role = profile.role.trim() || 'this role';
  return [
    `Tell me about yourself and why you are interested in ${role}.`,
    `Describe a project that best demonstrates your suitability for ${role}. What was your personal contribution?`,
    gap.missing[0] ? `This position mentions ${gap.missing[0]}. How would you approach work involving it, and what would you need to learn?` : 'Walk me through a difficult technical problem you solved, including your trade-offs.',
    'Tell me about a time you received difficult feedback. What changed as a result?',
    gap.matched[0] ? `Walk me through a concrete example of how you used ${gap.matched[0]}, including the result.` : 'Explain how you would learn a new tool or framework under a deadline.',
    'Describe a time you had to prioritize competing tasks with limited time.',
    `What would your priorities be during your first 30 days in ${role}?`,
  ];
}
export type Feedback = { score: number; summary: string; strengths: string[]; improvements: string[]; answerScores: number[] };
export function demoFeedback(answers: string[]): Feedback {
  const answerScores = answers.map(a => {
    const words = a.trim().split(/\s+/).filter(Boolean);
    if (!words.length) return 0;
    let score = Math.min(65, 25 + words.length);
    if (/\b(i|my|we)\b/i.test(a)) score += 8;
    if (/\b(result|impact|improved|reduced|increased|delivered|learned)\b/i.test(a)) score += 12;
    if (/\d/.test(a)) score += 8;
    return Math.min(100,score);
  });
  const score = Math.round(answerScores.reduce((a,b) => a+b,0) / (answerScores.length || 1));
  return {
    score, answerScores,
    summary: 'Demo-only, rule-based practice feedback. Scores reflect answer length and a few storytelling signals, NOT verified interview competence or an AI assessment.',
    strengths: ['Your responses are captured in one place for review.', ...(answers.some(a => /\b(result|impact|improved|reduced|increased|delivered)\b/i.test(a)) ? ['At least one answer mentions an outcome.'] : [])],
    improvements: ['Use STAR: Situation, Task, Action, Result.','Explain what YOU did and quantify outcomes where truthful.','Rehearse missing skills from the job description without claiming experience you do not have.'],
  };
}
