"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createClient } from "@supabase/supabase-js";
import { api, rawApi } from "@/lib/api";
import type { Capabilities, PracticeSession, SessionSummary } from "@/lib/types";

const STEPS = ["Your starting point", "Your role fit", "Practice room", "Your cheat sheet"];
const ROLES = ["Data Scientist", "Machine Learning Engineer", "Backend Developer", "Frontend Developer", "Data Engineer", "DevOps Engineer", "MLOps Engineer"];
function Arrow() { return <span aria-hidden="true">↗</span>; }
function message(error: unknown) { return error instanceof Error ? error.message : "Something went wrong. Please try again."; }

export default function Workspace() {
  const [caps, setCaps] = useState<Capabilities | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [authNotice, setAuthNotice] = useState("");
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [step, setStep] = useState(0);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [cv, setCv] = useState("");
  const [job, setJob] = useState("");
  const [role, setRole] = useState("Data Scientist");
  const [level, setLevel] = useState("junior");
  const [transcript, setTranscript] = useState("");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [recording, setRecording] = useState(false);
  const [recordedSeconds, setRecordedSeconds] = useState(0);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const recordingTimer = useRef<ReturnType<typeof setInterval> | null>(null);
  const player = useRef<HTMLAudioElement | null>(null);
  const audioUrl = useRef<string | null>(null);
  const mounted = useRef(true);
  const busyRef = useRef(false);
  const question = session?.analysis.questions[questionIndex];
  const answer = question ? session?.answers[question.id] : undefined;
  const answered = session ? Object.keys(session.answers).length : 0;
  const locked = !!busy || recording;
  const supabase = useMemo(() => {
    const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
    const key = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
    return url && key ? createClient(url, key) : null;
  }, []);

  const refreshSessions = useCallback(async () => {
    setSessions(await api<SessionSummary[]>("/v1/sessions", token));
  }, [token]);

  useEffect(() => {
    mounted.current = true;
    api<Capabilities>("/v1/capabilities", null).then(setCaps).catch(e => setError(message(e)));
    if (supabase) {
      supabase.auth.getSession().then(({ data }) => setToken(data.session?.access_token || null));
    }
    const listener = supabase?.auth.onAuthStateChange((_event, next) => {
      setToken(next?.access_token || null);
      if (!next) { setSession(null); setSessions([]); setStep(0); setCv(""); setJob(""); setTranscript(""); }
    });
    return () => {
      mounted.current = false;
      listener?.data.subscription.unsubscribe();
      if (recordingTimer.current) clearInterval(recordingTimer.current);
      if (recorder.current?.state === "recording") recorder.current.stop();
      recorder.current?.stream.getTracks().forEach(track => track.stop());
      player.current?.pause();
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
    };
  }, [supabase]);

  useEffect(() => {
    if (caps && (caps.auth_mode === "local" || token)) refreshSessions().catch(e => setError(message(e)));
  }, [caps, token, refreshSessions]);

  useEffect(() => {
    const q = session?.analysis.questions[questionIndex];
    setTranscript(q ? session?.answers[q.id]?.transcript || session?.drafts[q.id]?.original_transcript || "" : "");
    player.current?.pause();
    // A transcription response updates the draft without changing the active question.
  }, [session?.id, questionIndex]); // eslint-disable-line react-hooks/exhaustive-deps

  async function task(label: string, fn: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true; setBusy(label); setError("");
    try { await fn(); } catch (e) { if (mounted.current) setError(message(e)); }
    finally { busyRef.current = false; if (mounted.current) setBusy(""); }
  }

  async function createSession(event: React.FormEvent) {
    event.preventDefault();
    await task("Preparing your practice session…", async () => {
      const next = await api<PracticeSession>("/v1/sessions", token, { method: "POST", body: JSON.stringify({ cv_text: cv, job_description: job, role, experience_level: level }) });
      setSession(next); setQuestionIndex(0); setStep(1);
      await refreshSessions();
    });
  }

  async function upload(file: File | undefined) {
    if (!file) return;
    if (file.size > 5 * 1024 * 1024) { setError("Choose a file smaller than 5 MB."); return; }
    await task("Reading your CV…", async () => {
      const form = new FormData(); form.append("file", file);
      const result = await api<{ text: string }>("/v1/extract", token, { method: "POST", body: form });
      setCv(result.text);
    });
  }

  async function openSession(id: string) {
    await task("Opening your session…", async () => {
      const next = await api<PracticeSession>(`/v1/sessions/${id}`, token);
      setSession(next); setStep(next.report ? 3 : 2);
      const first = next.analysis.questions.findIndex(q => !next.answers[q.id]);
      setQuestionIndex(first === -1 ? 0 : first);
    });
  }

  async function listen() {
    if (!session || !question) return;
    await task("Preparing question audio…", async () => {
      player.current?.pause();
      if (audioUrl.current) URL.revokeObjectURL(audioUrl.current);
      const response = await rawApi(`/v1/sessions/${session.id}/speech`, token, { method: "POST", body: JSON.stringify({ question_id: question.id }) });
      audioUrl.current = URL.createObjectURL(await response.blob());
      player.current = new Audio(audioUrl.current);
      await player.current.play();
    });
  }

  async function startRecording() {
    if (!session || !question) return;
    setError(""); player.current?.pause();
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError("Recording needs a supported browser on HTTPS or localhost. You can type your answer below."); return;
    }
    let stream: MediaStream | undefined;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find(type => MediaRecorder.isTypeSupported(type));
      const current = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
      recorder.current = current;
      const chunks: Blob[] = [];
      current.ondataavailable = event => { if (event.data.size) chunks.push(event.data); };
      current.onstop = () => {
        stream?.getTracks().forEach(track => track.stop());
        if (recordingTimer.current) clearInterval(recordingTimer.current);
        if (!mounted.current) return;
        setRecording(false);
        void task("Transcribing your answer…", async () => {
          const form = new FormData();
          form.append("question_id", question.id);
          form.append("file", new Blob(chunks, { type: current.mimeType }), current.mimeType.includes("mp4") ? "answer.mp4" : "answer.webm");
          const result = await api<{ transcript: string; session: PracticeSession }>(`/v1/sessions/${session.id}/transcribe`, token, { method: "POST", body: form });
          setTranscript(result.transcript); setSession(result.session);
        });
      };
      current.onerror = () => { setError("Recording failed. Try again or type your answer."); if (current.state === "recording") current.stop(); };
      current.start(1000); setRecordedSeconds(0); setRecording(true);
      const started = Date.now();
      recordingTimer.current = setInterval(() => {
        const seconds = Math.floor((Date.now() - started) / 1000);
        setRecordedSeconds(seconds);
        if (seconds >= 175 && current.state === "recording") current.stop();
      }, 500);
    } catch (e) { stream?.getTracks().forEach(track => track.stop()); setError(`Microphone unavailable. ${message(e)}`); }
  }

  async function submitAnswer() {
    if (!session || !question) return;
    await task("Reviewing your answer…", async () => {
      const next = await api<PracticeSession>(`/v1/sessions/${session.id}/answers`, token, { method: "POST", body: JSON.stringify({ question_id: question.id, transcript }) });
      setSession(next); await refreshSessions();
    });
  }

  async function createReport() {
    if (!session) return;
    await task("Building your cheat sheet…", async () => {
      setSession(await api<PracticeSession>(`/v1/sessions/${session.id}/report`, token, { method: "POST" }));
      setStep(3); await refreshSessions();
    });
  }

  async function downloadPdf() {
    if (!session) return;
    await task("Preparing your PDF…", async () => {
      const response = await rawApi(`/v1/sessions/${session.id}/report.pdf`, token);
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a"); link.href = url; link.download = "RoleReady-cheat-sheet.pdf"; link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    });
  }

  const signedIn = caps?.auth_mode === "local" || !!token;
  const ready = caps && caps.bank_prepared && (caps.retriever !== "bge" || caps.index_prepared) && (caps.question_mode === "retrieval" || caps.generator_configured);

  return <div className="shell">
    <aside className="sidebar">
      <a className="brand" href="/" aria-label="RoleReady home"><span className="brand-mark">r<span>.</span></span>RoleReady<span className="brand-dot">β</span></a>
      <div className="workspace-label">YOUR WORKSPACE</div>
      <button className="new-session" disabled={locked} onClick={() => { setSession(null); setStep(0); setQuestionIndex(0); setError(""); }}>＋ New practice session</button>
      <nav aria-label="Session steps" className="steps">{STEPS.map((title, i) => <button key={title} className={step === i ? "active" : ""} disabled={locked || (i > 0 && !session) || (i === 3 && !session?.report)} onClick={() => setStep(i)}><span className="step-number">{i + 1}</span>{title}{step === i && <span className="step-dot" />}</button>)}</nav>
      <div className="session-heading"><span>RECENT SESSIONS</span><span>{sessions.length}</span></div>
      <div className="session-list">{sessions.length ? sessions.map(item => <div className={`session-row ${session?.id === item.id ? "selected" : ""}`} key={item.id}>
        <button className="session-link" disabled={locked} onClick={() => void openSession(item.id)}><strong>{item.role}</strong><span>{item.answered}/7 answers · {new Date(item.created_at).toLocaleDateString("en", { month: "short", day: "numeric" })}</span></button>
        <button className="delete-button" disabled={locked} aria-label={`Delete ${item.role} session`} onClick={() => setDeleteId(item.id)}>×</button>
      </div>) : <p className="empty-history">Your practice sessions will live here. Come back to see how you did.</p>}</div>
      <div className="sidebar-bottom"><div className="small-orbit" aria-hidden="true">✳</div><p>A little practice.<br /><strong>A clearer next step.</strong></p></div>
    </aside>
    <main>
      <header className="topbar"><div><span className="muted">Workspace</span><span className="slash">/</span>{session ? session.inputs.role : "New session"}</div><div className="topbar-right"><span className="language">EN</span>{caps?.auth_mode === "local" ? <span className="mode-pill">Local workspace</span> : token ? <button className="text-button" disabled={locked} onClick={() => void supabase?.auth.signOut()}>Sign out</button> : null}<span className="avatar" aria-hidden="true">R</span></div></header>
      {signedIn && <details className="mobile-history"><summary>Saved sessions ({sessions.length})</summary>{sessions.length ? sessions.map(item => <div className="session-row" key={item.id}><button className="session-link" disabled={locked} onClick={() => void openSession(item.id)}><strong>{item.role}</strong><span>{item.answered}/7 answers</span></button><button className="delete-button" disabled={locked} aria-label={`Delete ${item.role} session`} onClick={() => setDeleteId(item.id)}>×</button></div>) : <p className="empty-history">Your saved practice sessions will appear here.</p>}</details>}
      <div className="content">
        <div className="eyebrow"><span /> INTERVIEW PREPARATION, WITH DIRECTION</div>
        <div className="page-heading"><div><h1>{[<>Your next role.<br /><em>Your best preparation.</em></>, <>Know your strengths.<br /><em>Find your focus.</em></>, <>A little practice.<br /><em>A stronger answer.</em></>, <>Take your next step.<br /><em>Keep the good advice.</em></>][step]}</h1><p>{["Bring your experience and a role you want. We’ll help you prepare for the conversation.", "Use the evidence from your CV to focus your practice. An unmentioned skill is a chance to add context.", "Think it through, answer in your own words, and get feedback you can use.", "Seven answers, specific feedback, and a focused plan for your next interview."][step]}</p></div><div className="hero-symbol" aria-hidden="true"><span>↗</span><i /></div></div>
        {error && <div className="alert error" role="alert"><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError("")}>×</button></div>}
        {busy && <div className="alert progress" role="status"><span className="spinner" />{busy}</div>}
        {!caps && !error && <p role="status">Connecting to your workspace…</p>}
        {caps?.auth_mode === "supabase" && !token ? <section className="card auth-card"><div className="card-kicker">YOUR PRIVATE PRACTICE SPACE</div><h2>Sign in to get started</h2>{!supabase ? <p>Sign-in is not configured yet. The project owner needs to connect Supabase.</p> : <form onSubmit={event => { event.preventDefault(); void task("Signing in…", async () => { const { error: err } = await supabase.auth.signInWithPassword({ email, password }); if (err) throw err; }); }}>
          <label>Email<input type="email" autoComplete="email" required value={email} onChange={e => setEmail(e.target.value)} /></label><label>Password<input type="password" autoComplete="current-password" minLength={8} required value={password} onChange={e => setPassword(e.target.value)} /></label><div className="actions"><button className="primary" disabled={locked}>Sign in <Arrow /></button><button type="button" className="secondary" disabled={locked || !email || password.length < 8} onClick={() => void task("Creating your account…", async () => { const { error: err } = await supabase.auth.signUp({ email, password }); if (err) throw err; setAuthNotice("Check your email to confirm your account, then sign in here."); })}>Create account</button></div>{authNotice && <p role="status">{authNotice}</p>}
        </form>}</section> : signedIn && <>
          {step === 0 && <>
            <div className="feature-line"><span><b>01</b> Your CV + target role</span><span><b>02</b> 7 focused questions</span><span><b>03</b> Feedback you can use</span></div>
            {caps?.question_mode === "retrieval" && <div className="alert info">Question-bank practice is enabled. Questions are retrieved from an unreviewed research dataset; personalised gap analysis is not enabled.</div>}
            {caps && !ready && <div className="alert info">Practice setup is incomplete. The question model and prepared data need to be connected before you can start.</div>}
            <form onSubmit={createSession} className="setup-grid">
              <section className="card cv-card"><div className="card-title"><span className="card-icon">▤</span><div><h2>Start with your story</h2><p>Give your practice some real context.</p></div><span className="number-label">01</span></div>
                <label className={`upload-zone ${locked ? "disabled" : ""}`}><input type="file" accept=".pdf,.docx,.txt" disabled={locked} onChange={event => { void upload(event.target.files?.[0]); event.target.value = ""; }} /><span className="upload-icon" aria-hidden="true">↑</span><strong>Choose your CV</strong><span>PDF, DOCX or TXT · up to 5 MB</span></label>
                <div className="divider-text"><span />or paste your CV<span /></div>
                <label className="sr-only" htmlFor="cv">Your CV text</label><textarea id="cv" value={cv} onChange={e => setCv(e.target.value)} minLength={40} maxLength={24000} required placeholder="Your experience, skills, projects and education…" disabled={locked} rows={9} /><div className="field-note">Review the extracted text before continuing.<span>{cv.length.toLocaleString()}/24,000</span></div>
              </section>
              <section className="card role-card"><div className="card-title"><span className="card-icon">↗</span><div><h2>Where do you want to go?</h2><p>Make the practice relevant to your next role.</p></div><span className="number-label">02</span></div>
                <div className="role-fields"><label>Target role<input list="roles" value={role} onChange={e => setRole(e.target.value)} minLength={2} maxLength={120} required disabled={locked} /><datalist id="roles">{ROLES.map(r => <option key={r} value={r} />)}</datalist></label><label>Experience level<select value={level} onChange={e => setLevel(e.target.value)} disabled={locked}><option value="junior">Junior / early career</option><option value="mid">Mid-level</option><option value="senior">Senior</option></select></label></div>
                <label>Job description<textarea value={job} onChange={e => setJob(e.target.value)} minLength={40} maxLength={16000} required disabled={locked} placeholder="Paste the responsibilities, requirements and skills from the job posting…" rows={10} /></label><div className="field-note">A specific job description makes a better starting point.<span>{job.length.toLocaleString()}/16,000</span></div>
              </section>
              <div className="setup-footer"><p><span aria-hidden="true">◈</span> Your CV text and answers stay in your saved session.<br /><span>Recordings are processed, then discarded. Delete a session at any time.</span></p><button type="submit" className="primary large" disabled={locked || !ready || cv.trim().length < 40 || job.trim().length < 40}>Prepare my session <Arrow /></button></div>
            </form>
            <p className="quiet-note">English practice · AI feedback supports preparation; it does not predict hiring decisions.</p>
          </>}
          {step === 1 && session && <>
            <section className="card overview"><div className="card-kicker">YOUR STARTING POINT</div><h2>{session.inputs.role}</h2><p>{session.analysis.summary}</p></section>
            <div className="findings-grid">{session.analysis.findings.map((finding, i) => <article className="card finding" key={i}><span className={`tag ${finding.status === "supported" ? "green" : "amber"}`}>{finding.status === "supported" ? "Evidence in your CV" : "Not evidenced in your CV"}</span><h3>{finding.title}</h3><p>{finding.detail}</p><blockquote><small>JOB REQUIREMENT</small>“{finding.job_quote}”</blockquote>{finding.cv_quote && <blockquote><small>YOUR CV</small>“{finding.cv_quote}”</blockquote>}</article>)}</div>
            <div className="section-footer"><p>Seven questions. One at a time. Space to think.</p><button className="primary" disabled={locked} onClick={() => setStep(2)}>Enter the practice room <Arrow /></button></div>
          </>}
          {step === 2 && session && question && <div className="practice-grid"><section className="card practice-card"><div className="question-nav" aria-label="Practice questions">{session.analysis.questions.map((q, i) => <button key={q.id} aria-label={`Question ${i + 1}${session.answers[q.id] ? ", answered" : ""}`} aria-current={questionIndex === i ? "step" : undefined} className={`${questionIndex === i ? "current" : ""} ${session.answers[q.id] ? "answered" : ""}`} disabled={locked} onClick={() => setQuestionIndex(i)}>{session.answers[q.id] ? "✓" : i + 1}</button>)}<span>{answered}/7 complete</span></div>
            <div className="question-meta"><span className="tag green">{question.category}</span><span>{question.skill}</span><span>Level {question.difficulty}/3</span></div><h2 className="question-text">{question.text}</h2><p className="question-reason">{question.reason}</p><button className="secondary small" disabled={locked || !caps?.voice_enabled} onClick={() => void listen()}>▷ Listen to question</button>
            <div className="answer-area"><div className="answer-label"><label htmlFor="answer">Your answer</label><span>Use your own words</span></div><textarea id="answer" rows={9} maxLength={8000} value={transcript} onChange={e => setTranscript(e.target.value)} disabled={locked} placeholder="Record your answer or start typing here. You can review and correct a transcript before submitting it." /><div className="record-controls">{recording ? <button className="record-button recording" onClick={() => recorder.current?.stop()}>■ Stop recording · {recordedSeconds}s</button> : <button className="record-button" disabled={locked || !caps?.voice_enabled} onClick={() => void startRecording()}>● Record answer</button>}<span>{caps?.voice_enabled ? "Up to 3 minutes · microphone permission required" : "Voice is not connected. You can type your answer."}</span></div><p className="transcript-note">Check names, numbers and technical terms before submitting. Only this text is scored.</p></div>
            {!caps?.evaluator_configured && <p className="alert info">The evaluator is not connected yet. Scoring will be available once it is configured.</p>}
            <div className="actions"><button className="primary" disabled={locked || !caps?.evaluator_configured || transcript.trim().length < 10 || transcript.trim().split(/\s+/).length < 3} onClick={() => void submitAnswer()}>{answer ? "Re-evaluate answer" : "Get feedback"} <Arrow /></button>{questionIndex < 6 && <button className="text-button" disabled={locked} onClick={() => setQuestionIndex(questionIndex + 1)}>Next question →</button>}</div>
            {answer && <div className="feedback" aria-live="polite"><div className="feedback-top"><h3>Your feedback</h3><span className="score">{answer.evaluation.score}<small>/5</small></span></div><p className="preserve-lines">{answer.evaluation.feedback}</p><details><summary>Reference guidance</summary><ul>{question.reference_criteria.map((point, i) => <li key={i}>{point}</li>)}</ul><p>{question.reference_answer}</p></details><small>Rubric {answer.evaluation.rubric_version} · Provisional coaching score</small>{answer.transcript !== transcript && <p className="unsaved-note">You’ve edited this answer. Submit again to update its feedback.</p>}</div>}
          </section><aside className="practice-side"><section className="card tip-card"><span className="card-kicker">A LITTLE DIRECTION</span><h3>Make your thinking visible.</h3><p>{question.tip}</p><div className="tip-rule" /><p>It’s okay to pause. State your assumptions, explain your choices, and use examples that are true to your experience.</p></section><section className="card completion-card"><span className="card-kicker">YOUR SESSION</span><h3>{answered} of 7 answered</h3><div className="progress-track"><span style={{ width: `${answered / 7 * 100}%` }} /></div><p>Complete all seven answers to bring your feedback together.</p><button className="primary" disabled={locked || answered !== 7} onClick={() => void createReport()}>Create cheat sheet <Arrow /></button></section></aside></div>}
          {step === 3 && session?.report && <>
            <section className="card report-overview"><div><span className="card-kicker">{session.report.role}</span><h2>Your interview cheat sheet</h2><p>{session.report.notice}</p><button className="primary" disabled={locked} onClick={() => void downloadPdf()}>Download PDF ↓</button></div><div className="report-score"><strong>{session.report.average_score.toFixed(1)}<small>/5</small></strong><span>Average practice score</span></div></section>
            <h2 className="section-title">Focus your next practice</h2><div className="priority-grid">{session.report.priorities.map((id, index) => { const item = session.report!.items.find(i => i.question_id === id)!; return <article className="card" key={id}><span className="card-kicker">FOCUS 0{index + 1}</span><h3>{item.skill}</h3><ul>{item.practice_points.map((point, i) => <li key={i}>{point}</li>)}</ul></article>; })}</div>
            <h2 className="section-title">All seven answers, reviewed</h2>{session.report.items.map((item, i) => <details className="card report-item" key={item.question_id}><summary><span>{String(i + 1).padStart(2, "0")}</span><strong>{item.question}</strong><b>{item.score}/5</b></summary><p className="preserve-lines">{item.feedback}</p><h4>Reference guidance</h4><p>{item.reference_answer}</p></details>)}
          </>}
        </>}
        <footer className="page-footer"><span>RoleReady</span><span>Preparation is progress.</span></footer>
      </div>
    </main>
    {deleteId && <div className="modal-backdrop"><section className="card modal" role="dialog" aria-modal="true" aria-labelledby="delete-title"><h2 id="delete-title">Delete this session?</h2><p>This removes its saved CV text, answers, feedback and cheat sheet.</p><div className="actions"><button className="secondary" disabled={locked} onClick={() => setDeleteId(null)}>Keep session</button><button className="danger" disabled={locked} onClick={() => void task("Deleting session…", async () => { await api(`/v1/sessions/${deleteId}`, token, { method: "DELETE" }); if (session?.id === deleteId) { setSession(null); setStep(0); setTranscript(""); } setDeleteId(null); await refreshSessions(); })}>Delete session</button></div></section></div>}
  </div>;
}
