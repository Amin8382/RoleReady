'use client';
import { useMemo, useRef, useState } from 'react';
import { analyze, demoFeedback, questions, type Profile } from '@/lib/interview';

type Stage = 'setup' | 'analysis' | 'interview' | 'report';
const stages: { id: Stage; label: string }[] = [
  { id: 'setup', label: '01 · Your profile' }, { id: 'analysis', label: '02 · Gap analysis' },
  { id: 'interview', label: '03 · Interview' }, { id: 'report', label: '04 · Feedback' },
];
export default function Home() {
  const [stage,setStage] = useState<Stage>('setup');
  const [profile,setProfile] = useState<Profile>({ resume: '', job: '', role: '' });
  const [loading,setLoading] = useState(false);
  const [error,setError] = useState('');
  const [index,setIndex] = useState(0);
  const [answers,setAnswers] = useState<string[]>(Array(7).fill(''));
  const fileRef = useRef<HTMLInputElement>(null);
  const gap = useMemo(() => analyze(profile), [profile]);
  const qs = useMemo(() => questions(profile,gap),[profile,gap]);
  const feedback = useMemo(() => demoFeedback(answers),[answers]);
  function change(key: keyof Profile,value: string) { setProfile(s=>({...s,[key]:value})); }
  async function upload(file?: File) {
    if (!file) return;
    setLoading(true);setError('');
    try {
      const body = new FormData();body.append('file',file);
      const response = await fetch('/api/parse-resume',{method:'POST',body});
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || 'Upload failed.');
      change('resume',result.text);
    } catch(e) {setError(e instanceof Error ? e.message : 'Upload failed.');}
    finally {setLoading(false);if(fileRef.current) fileRef.current.value='';}
  }
  function start() {
    if (!profile.resume.trim() || !profile.job.trim() || !profile.role.trim()) {setError('Please enter your target role, resume and job description.');return;}
    setError('');setStage('analysis');
  }
  function download() {
    const content = [
      '# RoleReady · Practice cheat sheet',`Target role: ${profile.role}`,'',
      '## Gap analysis',`Matched: ${gap.matched.join(', ') || 'None found'}`,`Potential gaps: ${gap.missing.join(', ') || 'None found'}`,'',
      '## Interview rehearsal',...qs.flatMap((q,i)=>[`### ${i+1}. ${q}`,answers[i] || '(unanswered)','']),
      '## Demo feedback',`Demo score (heuristic, not AI): ${feedback.score}/100`,feedback.summary,...feedback.improvements.map(x=>'- '+x),
    ].join('\n');
    const url=URL.createObjectURL(new Blob([content],{type:'text/markdown;charset=utf-8'}));
    const link=document.createElement('a');link.href=url;link.download='roleready-cheatsheet.md';link.click();URL.revokeObjectURL(url);
  }
  return <main className="shell">
    <nav className="nav"><a className="logo" href="/">Role<span>Ready.</span></a><span className="tag">INTERVIEW INTELLIGENCE · MVP</span></nav>
    <section className="hero"><span className="eyebrow">PREPARE WITH PURPOSE</span><h1>Your next interview.<br/><em>Your strongest performance.</em></h1><p className="sub">Bring your resume and a job description. Discover skill gaps, rehearse seven tailored questions, and leave with a practical improvement plan.</p>
      <div className="steps">{stages.map(s=><span key={s.id} className={'step '+(stage===s.id?'active':'')}>{s.label}</span>)}</div>
    </section>
    <section className="work" aria-live="polite">
      {stage==='setup' && <><h2>Let's build your interview plan.</h2><p>Start with the role you want and the experience you already have. Resume content stays in this browser during the session; uploaded files are parsed server-side and are not intentionally stored.</p>
        <div className="field"><label htmlFor="role">Target position</label><input id="role" value={profile.role} onChange={e=>change('role',e.target.value)} placeholder="e.g. Machine Learning Engineer" maxLength={120}/></div>
        <div className="grid"><div><div className="field"><label htmlFor="resume">Resume text</label><textarea id="resume" value={profile.resume} onChange={e=>change('resume',e.target.value)} placeholder="Paste resume text or upload a file…" maxLength={20000} /></div><input ref={fileRef} aria-label="Upload resume" type="file" accept=".pdf,.docx,.txt" onChange={e=>void upload(e.target.files?.[0])}/><div className="hint">PDF, DOCX or TXT, up to 5 MB. Scanned PDFs are not supported yet.</div></div>
          <div className="field"><label htmlFor="job">Job description</label><textarea id="job" value={profile.job} onChange={e=>change('job',e.target.value)} placeholder="Paste the job requirements here…" maxLength={20000}/></div></div>
        {error && <div className="alert" role="alert">{error}</div>}
        <div className="actions"><button className="primary" onClick={start} disabled={loading}>{loading?'Reading resume…':'Analyze my fit →'}</button><span className="hint">No account or API key required for this demo.</span></div></>}
      {stage==='analysis' && <><span className="pill">STEP 02 · KEYWORD MATCH</span><h2 style={{marginTop:16}}>Your role-fit snapshot</h2><p>This is a transparent keyword comparison, not an AI judgment. Missing keywords may represent wording differences rather than actual missing skills.</p><div className="scoreline"><span className="metric">{gap.coverage}%</span><span className="hint">Job-description skill keywords also found in your resume</span></div>
        <div className="grid"><div className="mini"><h3>Skills found in both</h3><p>{gap.matched.length ? gap.matched.join(' · ') : 'No shared keywords detected.'}</p></div><div className="mini"><h3>Worth preparing for</h3><p>{gap.missing.length ? gap.missing.join(' · ') : 'No missing keywords in the current vocabulary.'}</p></div></div>
        {gap.keywords.length===0 && <div className="info" style={{marginTop:18}}>No supported skill keywords detected. We can still practice behavioral and project questions.</div>}
        <div className="actions"><button className="secondary" onClick={()=>setStage('setup')}>← Edit profile</button><button className="primary" onClick={()=>{setIndex(0);setStage('interview');}}>Begin 7-question interview →</button></div></>}
      {stage==='interview' && <><span className="pill">QUESTION {index+1} OF 7</span><div className="progress"><div style={{width:`${((index+1)/7)*100}%`}}/></div><div className="question">{qs[index]}</div><p>Answer as if you were in a real interview. Try the STAR method. Voice recording and transcription will be added in the next phase.</p>
        <div className="field"><label htmlFor="answer">Your response</label><textarea id="answer" value={answers[index]} onChange={e=>setAnswers(old=>old.map((a,i)=>i===index?e.target.value:a))} placeholder="Type your response here…" maxLength={5000}/></div><div className="actions"><button className="secondary" onClick={()=>index===0?setStage('analysis'):setIndex(i=>i-1)}>← Back</button><button className="primary" onClick={()=>index===6?setStage('report'):setIndex(i=>i+1)}>{index===6?'Get my feedback →':'Next question →'}</button></div></>}
      {stage==='report' && <><span className="pill">PRACTICE COMPLETE</span><h2 style={{marginTop:16}}>Your rehearsal debrief</h2><div className="info"><strong>Demo / heuristic mode.</strong> This is not a model-generated performance assessment. Your answers are scored using simple length and wording signals.</div><div className="scoreline" style={{marginTop:18}}><span className="metric">{feedback.score}/100</span><span className="mode">DEMO SCORE ONLY</span></div><p>{feedback.summary}</p>
        <div className="cards"><div className="mini"><h3>What worked</h3>{feedback.strengths.map(x=><p key={x}>✓ {x}</p>)}</div><div className="mini"><h3>What to improve</h3>{feedback.improvements.map(x=><p key={x}>→ {x}</p>)}</div><div className="mini"><h3>Skills to review</h3><p>{gap.missing.join(' · ') || 'No detected skill gaps.'}</p></div></div>
        <h2 style={{marginTop:30}}>Your answers</h2>{qs.map((q,i)=><div className="answers" key={i}><strong>{i+1}. {q}</strong><p>{answers[i] || 'No answer entered.'}</p><span className="hint">Demo signal: {feedback.answerScores[i]}/100</span></div>)}
        <div className="actions"><button className="primary" onClick={download}>Download cheat sheet ↓</button><button className="secondary" onClick={()=>{setStage('analysis');setAnswers(Array(7).fill(''));setIndex(0);}}>Practice again</button></div></>}
    </section><footer className="footer">© RoleReady · Built for growth, not guesswork. · Demo MVP</footer>
  </main>;
}
