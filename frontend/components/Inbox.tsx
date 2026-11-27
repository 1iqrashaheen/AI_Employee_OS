"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, classify, getEmails, getHealth, summarize } from "@/lib/api";
import { formatDate, senderAddress, senderName } from "@/lib/format";
import { ClassifyResult, Email, EmailSource, Priority, SummaryResult } from "@/lib/types";
import PriorityBadge from "./PriorityBadge";

type Analysis = { summary?: SummaryResult; classify?: ClassifyResult };
type Filter = "all" | Priority | "unanalyzed";
type Sort = "newest" | "priority";
type Busy = "summary" | "classify";

const STORAGE_KEY = "email-assistant-analysis-v1";
const ORDER: Record<Priority, number> = { High: 0, Medium: 1, Low: 2 };
const FILTERS: { id: Filter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "High", label: "High" },
  { id: "Medium", label: "Medium" },
  { id: "Low", label: "Low" },
  { id: "unanalyzed", label: "Not analyzed" },
];

export default function Inbox(props: {
  onReply: (email: Email) => void;
  source: EmailSource;
  gmailEmail: string | null; // the connected Gmail address, or null when Gmail is not connected
  onSourceChange: (source: EmailSource) => void;
  onOpenConnect: () => void;
}) {
  const { onReply, source, gmailEmail, onSourceChange, onOpenConnect } = props;
  const [emails, setEmails] = useState<Email[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [llmConfigured, setLlmConfigured] = useState<boolean | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<Record<string, Analysis>>({});
  const [busy, setBusy] = useState<Record<string, Busy | undefined>>({});
  const [errors, setErrors] = useState<Record<string, string | undefined>>({});
  const [batch, setBatch] = useState<{ done: number; total: number } | null>(null);
  const [batchError, setBatchError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [sort, setSort] = useState<Sort>("newest");
  const [restored, setRestored] = useState(false);

  // Load emails and backend status.
  const load = useCallback(async () => {
    setLoadError(null);
    setEmails(null);
    setSelectedId(null);
    setFilter("all");
    try {
      setEmails(await getEmails(source));
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : "Could not load emails.");
    }
    getHealth()
      .then((h) => setLlmConfigured(h.llm_configured))
      .catch(() => setLlmConfigured(null));
  }, [source]);

  useEffect(() => {
    load();
  }, [load]);

  // Remember analysis results between visits (per browser; storage can be unavailable).
  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) setAnalysis(JSON.parse(saved));
    } catch {
      /* ignore */
    }
    setRestored(true);
  }, []);
  useEffect(() => {
    if (!restored) return;
    try {
      // Results about real Gmail emails stay in memory only; they are not saved in the browser.
      const sampleOnly = Object.fromEntries(Object.entries(analysis).filter(([id]) => !id.startsWith("gmail:")));
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sampleOnly));
    } catch {
      /* ignore */
    }
  }, [analysis, restored]);

  const setBusyFor = (id: string, value: Busy | undefined) => setBusy((b) => ({ ...b, [id]: value }));
  const setErrorFor = (id: string, value: string | undefined) => setErrors((e) => ({ ...e, [id]: value }));

  const runSummary = useCallback(async (id: string) => {
    setBusyFor(id, "summary");
    setErrorFor(id, undefined);
    try {
      const summary = await summarize(id);
      setAnalysis((a) => ({ ...a, [id]: { ...a[id], summary } }));
    } catch (e) {
      setErrorFor(id, e instanceof Error ? e.message : "Summarize failed.");
    } finally {
      setBusyFor(id, undefined);
    }
  }, []);

  /** Returns an ApiError when the failure means every further call will fail too. */
  const runClassify = useCallback(async (id: string): Promise<ApiError | null> => {
    setBusyFor(id, "classify");
    setErrorFor(id, undefined);
    try {
      const result = await classify(id);
      setAnalysis((a) => ({ ...a, [id]: { ...a[id], classify: result } }));
      return null;
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError(-1, "Prioritize failed.");
      setErrorFor(id, err.message);
      return err.status === 503 || err.status === 0 ? err : null;
    } finally {
      setBusyFor(id, undefined);
    }
  }, []);

  const prioritizeAll = async () => {
    if (!emails) return;
    const todo = emails.filter((e) => !analysis[e.id]?.classify);
    if (todo.length === 0) return;
    setBatchError(null);
    setBatch({ done: 0, total: todo.length });
    let next = 0;
    let done = 0;
    let fatal: ApiError | null = null;
    const worker = async () => {
      while (next < todo.length && !fatal) {
        const email = todo[next++];
        const err = await runClassify(email.id);
        if (err) fatal = err;
        done++;
        setBatch({ done, total: todo.length });
      }
    };
    await Promise.all([worker(), worker(), worker()]);
    setBatch(null);
    if (fatal) setBatchError((fatal as ApiError).message);
  };

  const resetAnalysis = () => {
    setAnalysis({});
    setErrors({});
    setBatchError(null);
  };

  const visible = useMemo(() => {
    if (!emails) return [];
    const list = emails.filter((e) => {
      const c = analysis[e.id]?.classify;
      if (filter === "all") return true;
      if (filter === "unanalyzed") return !c;
      return c?.priority === filter;
    });
    return [...list].sort((a, b) => {
      if (sort === "priority") {
        const pa = analysis[a.id]?.classify?.priority;
        const pb = analysis[b.id]?.classify?.priority;
        const diff = (pa ? ORDER[pa] : 3) - (pb ? ORDER[pb] : 3);
        if (diff !== 0) return diff;
      }
      return new Date(b.date).getTime() - new Date(a.date).getTime();
    });
  }, [emails, analysis, filter, sort]);

  const selected = emails?.find((e) => e.id === selectedId) ?? null;
  const analyzedCount = emails ? emails.filter((e) => analysis[e.id]?.classify).length : 0;

  return (
    <div className="inbox">
      <header className="topbar">
        <div className="segmented" role="group" aria-label="Email source">
          <button aria-pressed={source === "sample"} onClick={() => onSourceChange("sample")} disabled={!!batch}>
            Sample emails
          </button>
          <button
            aria-pressed={source === "gmail"}
            onClick={() => (gmailEmail ? onSourceChange("gmail") : onOpenConnect())}
            disabled={!!batch}
            title={gmailEmail ? `Show the newest emails in ${gmailEmail}` : "Connect Gmail first"}
          >
            My Gmail
          </button>
        </div>
        {source === "gmail" && (
          <button className="btn" onClick={load} disabled={!!batch || emails === null}>
            Refresh
          </button>
        )}
        {batch ? (
          <span className="progress" role="status">
            Prioritizing {batch.done}/{batch.total}…
          </span>
        ) : (
          emails && (
            <span className="progress">
              {analyzedCount}/{emails.length} prioritized
            </span>
          )
        )}
        <button className="btn btn-primary" onClick={prioritizeAll} disabled={!emails || !!batch || analyzedCount === emails.length}>
          Prioritize all
        </button>
        <button className="btn" onClick={resetAnalysis} disabled={!!batch || Object.keys(analysis).length === 0}>
          Clear results
        </button>
      </header>

      {source === "gmail" && (
        <div className="banner banner-info" role="note">
          Showing the newest emails from {gmailEmail ?? "your Gmail"}. This app only reads your mailbox and cannot change or
          delete anything. Summarize and Prioritize send the email text to your AI provider.
        </div>
      )}
      {llmConfigured === false && (
        <div className="banner banner-warn" role="status">
          No AI model is configured on the backend, so summaries and priorities are unavailable. Set LLM_PROVIDER and
          LLM_API_KEY in .env and restart the backend (LLM_PROVIDER=mock works without a key for a demo).
        </div>
      )}
      {batchError && (
        <div className="banner banner-error" role="alert">
          Stopped prioritizing: {batchError}
        </div>
      )}

      <div className={`layout ${selected ? "has-selection" : ""}`}>
        <section className="list-pane" aria-label="Inbox">
          <div className="toolbar">
            {FILTERS.map((f) => (
              <button key={f.id} className="chip" aria-pressed={filter === f.id} onClick={() => setFilter(f.id)}>
                {f.label}
              </button>
            ))}
            <select aria-label="Sort emails" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
              <option value="newest">Newest first</option>
              <option value="priority">Priority first</option>
            </select>
          </div>

          {loadError ? (
            <div className="empty" role="alert">
              <p>{loadError}</p>
              <button className="btn" onClick={load}>
                Try again
              </button>
              {source === "gmail" && (
                <button className="btn" onClick={onOpenConnect}>
                  Open Connect
                </button>
              )}
            </div>
          ) : emails === null ? (
            <div className="empty" role="status">
              Loading emails…
            </div>
          ) : visible.length === 0 ? (
            <div className="empty">No emails match this filter.</div>
          ) : (
            <ul className="list">
              {visible.map((e) => {
                const c = analysis[e.id]?.classify;
                return (
                  <li key={e.id}>
                    <button className="row" aria-current={e.id === selectedId} onClick={() => setSelectedId(e.id)}>
                      <div className="row-top">
                        <span className="row-from">{senderName(e.from)}</span>
                        <span className="row-date">{formatDate(e.date)}</span>
                      </div>
                      <div className="row-subject">{e.subject}</div>
                      {busy[e.id] === "classify" ? (
                        <span className="badge badge-none">Analyzing…</span>
                      ) : (
                        <PriorityBadge priority={c?.priority} suspicious={c?.suspicious} />
                      )}
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <section className="detail-pane" aria-label="Email detail">
          {selected ? (
            <EmailDetail
              email={selected}
              analysis={analysis[selected.id]}
              busy={busy[selected.id]}
              error={errors[selected.id]}
              onBack={() => setSelectedId(null)}
              onSummarize={() => runSummary(selected.id)}
              onPrioritize={() => runClassify(selected.id)}
              onReply={() => onReply(selected)}
            />
          ) : (
            <div className="placeholder">Select an email to read it.</div>
          )}
        </section>
      </div>
    </div>
  );
}

function EmailDetail(props: {
  email: Email;
  analysis?: Analysis;
  busy?: Busy;
  error?: string;
  onBack: () => void;
  onSummarize: () => void;
  onPrioritize: () => void;
  onReply: () => void;
}) {
  const { email, analysis, busy, error } = props;
  const c = analysis?.classify;
  const s = analysis?.summary;
  const address = senderAddress(email.from);

  return (
    <article className="detail">
      <button className="btn back" onClick={props.onBack}>
        ← Inbox
      </button>
      <h2>{email.subject}</h2>
      <div className="meta">
        {senderName(email.from)}
        {address && ` <${address}>`} · {formatDate(email.date)}
      </div>

      <div className="actions">
        <button className="btn btn-primary" onClick={props.onSummarize} disabled={!!busy}>
          {busy === "summary" ? "Summarizing…" : s ? "Summarize again" : "Summarize"}
        </button>
        <button className="btn" onClick={props.onPrioritize} disabled={!!busy}>
          {busy === "classify" ? "Prioritizing…" : c ? "Prioritize again" : "Prioritize"}
        </button>
        <button className="btn" onClick={props.onReply}>
          Reply with AI
        </button>
      </div>

      {error && (
        <div className="card card-error" role="alert">
          <h3>Something went wrong</h3>
          <p>{error}</p>
        </div>
      )}

      {busy === "summary" && (
        <div className="card" role="status" aria-label="Summarizing">
          <div className="skeleton" />
          <div className="skeleton short" />
        </div>
      )}
      {s && busy !== "summary" && (
        <div className="card">
          <h3>Summary</h3>
          <p>{s.summary}</p>
          {s.action_items.length > 0 ? (
            <>
              <h3 style={{ marginTop: 12 }}>Action items</h3>
              <ul>
                {s.action_items.map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </>
          ) : (
            <p className="note">No action items.</p>
          )}
          {s.truncated && <p className="note">This email was very long, so the middle part was skipped.</p>}
        </div>
      )}

      {c && busy !== "classify" && (
        <div className="card">
          <h3>Priority</h3>
          <PriorityBadge priority={c.priority} suspicious={c.suspicious} /> <span className="note">{c.category}</span>
          <p style={{ marginTop: 6 }}>{c.reason}</p>
        </div>
      )}

      {/* Email text is shown as plain text only. It is never rendered as HTML. */}
      <pre className="body-text">{email.body}</pre>
    </article>
  );
}
