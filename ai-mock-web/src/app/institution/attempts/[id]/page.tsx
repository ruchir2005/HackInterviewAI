"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { CheckCircle2, Clock, Save } from "lucide-react";
import { institutionApi, InstitutionAttempt } from "@/app/lib/institutionApi";

type Drafts = Record<string, { answer_text?: string; selected_option_index?: number }>;

export default function InstitutionAttemptPage() {
  const { id } = useParams<{ id: string }>();
  const [attempt, setAttempt] = useState<InstitutionAttempt | null>(null);
  const [drafts, setDrafts] = useState<Drafts>({});
  const [remaining, setRemaining] = useState(0);
  const [targetTime, setTargetTime] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await institutionApi<InstitutionAttempt>(`attempts/${id}`);
      setAttempt(data);
      const existing: Drafts = {};
      data.answers.forEach((a) => { existing[a.question_id] = { answer_text:a.answer_text || "", selected_option_index:a.selected_option_index ?? undefined }; });
      setDrafts(existing);
      const serverRemaining = Math.max(0, new Date(data.expires_at).getTime() - new Date(data.server_time).getTime());
      setTargetTime(Date.now() + serverRemaining);
      setRemaining(Math.ceil(serverRemaining / 1000));
    } catch (err) { setError(err instanceof Error ? err.message : "Could not load attempt"); }
  }, [id]);

  useEffect(() => { load(); }, [load]);
  const isOpen = attempt?.status === "in_progress";

  const submit = useCallback(async () => {
    if (!attempt || attempt.status !== "in_progress" || busy) return;
    setBusy(true); setError(null);
    try { setAttempt(await institutionApi<InstitutionAttempt>(`attempts/${attempt.id}/submit`, { method:"POST" })); }
    catch (err) { setError(err instanceof Error ? err.message : "Could not submit attempt"); }
    finally { setBusy(false); }
  }, [attempt, busy]);

  useEffect(() => {
    if (!isOpen || !targetTime) return;
    const timer = setInterval(() => {
      const next = Math.max(0, Math.ceil((targetTime - Date.now()) / 1000));
      setRemaining(next);
      if (next === 0) { clearInterval(timer); submit(); }
    }, 1000);
    return () => clearInterval(timer);
  }, [isOpen, targetTime, submit]);

  const questions = useMemo(() => attempt?.interview.rounds.flatMap((round) => round.questions) || [], [attempt]);
  const save = async (questionId: string) => {
    if (!attempt || !isOpen) return;
    try {
      await institutionApi(`attempts/${attempt.id}/answers/${questionId}`, { method:"PUT", body:JSON.stringify(drafts[questionId] || {}) });
    } catch (err) { setError(err instanceof Error ? err.message : "Answer could not be saved"); }
  };

  if (!attempt) return <div className="p-12 text-center">{error || "Loading your attempt…"}</div>;
  const mins = Math.floor(remaining / 60), secs = remaining % 60;

  if (!isOpen) return <div className="min-h-screen px-5 py-16"><div className="max-w-4xl mx-auto space-y-6"><Link href="/institution" className="text-primary">← Institution workspace</Link><div className="bg-card border border-border rounded-2xl p-8"><CheckCircle2 className="w-12 h-12 text-emerald-500 mb-4"/><h1 className="text-3xl font-bold">{attempt.interview.title}</h1><p className="text-muted-foreground mt-2">Status: {attempt.status.replace("_"," ")}</p><p className="text-5xl font-extrabold text-primary my-7">{attempt.overall_score_percentage == null ? "Evaluation pending" : `${attempt.overall_score_percentage}%`}</p>{attempt.answers.map((answer)=>{const q=questions.find((x)=>x.id===answer.question_id);return <div key={answer.id} className="border-t border-border py-5"><p className="font-semibold">{q?.question_text}</p><p className="text-sm text-muted-foreground mt-2">Your answer: {q?.question_type==="mcq" ? q.mcq_options?.[answer.selected_option_index ?? -1] || "Unanswered" : answer.answer_text || "Unanswered"}</p><p className="text-sm mt-2">Score: {answer.score ?? "Pending"} / {q?.max_score}</p><p className="text-sm text-muted-foreground">{answer.feedback || (answer.evaluation_status==="failed" ? "AI evaluation failed; faculty can retry." : "")}</p></div>})}</div></div></div>;

  return <div className="min-h-screen px-5 py-12"><div className="max-w-4xl mx-auto space-y-6"><div className="sticky top-3 z-40 bg-card/95 backdrop-blur border border-border rounded-2xl p-4 flex items-center justify-between"><div><h1 className="font-bold">{attempt.interview.title}</h1><p className="text-xs text-muted-foreground">Answers save individually. Refresh resumes this attempt.</p></div><span className="flex items-center gap-2 text-lg font-mono font-bold"><Clock className="w-5 h-5 text-primary"/>{mins}:{String(secs).padStart(2,"0")}</span></div>{error&&<div className="p-4 rounded-xl bg-red-500/10 text-red-400">{error}</div>}<section className="bg-card border border-border rounded-2xl p-6"><h2 className="font-bold">Instructions</h2><p className="text-muted-foreground mt-2 whitespace-pre-wrap">{attempt.interview.instructions || "Answer every question to the best of your ability. Submit before the timer expires."}</p></section>{attempt.interview.rounds.map((round)=><section key={round.id} className="space-y-4"><h2 className="text-xl font-bold">{round.title}</h2>{round.questions.map((q)=><div key={q.id} className="bg-card border border-border rounded-2xl p-6"><p className="font-semibold mb-4">{q.position+1}. {q.question_text}</p>{q.question_type==="mcq" ? <div className="space-y-2">{q.mcq_options?.map((option,index)=><label key={index} className="flex gap-3 border border-border rounded-xl p-3 cursor-pointer"><input type="radio" name={q.id} checked={drafts[q.id]?.selected_option_index===index} onChange={()=>{setDrafts({...drafts,[q.id]:{selected_option_index:index}});setTimeout(()=>institutionApi(`attempts/${attempt.id}/answers/${q.id}`,{method:"PUT",body:JSON.stringify({selected_option_index:index})}).catch((e)=>setError(e.message)),0)}}/>{option}</label>)}</div> : <><textarea value={drafts[q.id]?.answer_text||""} onChange={(e)=>setDrafts({...drafts,[q.id]:{answer_text:e.target.value}})} onBlur={()=>save(q.id)} className="w-full min-h-36 bg-background border border-border rounded-xl p-4" placeholder="Type your answer…"/><button type="button" onClick={()=>save(q.id)} className="mt-3 inline-flex gap-2 items-center text-sm text-primary font-semibold"><Save className="w-4 h-4"/>Save answer</button></>}</div>)}</section>)}<button disabled={busy} onClick={submit} className="w-full py-4 rounded-xl bg-primary text-primary-foreground font-bold">{busy?"Submitting and evaluating…":"Submit interview"}</button></div></div>;
}
