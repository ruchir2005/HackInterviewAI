"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Building2, ClipboardList, GraduationCap, Plus, RefreshCw, Users } from "lucide-react";
import {
  institutionApi,
  InstitutionInterview,
  Membership,
} from "@/app/lib/institutionApi";

interface Member {
  membership_id: string;
  email: string;
  name: string | null;
  role: string;
  batch: string | null;
  branch: string | null;
}

interface Dashboard {
  institution: { id: string; name: string };
  membership: { role: string; batch: string | null; branch: string | null };
  interviews: InstitutionInterview[];
  members?: Member[];
}

export default function InstitutionLandingPage() {
  const router = useRouter();
  const [memberships, setMemberships] = useState<Membership[]>([]);
  const [selectedId, setSelectedId] = useState("");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [memberForm, setMemberForm] = useState({ email: "", name: "", role: "student", batch: "", branch: "" });

  useEffect(() => {
    institutionApi<Membership[]>("memberships")
      .then((items) => {
        setMemberships(items);
        if (items.length) setSelectedId(items[0].institution_id);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const loadDashboard = async (institutionId: string) => {
    setError(null);
    try {
      setDashboard(await institutionApi<Dashboard>(`${institutionId}/dashboard`));
    } catch (err) {
      setDashboard(null);
      setError(err instanceof Error ? err.message : "Could not load the institution");
    }
  };

  useEffect(() => {
    if (selectedId) loadDashboard(selectedId);
  }, [selectedId]);

  const beginAttempt = async (interview: InstitutionInterview) => {
    if (interview.attempt) {
      router.push(`/institution/attempts/${interview.attempt.id}`);
      return;
    }
    try {
      const attempt = await institutionApi<{ id: string }>(
        `${selectedId}/interviews/${interview.id}/attempts`, { method: "POST" }
      );
      router.push(`/institution/attempts/${attempt.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start the interview");
    }
  };

  const publish = async (interviewId: string) => {
    try {
      await institutionApi(`${selectedId}/interviews/${interviewId}/publish`, { method: "POST" });
      await loadDashboard(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not publish the interview");
    }
  };

  const addMember = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await institutionApi(`${selectedId}/members`, {
        method: "POST",
        body: JSON.stringify({
          email: memberForm.email,
          name: memberForm.name || null,
          role: memberForm.role,
          batch: memberForm.batch || null,
          branch: memberForm.branch || null,
        }),
      });
      setMemberForm({ email: "", name: "", role: "student", batch: "", branch: "" });
      await loadDashboard(selectedId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not add the member");
    }
  };

  if (loading) return <CenteredMessage text="Loading your verified institution memberships…" />;
  if (!memberships.length) {
    return (
      <CenteredMessage
        title="No institution membership"
        text="Your signed-in account has not been added to an institution. Ask an institution administrator to add your Google account email, then return to this page. Selecting Institution Based or changing a URL cannot grant access."
      />
    );
  }

  const isStudent = dashboard?.membership.role === "student";
  const isAdmin = dashboard?.membership.role === "institution_admin";
  const ongoing = dashboard?.interviews.filter((i) => i.attempt?.status === "in_progress") || [];
  const completed = dashboard?.interviews.filter((i) => i.attempt && i.attempt.status !== "in_progress") || [];
  const available = dashboard?.interviews.filter((i) => !i.attempt) || [];

  return (
    <div className="min-h-screen px-5 py-16">
      <div className="max-w-6xl mx-auto space-y-8">
        <header className="flex flex-col md:flex-row md:items-end justify-between gap-5">
          <div>
            <p className="text-sm font-semibold text-primary mb-2">Institution Based Interviews</p>
            <h1 className="text-4xl font-extrabold text-foreground">{dashboard?.institution.name || "Your institution"}</h1>
            <p className="text-muted-foreground mt-2">Access is based on your verified membership and institution role.</p>
          </div>
          {memberships.length > 1 && (
            <label className="text-sm text-muted-foreground">
              Verified membership
              <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)} className="block mt-2 bg-card border border-border rounded-xl px-4 py-3 text-foreground">
                {memberships.map((m) => <option key={m.membership_id} value={m.institution_id}>{m.institution_name} · {m.role}</option>)}
              </select>
            </label>
          )}
        </header>

        {error && <div className="rounded-xl border border-red-500/30 bg-red-500/10 p-4 text-red-400">{error}</div>}
        {!dashboard && <CenteredMessage text="Loading institution workspace…" />}

        {dashboard && isStudent && (
          <>
            <div className="grid sm:grid-cols-3 gap-4">
              <Stat label="Eligible interviews" value={dashboard.interviews.length} icon={<ClipboardList />} />
              <Stat label="Ongoing" value={ongoing.length} icon={<RefreshCw />} />
              <Stat label="Completed" value={completed.length} icon={<GraduationCap />} />
            </div>
            <InterviewSection title="Ongoing attempts" empty="You have no ongoing attempts." items={ongoing} action={beginAttempt} />
            <InterviewSection title="Eligible published interviews" empty="No published interview is currently eligible for your batch and branch." items={available} action={beginAttempt} />
            <InterviewSection title="Completed results" empty="You have not completed an institution interview yet." items={completed} action={beginAttempt} />
          </>
        )}

        {dashboard && !isStudent && (
          <>
            <div className="grid sm:grid-cols-3 gap-4">
              <Stat label="Managed interviews" value={dashboard.interviews.length} icon={<ClipboardList />} />
              <Stat label="Students" value={(dashboard.members || []).filter((m) => m.role === "student").length} icon={<Users />} />
              <Stat label="Your role" value={dashboard.membership.role.replace("_", " ")} icon={<Building2 />} />
            </div>
            <section className="bg-card border border-border rounded-2xl p-6 shadow-md">
              <div className="flex items-center justify-between gap-4 mb-5">
                <div><h2 className="text-xl font-bold">Interview management</h2><p className="text-sm text-muted-foreground">Published questions and scoring are locked.</p></div>
                <Link href={`/institution/builder?institutionId=${selectedId}`} className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-primary text-primary-foreground font-semibold"><Plus className="w-4 h-4" />Create interview</Link>
              </div>
              <div className="space-y-3">
                {dashboard.interviews.map((item) => (
                  <div key={item.id} className="border border-border rounded-xl p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
                    <div><h3 className="font-semibold">{item.title}</h3><p className="text-sm text-muted-foreground">{item.status} · {item.duration_minutes} min · {item.attempt_count || 0} attempts</p></div>
                    <div className="flex flex-wrap gap-2">
                      {item.status === "draft" && <Link href={`/institution/builder?institutionId=${selectedId}&interviewId=${item.id}`} className="btn-secondary">Edit</Link>}
                      {item.status === "draft" && <button onClick={() => publish(item.id)} className="btn-secondary">Publish</button>}
                      <Link href={`/institution/reports/${item.id}?institutionId=${selectedId}`} className="btn-secondary">Student reports</Link>
                    </div>
                  </div>
                ))}
                {!dashboard.interviews.length && <p className="text-muted-foreground">No interviews created yet.</p>}
              </div>
            </section>

            {isAdmin && (
              <section className="bg-card border border-border rounded-2xl p-6 shadow-md">
                <h2 className="text-xl font-bold mb-1">Add a verified member</h2>
                <p className="text-sm text-muted-foreground mb-5">Only institution administrators can assign institution roles.</p>
                <form onSubmit={addMember} className="grid md:grid-cols-3 gap-3">
                  <input required type="email" placeholder="Google account email" value={memberForm.email} onChange={(e) => setMemberForm({...memberForm, email:e.target.value})} className="field" />
                  <input placeholder="Name (optional)" value={memberForm.name} onChange={(e) => setMemberForm({...memberForm, name:e.target.value})} className="field" />
                  <select value={memberForm.role} onChange={(e) => setMemberForm({...memberForm, role:e.target.value})} className="field"><option value="student">Student</option><option value="faculty">Faculty</option><option value="institution_admin">Institution admin</option></select>
                  <input placeholder="Batch (optional)" value={memberForm.batch} onChange={(e) => setMemberForm({...memberForm, batch:e.target.value})} className="field" />
                  <input placeholder="Branch (optional)" value={memberForm.branch} onChange={(e) => setMemberForm({...memberForm, branch:e.target.value})} className="field" />
                  <button className="rounded-xl bg-primary text-primary-foreground font-semibold px-4 py-3">Add member</button>
                </form>
              </section>
            )}
          </>
        )}
      </div>
      <style jsx>{`.field{background:var(--card);border:1px solid var(--border);border-radius:.75rem;padding:.75rem;color:var(--foreground)} :global(.btn-secondary){border:1px solid var(--border);border-radius:.65rem;padding:.55rem .8rem;font-size:.875rem;font-weight:600}`}</style>
    </div>
  );
}

function CenteredMessage({ title = "Institution interviews", text }: { title?: string; text: string }) {
  return <div className="min-h-[70vh] flex items-center justify-center px-5"><div className="max-w-xl text-center bg-card border border-border rounded-2xl p-10 shadow-md"><GraduationCap className="w-12 h-12 text-primary mx-auto mb-4"/><h1 className="text-2xl font-bold mb-3">{title}</h1><p className="text-muted-foreground leading-relaxed">{text}</p><Link href="/InterviewSelectionPage" className="inline-block mt-6 text-primary font-semibold">Back to interview types</Link></div></div>;
}

function Stat({ label, value, icon }: { label: string; value: string | number; icon: React.ReactNode }) {
  return <div className="bg-card border border-border rounded-2xl p-5 flex items-center gap-4"><span className="text-primary">{icon}</span><div><p className="text-2xl font-bold capitalize">{value}</p><p className="text-sm text-muted-foreground">{label}</p></div></div>;
}

function InterviewSection({ title, empty, items, action }: { title:string; empty:string; items:InstitutionInterview[]; action:(i:InstitutionInterview)=>void }) {
  return <section><h2 className="text-xl font-bold mb-4">{title}</h2><div className="grid md:grid-cols-2 gap-4">{items.map((item)=><article key={item.id} className="bg-card border border-border rounded-2xl p-6 shadow-md"><div className="flex justify-between gap-3"><h3 className="text-lg font-bold">{item.title}</h3><span className="text-xs text-primary font-semibold">{item.attempt?.status || "available"}</span></div><p className="text-sm text-muted-foreground mt-2">{item.description || "Faculty-configured interview"}</p><div className="text-xs text-muted-foreground mt-4 space-y-1"><p>Duration: {item.duration_minutes} minutes</p><p>Deadline: {item.deadline ? new Date(item.deadline).toLocaleString() : "No deadline"}</p></div><button onClick={()=>action(item)} className="mt-5 rounded-xl bg-primary text-primary-foreground px-4 py-2.5 font-semibold">{item.attempt?.status === "in_progress" ? "Resume attempt" : item.attempt ? "View result" : "View and start"}</button></article>)}{!items.length&&<p className="text-muted-foreground">{empty}</p>}</div></section>;
}
