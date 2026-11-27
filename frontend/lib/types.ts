export type Priority = "High" | "Medium" | "Low";
export type Status = "unread" | "read" | "draft" | "approved" | "sent";

export interface Email {
  id: string;
  thread_id: string;
  from: string;
  subject: string;
  body: string;
  date: string;
  summary: string | null;
  priority: Priority | null;
  status: Status;
}

export interface SummaryResult {
  summary: string;
  action_items: string[];
  truncated: boolean;
}

export interface ClassifyResult {
  priority: Priority;
  category: string;
  reason: string;
  suspicious: boolean;
  truncated: boolean;
}

export type Tone = "professional" | "friendly" | "formal" | "firm" | "apologetic" | "concise";
export const TONES: Tone[] = ["professional", "friendly", "formal", "firm", "apologetic", "concise"];

export interface DraftSuggestion {
  subject: string;
  body: string;
  recipient: string | null;
  status: string;
  notes: string[];
}

export type DraftStatus = "draft" | "approved" | "sent";

export interface DraftRecord {
  id: string;
  subject: string;
  body: string;
  recipient: string | null;
  reply_to_email_id: string | null;
  instruction: string | null;
  status: DraftStatus;
  created_at: string;
  updated_at: string;
  approved_at: string | null;
  sent_at: string | null;
  delivery: string | null; // "mock" (demo) or "gmail" (really sent)
  delivery_id: string | null;
  history: { at: string; event: string }[];
}

export type EmailSource = "sample" | "gmail";

export interface Health {
  status: string;
  mode: "sample" | "gmail";
  google_configured: boolean;
  google_connected: boolean;
  llm_configured: boolean;
  send_mode: "mock" | "real" | "needs_permission";
}

export interface AuthStatus {
  configured: boolean;
  missing: string[]; // names of the settings still missing in .env
  connected: boolean;
  email: string | null;
  scopes: string[];
  can_read: boolean;
  can_send: boolean;
  reauth_required: boolean; // the connection expired or was revoked: reconnect
  redirect_uri: string;
}

export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface ActivityEntry {
  at: string;
  event: string;
  label: string;
  draft_id?: string;
  to?: string | null;
  subject?: string;
  delivery?: string;
  detail?: string;
  account?: string;
}
