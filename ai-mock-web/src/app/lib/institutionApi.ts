export type InstitutionRole = "institution_admin" | "faculty" | "student";

export interface Membership {
  membership_id: string;
  institution_id: string;
  institution_name: string;
  institution_slug: string;
  role: InstitutionRole;
  batch: string | null;
  branch: string | null;
}

export interface InstitutionQuestion {
  id: string;
  question_text: string;
  question_type: "hr" | "technical" | "mcq";
  position: number;
  mcq_options: string[] | null;
  mcq_correct_index?: number;
  max_score: number;
}

export interface InstitutionRound {
  id: string;
  title: string;
  position: number;
  questions: InstitutionQuestion[];
}

export interface InstitutionInterview {
  id: string;
  institution_id: string;
  title: string;
  description: string | null;
  instructions: string | null;
  duration_minutes: number;
  deadline: string | null;
  eligible_batches: string[];
  eligible_branches: string[];
  status: "draft" | "published";
  published_at: string | null;
  rounds: InstitutionRound[];
  attempt?: { id: string; status: string; expires_at: string; score: number | null } | null;
  attempt_count?: number;
}

export interface AttemptAnswer {
  id: string;
  question_id: string;
  answer_text: string | null;
  selected_option_index: number | null;
  score: number | null;
  feedback: string | null;
  evaluation_status: string;
}

export interface InstitutionAttempt {
  id: string;
  interview_id: string;
  student_user_id: string;
  status: string;
  started_at: string;
  expires_at: string;
  submitted_at: string | null;
  overall_score_percentage: number | null;
  server_time: string;
  interview: InstitutionInterview;
  answers: AttemptAnswer[];
}

export class InstitutionApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

export async function institutionApi<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api/institution/${path.replace(/^\//, "")}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new InstitutionApiError(data?.detail || `Request failed (HTTP ${response.status})`, response.status);
  }
  return data as T;
}
