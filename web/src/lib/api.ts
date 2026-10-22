/** Typed client for the agent (ARCHITECTURE.md §8). Same-origin: /api is rewritten to the agent. */

export type RunStatus = "queued" | "running" | "awaiting_approval" | "succeeded" | "failed" | "cancelled";
export type Risk = "read" | "sensitive" | "human_only";
export type StepStatus = "pending" | "running" | "blocked" | "done" | "failed" | "skipped";

export interface ApiError {
  code: string;
  message_fa: string;
  detail?: string;
}

export class AgentError extends Error {
  constructor(
    public status: number,
    public error: ApiError,
  ) {
    super(error.message_fa);
  }
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(path, {
    ...init,
    credentials: "same-origin",
    headers: { "content-type": "application/json", ...init.headers },
  });
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) {
    throw new AgentError(res.status, body?.error ?? { code: `http_${res.status}`, message_fa: "خطای ارتباط با دستیار" });
  }
  return body as T;
}

/** Every block carries where and when it came from (hard rule 3). */
export interface Sourced {
  source: string;
  observed_at?: string;
}
export interface LiaraApp {
  name: string;
  type: string | null;
  status: string | null;
  plan: string | null;
  deployed: boolean | null;
}
export interface Dashboard {
  observed_at: string;
  liara: null | {
    token_last4: string;
    team_id: string | null;
    account: string | null;
    verified_at: string;
    balance?: Sourced & { toman: number | null };
    apps?: Sourced & { items: LiaraApp[] };
    error?: ApiError;
  };
  github: null | { login: string; token_last4: string; verified_at: string };
}
export interface LogLine {
  ts: string | null;
  type: string | null;
  message: string | null;
}
export interface Monitor {
  name: string;
  minutes: number;
  observed_at: string;
  status: Sourced & { status: string | null; plan: string | null; scale: number | null; type: string | null };
  logs: Sourced & { lines: LogLine[] };
  metrics: null | (Sourced & { memory: [number, number][]; cpu: [number, number][] });
  releases: Sourced & { current: string | null; items: { id: string; state: string; created_at: string }[] };
}

export const api = {
  dashboard: () => call<Dashboard>("/api/dashboard"),
  monitor: (name: string, minutes: number) =>
    call<Monitor>(`/api/apps/${encodeURIComponent(name)}/monitor?minutes=${minutes}`),
  me: () => call<{ user_id: string }>("/api/session"),
  login: (passphrase: string) =>
    call<{ user_id: string }>("/api/session", { method: "POST", body: JSON.stringify({ passphrase }) }),
  startRun: (body: { text: string; project_id?: string; conversation_id?: string; mode?: string }) =>
    call<{ run_id: string; conversation_id: string }>("/api/runs", { method: "POST", body: JSON.stringify(body) }),
  decide: (approvalId: string, decision: "approve" | "reject", signature: string) =>
    call<{ status: string }>(`/api/approvals/${approvalId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, signature }),
    }),
  connectLiara: (token: string, team_id?: string) =>
    call<{ id: string; token_last4: string; account: string | null }>("/api/connections/liara", {
      method: "POST",
      body: JSON.stringify({ token, team_id: team_id || null }),
    }),
  connectGithub: (token: string) =>
    call<{ id: string; token_last4: string; login: string }>("/api/connections/github", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),
  envValue: (projectId: string, key: string, value: string) =>
    call<{ key: string; value_ref: string }>(`/api/projects/${projectId}/env-values`, {
      method: "POST",
      body: JSON.stringify({ key, value }),
    }),
  githubConnection: () => call<{ id: string; token_last4: string; login: string }>("/api/connections/github"),
  liaraConnection: () =>
    call<{ id: string; token_last4: string; team_id: string | null; account: string | null }>("/api/connections/liara"),
};
