export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_BASE_URL || 'http://127.0.0.1:8000/api/v1').replace(/\/$/, '');

export type ApiEnvelope<T> = { success: boolean; message: string; data: T; code?: string; errors?: {field:string;message:string}[]; request_id?: string };
export type User = { id:string; company_id:string; full_name:string; email:string; role:string; phone:string|null; is_active:boolean; last_login_at:string|null; created_at:string };
export type Company = { id:string; name:string; email:string; phone:string|null; plan:string; is_active:boolean };
export type AuthData = { access_token:string; refresh_token:string; token_type:string; expires_in:number; user?:User; company?:Company };

let accessToken: string | null = null;
let refreshToken: string | null = null;
let refreshPromise: Promise<boolean> | null = null;

export function setSession(tokens: AuthData) {
  accessToken = tokens.access_token;
  refreshToken = tokens.refresh_token;
  if (typeof window !== 'undefined') localStorage.setItem('ai_employee_refresh_token', tokens.refresh_token);
}
export function clearSession() {
  accessToken = null; refreshToken = null;
  if (typeof window !== 'undefined') { localStorage.removeItem('ai_employee_refresh_token'); localStorage.removeItem('ai_employee_user'); localStorage.removeItem('ai_employee_company'); }
}
export function saveIdentity(user?: User, company?: Company) {
  if (typeof window !== 'undefined') {
    if (user) localStorage.setItem('ai_employee_user', JSON.stringify(user));
    if (company) localStorage.setItem('ai_employee_company', JSON.stringify(company));
  }
}
export function getSavedIdentity(): {user:User|null;company:Company|null} {
  if (typeof window === 'undefined') return {user:null,company:null};
  try { return { user: JSON.parse(localStorage.getItem('ai_employee_user') || 'null'), company: JSON.parse(localStorage.getItem('ai_employee_company') || 'null') }; } catch { return {user:null,company:null}; }
}

async function refreshSession(): Promise<boolean> {
  if (refreshPromise) return refreshPromise;
  refreshPromise = (async () => {
    if (typeof window === 'undefined') return false;
    refreshToken = refreshToken || localStorage.getItem('ai_employee_refresh_token');
    if (!refreshToken) return false;
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({refresh_token:refreshToken}) });
      const body = await response.json();
      if (!response.ok || !body.success) { clearSession(); return false; }
      setSession(body.data as AuthData); return true;
    } catch { return false; }
    finally { refreshPromise = null; }
  })();
  return refreshPromise;
}

export async function initializeSession(): Promise<boolean> {
  if (typeof window === 'undefined') return false;
  refreshToken = localStorage.getItem('ai_employee_refresh_token');
  if (!refreshToken) return false;
  return refreshSession();
}

export async function apiRequest<T>(path:string, options:RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (options.body && !headers.has('Content-Type')) headers.set('Content-Type','application/json');
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  const response = await fetch(`${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`, {...options, headers, cache:'no-store'});
  const body = await response.json().catch(() => ({}));
  if (!response.ok || body.success === false) {
    if (response.status === 401 && body.code === 'TOKEN_EXPIRED' && retry && await refreshSession()) return apiRequest<T>(path, options, false);
    if (response.status === 401 && ['AUTH_REQUIRED','TOKEN_EXPIRED','TOKEN_INVALID','TOKEN_REVOKED'].includes(body.code)) clearSession();
    const error = new Error(body.message || `Request failed (${response.status})`) as Error & {code?:string;status?:number;fields?:{field:string;message:string}[];requestId?:string};
    error.code = body.code; error.status = response.status; error.fields = body.errors; error.requestId = body.request_id; throw error;
  }
  return body as T;
}

export async function login(email:string,password:string) { const r=await apiRequest<ApiEnvelope<AuthData>>('/auth/login',{method:'POST',body:JSON.stringify({email,password})},false); setSession(r.data); saveIdentity(r.data.user,r.data.company); return r.data; }
export async function register(input:{company_name:string;full_name:string;email:string;password:string}) { const r=await apiRequest<ApiEnvelope<AuthData>>('/auth/register',{method:'POST',body:JSON.stringify(input)},false); setSession(r.data); saveIdentity(r.data.user,r.data.company); return r.data; }
export async function fetchMe() { const r=await apiRequest<ApiEnvelope<{user:User;company:Company}>>('/auth/me'); saveIdentity(r.data.user,r.data.company); return r.data; }
export async function changePassword(current_password:string,new_password:string) { const r=await apiRequest<ApiEnvelope<AuthData>>('/auth/change-password',{method:'POST',body:JSON.stringify({current_password,new_password})}); setSession(r.data); return r.data; }
export async function logout() { try { await apiRequest('/auth/logout',{method:'POST'}); } catch { /* local logout remains available if this endpoint is not deployed yet */ } finally { clearSession(); } }
