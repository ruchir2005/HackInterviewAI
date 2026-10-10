"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Plus, Save, Trash2 } from "lucide-react";
import { institutionApi, InstitutionInterview } from "@/app/lib/institutionApi";

type QuestionDraft = {
  question_text: string;
  question_type: "hr" | "technical" | "mcq";
  mcq_options: string[];
  mcq_correct_index: number;
  max_score: number;
};
type RoundDraft = { title: string; questions: QuestionDraft[] };

const newQuestion = (): QuestionDraft => ({
  question_text: "", question_type: "hr", mcq_options: ["", "", "", ""], mcq_correct_index: 0, max_score: 10,
});
const newRound = (): RoundDraft => ({ title: "Interview Round", questions: [newQuestion()] });

function Builder() {
  const router = useRouter();
  const search = useSearchParams();
  const institutionId = search.get("institutionId") || "";
  const interviewId = search.get("interviewId");
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [instructions, setInstructions] = useState("");
  const [duration, setDuration] = useState(30);
  const [deadline, setDeadline] = useState("");
  const [batches, setBatches] = useState("");
  const [branches, setBranches] = useState("");
  const [rounds, setRounds] = useState<RoundDraft[]>([newRound()]);
  const [locked, setLocked] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!institutionId || !interviewId) return;
    institutionApi<InstitutionInterview>(`${institutionId}/interviews/${interviewId}`)
      .then((item) => {
        setTitle(item.title); setDescription(item.description || ""); setInstructions(item.instructions || "");
        setDuration(item.duration_minutes); setDeadline(item.deadline ? item.deadline.slice(0, 16) : "");
        setBatches(item.eligible_batches.join(", ")); setBranches(item.eligible_branches.join(", "));
        setLocked(item.status === "published");
        setRounds(item.rounds.map((round) => ({
          title: round.title,
          questions: round.questions.map((q) => ({
            question_text: q.question_text, question_type: q.question_type,
            mcq_options: q.mcq_options || ["", "", "", ""],
            mcq_correct_index: q.mcq_correct_index || 0, max_score: q.max_score,
          })),
        })));
      })
      .catch((err) => setError(err.message));
  }, [institutionId, interviewId]);

  const updateRound = (index: number, next: RoundDraft) => setRounds((items) => items.map((r, i) => i === index ? next : r));
  const updateQuestion = (ri: number, qi: number, next: QuestionDraft) => {
    const round = rounds[ri];
    updateRound(ri, { ...round, questions: round.questions.map((q, i) => i === qi ? next : q) });
  };

  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setSaving(true); setError(null);
    const body = {
      title, description: description || null, instructions: instructions || null,
      duration_minutes: duration,
      deadline: deadline ? new Date(deadline).toISOString() : null,
      eligible_batches: batches.split(",").map((x) => x.trim()).filter(Boolean),
      eligible_branches: branches.split(",").map((x) => x.trim()).filter(Boolean),
      rounds: rounds.map((round) => ({
        title: round.title,
        questions: round.questions.map((q) => ({
          question_text: q.question_text, question_type: q.question_type,
          mcq_options: q.question_type === "mcq" ? q.mcq_options : null,
          mcq_correct_index: q.question_type === "mcq" ? q.mcq_correct_index : null,
          max_score: q.max_score,
        })),
      })),
    };
    try {
      await institutionApi(
        interviewId ? `${institutionId}/interviews/${interviewId}` : `${institutionId}/interviews`,
        { method: interviewId ? "PUT" : "POST", body: JSON.stringify(body) }
      );
      router.push("/institution");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the interview");
    } finally { setSaving(false); }
  };

  if (!institutionId) return <div className="p-10 text-center">Missing institution selection. <Link className="text-primary" href="/institution">Return to institution workspace.</Link></div>;

  return (
    <div className="min-h-screen px-5 py-14"><form onSubmit={save} className="max-w-5xl mx-auto space-y-6">
      <div><Link href="/institution" className="text-sm text-primary">← Institution workspace</Link><h1 className="text-3xl font-extrabold mt-3">{interviewId ? "Edit interview" : "Create institution interview"}</h1><p className="text-muted-foreground mt-2">Questions are faculty-defined and become immutable after publication.</p></div>
      {error && <div className="p-4 border border-red-500/30 bg-red-500/10 text-red-400 rounded-xl">{error}</div>}
      {locked && <div className="p-4 border border-amber-500/30 bg-amber-500/10 text-amber-400 rounded-xl">This interview is published. Its questions and scoring are locked.</div>}
      <fieldset disabled={locked} className="space-y-6 disabled:opacity-70">
        <section className="panel grid md:grid-cols-2 gap-4">
          <label className="md:col-span-2">Title<input required value={title} onChange={(e)=>setTitle(e.target.value)} className="field" /></label>
          <label className="md:col-span-2">Description<textarea value={description} onChange={(e)=>setDescription(e.target.value)} className="field min-h-20" /></label>
          <label className="md:col-span-2">Student instructions<textarea value={instructions} onChange={(e)=>setInstructions(e.target.value)} className="field min-h-20" /></label>
          <label>Duration in minutes<input required min={1} max={480} type="number" value={duration} onChange={(e)=>setDuration(Number(e.target.value))} className="field" /></label>
          <label>Deadline (optional)<input type="datetime-local" value={deadline} onChange={(e)=>setDeadline(e.target.value)} className="field" /></label>
          <label>Eligible batches (comma-separated)<input value={batches} onChange={(e)=>setBatches(e.target.value)} placeholder="2026, 2027" className="field" /></label>
          <label>Eligible branches (comma-separated)<input value={branches} onChange={(e)=>setBranches(e.target.value)} placeholder="CSE, ECE" className="field" /></label>
        </section>
        {rounds.map((round, ri) => <section key={ri} className="panel space-y-4">
          <div className="flex gap-3 items-center"><input required value={round.title} onChange={(e)=>updateRound(ri,{...round,title:e.target.value})} className="field text-lg font-semibold" /><button type="button" disabled={rounds.length===1} onClick={()=>setRounds(rounds.filter((_,i)=>i!==ri))} className="p-3 text-red-400"><Trash2 className="w-5 h-5"/></button></div>
          {round.questions.map((q, qi) => <div key={qi} className="rounded-xl border border-border p-4 space-y-3">
            <div className="flex items-center justify-between"><span className="text-sm font-semibold">Question {qi+1}</span><button type="button" disabled={round.questions.length===1} onClick={()=>updateRound(ri,{...round,questions:round.questions.filter((_,i)=>i!==qi)})} className="text-red-400"><Trash2 className="w-4 h-4"/></button></div>
            <textarea required value={q.question_text} onChange={(e)=>updateQuestion(ri,qi,{...q,question_text:e.target.value})} placeholder="Enter the exact question students will see" className="field min-h-24" />
            <div className="grid md:grid-cols-2 gap-3"><label>Type<select value={q.question_type} onChange={(e)=>updateQuestion(ri,qi,{...q,question_type:e.target.value as QuestionDraft["question_type"]})} className="field"><option value="hr">HR free text</option><option value="technical">Technical free text</option><option value="mcq">MCQ</option></select></label><label>Maximum score<input type="number" min={1} max={100} value={q.max_score} onChange={(e)=>updateQuestion(ri,qi,{...q,max_score:Number(e.target.value)})} className="field" /></label></div>
            {q.question_type === "mcq" && <div className="grid md:grid-cols-2 gap-2">{q.mcq_options.map((option, oi)=><label key={oi} className="flex items-center gap-2"><input type="radio" checked={q.mcq_correct_index===oi} onChange={()=>updateQuestion(ri,qi,{...q,mcq_correct_index:oi})}/><input required value={option} onChange={(e)=>updateQuestion(ri,qi,{...q,mcq_options:q.mcq_options.map((x,i)=>i===oi?e.target.value:x)})} placeholder={`Option ${oi+1}`} className="field" /></label>)}</div>}
          </div>)}
          <button type="button" onClick={()=>updateRound(ri,{...round,questions:[...round.questions,newQuestion()]})} className="secondary"><Plus className="w-4 h-4"/>Add question</button>
        </section>)}
        <button type="button" onClick={()=>setRounds([...rounds,newRound()])} className="secondary"><Plus className="w-4 h-4"/>Add round</button>
      </fieldset>
      {!locked && <button disabled={saving} className="inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-primary text-primary-foreground font-bold"><Save className="w-4 h-4"/>{saving?"Saving…":"Save draft"}</button>}
    </form><style jsx>{`.panel{background:var(--card);border:1px solid var(--border);border-radius:1rem;padding:1.5rem}.field{display:block;width:100%;margin-top:.4rem;background:var(--background);border:1px solid var(--border);border-radius:.7rem;padding:.75rem;color:var(--foreground)}.secondary{display:inline-flex;align-items:center;gap:.4rem;border:1px solid var(--border);border-radius:.7rem;padding:.6rem .8rem;font-weight:600}`}</style></div>
  );
}

export default function BuilderPage() { return <Suspense fallback={<div className="p-10 text-center">Loading builder…</div>}><Builder /></Suspense>; }
