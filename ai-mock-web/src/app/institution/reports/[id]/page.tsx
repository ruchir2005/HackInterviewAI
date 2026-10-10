"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { institutionApi, InstitutionAttempt } from "@/app/lib/institutionApi";

interface ReportRow { user_id:string; name:string|null; email:string; batch:string|null; branch:string|null; attempt:{id:string;status:string;score:number|null}|null }
interface Reports { interview:{id:string;title:string}; assigned_students:number; completed_count:number; students:ReportRow[] }

function ReportsView() {
  const { id } = useParams<{id:string}>();
  const institutionId = useSearchParams().get("institutionId") || "";
  const [report,setReport]=useState<Reports|null>(null); const [selected,setSelected]=useState<InstitutionAttempt|null>(null); const [error,setError]=useState<string|null>(null);
  const load=useCallback(()=>institutionApi<Reports>(`${institutionId}/interviews/${id}/reports`).then(setReport).catch((e)=>setError(e.message)),[institutionId,id]);
  useEffect(()=>{if(institutionId)load();},[institutionId,load]);
  const inspect=(attemptId:string)=>institutionApi<InstitutionAttempt>(`attempts/${attemptId}`).then(setSelected).catch((e)=>setError(e.message));
  const retry=async()=>{if(!selected)return;try{setSelected(await institutionApi<InstitutionAttempt>(`${institutionId}/attempts/${selected.id}/retry-evaluation`,{method:"POST"}));load();}catch(e){setError(e instanceof Error?e.message:"Retry failed")}};
  if(!institutionId)return <div className="p-10 text-center">Missing institution context.</div>;
  return <div className="min-h-screen px-5 py-14"><div className="max-w-6xl mx-auto space-y-6"><Link href="/institution" className="text-primary">← Institution workspace</Link><div><h1 className="text-3xl font-bold">{report?.interview.title||"Student reports"}</h1>{report&&<p className="text-muted-foreground mt-2">{report.completed_count} completed · {report.assigned_students} eligible students</p>}</div>{error&&<div className="p-4 rounded-xl bg-red-500/10 text-red-400">{error}</div>}<div className="grid lg:grid-cols-[1fr_1.2fr] gap-6"><section className="bg-card border border-border rounded-2xl p-5"><h2 className="font-bold mb-4">Assigned students</h2><div className="space-y-2">{report?.students.map((row)=><button key={row.user_id} disabled={!row.attempt} onClick={()=>row.attempt&&inspect(row.attempt.id)} className="w-full text-left border border-border rounded-xl p-3 disabled:opacity-60"><div className="flex justify-between gap-3"><span className="font-semibold">{row.name||row.email}</span><span className="text-sm text-primary">{row.attempt?.score==null?row.attempt?.status||"not started":`${row.attempt.score}%`}</span></div><p className="text-xs text-muted-foreground">{row.email} · {row.batch||"Any batch"} · {row.branch||"Any branch"}</p></button>)}</div></section><section className="bg-card border border-border rounded-2xl p-5">{selected?<><div className="flex justify-between gap-3"><div><h2 className="font-bold">Individual report</h2><p className="text-sm text-muted-foreground">{selected.status.replace("_"," ")} · {selected.overall_score_percentage??"score pending"}</p></div>{selected.status==="evaluation_failed"&&<button onClick={retry} className="border border-border rounded-lg px-3 py-2 text-sm font-semibold">Retry AI evaluation</button>}</div>{selected.answers.map((answer)=>{const q=selected.interview.rounds.flatMap(r=>r.questions).find(q=>q.id===answer.question_id);return <div key={answer.id} className="border-t border-border py-4 mt-4"><p className="font-semibold">{q?.question_text}</p><p className="text-sm text-muted-foreground mt-2">Answer: {q?.question_type==="mcq"?q.mcq_options?.[answer.selected_option_index??-1]||"Unanswered":answer.answer_text||"Unanswered"}</p><p className="text-sm mt-2">Score: {answer.score??"Pending"} / {q?.max_score}</p><p className="text-sm text-muted-foreground">{answer.feedback}</p></div>})}</>:<p className="text-muted-foreground">Select a student attempt to inspect exact questions, answers, scores, and feedback.</p>}</section></div></div></div>;
}

export default function ReportsPage(){return <Suspense fallback={<div className="p-10 text-center">Loading reports…</div>}><ReportsView/></Suspense>}
