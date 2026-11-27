import {
  ActivityEntry,
  API_URL,
  AuthStatus,
  ClassifyResult,
  DraftRecord,
  DraftSuggestion,
  Email,
  EmailSource,
  Health,
  SummaryResult,
  Tone,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

/** FastAPI sends a string for our own errors and a list for validation errors. Make both readable. */
function readDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { loc?: unknown[]; msg?: string };
    const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : "";
    return `${field ? field + ": " : ""}${first.msg ?? "Invalid value"}`;
  }
  return fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...init,
      headers: { "content-type": "application/json" },
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, `Cannot reach the backend at ${API_URL}. Is it running?`);
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      detail = readDetail((await res.json()).detail, detail);
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const getEmails = (source: EmailSource = "sample") => request<Email[]>(`/emails?source=${source}`);
export const getEmail = (id: string) => request<Email>(`/emails/${encodeURIComponent(id)}`);
export const getHealth = () => request<Health>("/health");
export const summarize = (emailId: string) => post<SummaryResult>("/summarize", { email_id: emailId });
export const classify = (emailId: string) => post<ClassifyResult>("/classify", { email_id: emailId });

export const generateDraft = (req: {
  instruction: string;
  tone: Tone;
  recipient: string | null;
  reply_to_email_id: string | null;
}) => post<DraftSuggestion>("/draft", req);

export const listDrafts = () => request<DraftRecord[]>("/drafts");
export const createDraft = (req: {
  subject: string;
  body: string;
  recipient: string | null;
  reply_to_email_id: string | null;
  instruction: string | null;
}) => post<DraftRecord>("/drafts", req);
export const saveDraft = (id: string, req: { subject: string; body: string; recipient: string | null }) =>
  request<DraftRecord>(`/drafts/${id}`, { method: "PUT", body: JSON.stringify(req) });
export const approveDraft = (id: string) => post<DraftRecord>(`/drafts/${id}/approve`);
export const revokeApproval = (id: string) => post<DraftRecord>(`/drafts/${id}/revoke-approval`);
export const sendDraft = (id: string) => post<DraftRecord>(`/drafts/${id}/send`);

export const getAuthStatus = () => request<AuthStatus>("/auth/status");
/** Asks the backend for the Google sign-in address. The caller then sends the browser there. */
export const startGoogleLogin = (allowSend = false) =>
  post<{ url: string }>(`/auth/google/login${allowSend ? "?send=true" : ""}`);
export const getActivity = () => request<ActivityEntry[]>("/activity?limit=50");
export const disconnectGoogle = () => post<{ disconnected: boolean; revoked_at_google: boolean }>("/auth/google/disconnect");
