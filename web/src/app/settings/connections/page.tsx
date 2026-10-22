"use client";

import { useState } from "react";
import { AppShell } from "@/components/AppShell";
import { AuthGate } from "@/components/AuthGate";
import { Icon } from "@/components/Icon";
import { CopyCommand, Skeleton, SourceTag, StatusChip } from "@/components/ui";
import { AgentError, api, type Dashboard } from "@/lib/api";
import { fa } from "@/lib/fa";
import { toman } from "@/lib/money";
import { relativeFa } from "@/lib/persian";
import { useDashboard } from "@/lib/useDashboard";

const INPUT =
  "mono min-h-12 w-full rounded-[16px] border border-line bg-ground px-4 outline-none transition-colors duration-150 focus-visible:border-amber";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-h-11 items-center justify-between gap-4 border-b border-line/60 py-2 last:border-0">
      <dt className="text-[13px] text-ink-muted">{label}</dt>
      <dd className="min-w-0 truncate text-[14px]">{children}</dd>
    </div>
  );
}

function Masked({ last4 }: { last4: string }) {
  return (
    <span className="mono text-ink">
      <span className="text-ink-faint">••••••••</span>
      {last4}
    </span>
  );
}

/** One service: what is saved now (clearly), and a form that opens only to add or replace the token. */
function ConnectionCard({
  title,
  icon,
  connected,
  details,
  steps,
  form,
  index,
}: {
  title: string;
  icon: "box" | "git";
  connected: boolean | null;
  details: React.ReactNode;
  steps: React.ReactNode;
  form: (close: () => void) => React.ReactNode;
  index: number;
}) {
  const [editing, setEditing] = useState(false);
  const open = connected === false || editing;
  return (
    <section className="tile-in rounded-[28px] bg-card p-5 md:p-6" style={{ "--i": index } as React.CSSProperties}>
      <header className="mb-4 flex items-center gap-3">
        <span className="grid size-11 place-items-center rounded-full bg-raised">
          <Icon name={icon} />
        </span>
        <h2 className="flex-1 text-lg font-medium">{title}</h2>
        {connected === null ? (
          <Skeleton className="h-6 w-16" />
        ) : connected ? (
          <StatusChip tone="ok">{fa.connectedChip}</StatusChip>
        ) : (
          <StatusChip tone="off">{fa.notConnected}</StatusChip>
        )}
      </header>

      {connected === null ? (
        <div className="flex flex-col gap-3">
          <Skeleton className="h-5 w-full" />
          <Skeleton className="h-5 w-2/3" />
        </div>
      ) : (
        connected && <dl className="rounded-[18px] bg-raised/60 px-4">{details}</dl>
      )}

      <div className="disclose" data-open={open}>
        <div>
          <div className={connected ? "pt-5" : ""}>
            <ol className="mb-4 flex flex-col gap-2 text-[14px] text-ink-muted">{steps}</ol>
            {form(() => setEditing(false))}
          </div>
        </div>
      </div>

      {connected && (
        <button
          type="button"
          onClick={() => setEditing((e) => !e)}
          aria-expanded={editing}
          className="pressable mt-4 inline-flex min-h-11 items-center gap-2 rounded-full bg-raised px-4 text-[14px] hover:bg-line"
        >
          <Icon name={editing ? "x" : "key"} size={18} />
          {editing ? fa.cancel : fa.replaceToken}
        </button>
      )}
    </section>
  );
}

function Step({ n, children }: { n: number; children: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span className="grid size-6 shrink-0 place-items-center rounded-full bg-raised text-[12px] text-ink">
        {new Intl.NumberFormat("fa-IR").format(n)}
      </span>
      <span className="flex-1 pt-0.5 leading-6">{children}</span>
    </li>
  );
}

function SaveButton({ busy, disabled, ok }: { busy: boolean; disabled: boolean; ok: boolean }) {
  return (
    <button
      type="submit"
      disabled={disabled || busy}
      className="pressable inline-flex min-h-12 min-w-32 items-center justify-center gap-2 rounded-full bg-ink px-6 text-[15px] font-medium text-ground disabled:opacity-40"
    >
      <span key={busy ? "b" : ok ? "o" : "s"} className="swap inline-flex items-center gap-2">
        {busy ? (
          <>
            <span className="spinner size-4 rounded-full border-[1.5px] border-ground border-t-transparent" />
            {fa.checking}
          </>
        ) : ok ? (
          <>
            <Icon name="check" size={18} />
            {fa.saved}
          </>
        ) : (
          fa.save
        )}
      </span>
    </button>
  );
}

function useSubmit(run: () => Promise<unknown>, done: () => void) {
  const [busy, setBusy] = useState(false);
  const [ok, setOk] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: React.FormEvent, close: () => void) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await run();
      setOk(true);
      setTimeout(() => setOk(false), 1800);
      close();
      done();
    } catch (err) {
      setError(err instanceof AgentError ? err.message : fa.connectionLost);
    } finally {
      setBusy(false);
    }
  };
  return { busy, ok, error, submit };
}

function LiaraCard({ data, reload }: { data: Dashboard | null; reload: () => Promise<void> }) {
  const l = data?.liara;
  const [token, setToken] = useState("");
  const [team, setTeam] = useState("");
  const s = useSubmit(
    () => api.connectLiara(token, team),
    () => {
      setToken("");
      setTeam("");
      reload();
    },
  );
  return (
    <ConnectionCard
      index={0}
      title={fa.liaraTitle}
      icon="box"
      connected={data ? Boolean(l) : null}
      details={
        l && (
          <>
            <Row label={fa.account}>{l.account ?? "—"}</Row>
            <Row label={fa.token}>
              <Masked last4={l.token_last4} />
            </Row>
            <Row label={fa.team}>{l.team_id ? <span className="mono">{l.team_id}</span> : fa.personal}</Row>
            <Row label={l.team_id ? fa.teamCredit : fa.accountCredit}>
              {l.balance?.toman != null ? (
                <span className="flex flex-col items-end">
                  <span>{toman(l.balance.toman)}</span>
                  <SourceTag source={l.balance.source} at={l.balance.observed_at} />
                </span>
              ) : (
                <span className="text-red">{l.error?.message_fa ?? "—"}</span>
              )}
            </Row>
            <Row label={fa.lastChecked}>{relativeFa(l.verified_at)}</Row>
          </>
        )
      }
      steps={fa.liaraSteps.map((t, i) => (
        <Step key={t} n={i + 1}>
          {t}
        </Step>
      ))}
      form={(c) => (
        <form
          onSubmit={(e) => s.submit(e, c)}
          className="flex flex-col gap-3"
        >
          <label htmlFor="liara" className="text-[13px] text-ink-muted">
            {fa.liaraToken}
          </label>
          <input id="liara" type="password" autoComplete="off" spellCheck={false} value={token}
            onChange={(e) => setToken(e.target.value)} className={INPUT} />
          <label htmlFor="team" className="text-[13px] text-ink-muted">
            {fa.teamId}
          </label>
          <input id="team" autoComplete="off" spellCheck={false} value={team} placeholder={l?.team_id ?? ""}
            onChange={(e) => setTeam(e.target.value)} className={INPUT} />
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <SaveButton busy={s.busy} ok={s.ok} disabled={!token} />
            {s.error && <p className="rise text-[13px] text-red">{s.error}</p>}
          </div>
        </form>
      )}
    />
  );
}

function GithubCard({ data, reload }: { data: Dashboard | null; reload: () => Promise<void> }) {
  const g = data?.github;
  const [token, setToken] = useState("");
  const s = useSubmit(
    () => api.connectGithub(token),
    () => {
      setToken("");
      reload();
    },
  );
  return (
    <ConnectionCard
      index={1}
      title={fa.githubTitle}
      icon="git"
      connected={data ? Boolean(g) : null}
      details={
        g && (
          <>
            <Row label={fa.account}>
              <span className="mono">{g.login}</span>
            </Row>
            <Row label={fa.token}>
              <Masked last4={g.token_last4} />
            </Row>
            <Row label={fa.lastChecked}>{relativeFa(g.verified_at)}</Row>
          </>
        )
      }
      steps={
        <>
          <Step n={1}>
            {fa.githubSteps[0]}
            <span className="mt-2 block">
              <CopyCommand command="gh auth token | pbcopy" />
            </span>
          </Step>
          <Step n={2}>{fa.githubSteps[1]}</Step>
        </>
      }
      form={(c) => (
        <form
          onSubmit={(e) => s.submit(e, c)}
          className="flex flex-col gap-3"
        >
          <label htmlFor="github" className="text-[13px] text-ink-muted">
            {fa.githubToken}
          </label>
          <input id="github" type="password" autoComplete="off" spellCheck={false} value={token}
            onChange={(e) => setToken(e.target.value)} className={INPUT} />
          <div className="mt-1 flex flex-wrap items-center gap-3">
            <SaveButton busy={s.busy} ok={s.ok} disabled={!token} />
            {s.error && <p className="rise text-[13px] text-red">{s.error}</p>}
          </div>
        </form>
      )}
    />
  );
}

function Connections() {
  const { data, reload } = useDashboard();
  return (
    <main className="mx-auto w-full max-w-3xl px-4 pb-16 pt-4 md:px-8">
      <p className="text-[32px] font-light leading-10 text-ink-faint">{fa.settingsLight}</p>
      <h1 className="mb-3 text-[32px] font-extrabold leading-10">{fa.settings}</h1>
      <p className="mb-8 max-w-xl text-[14px] leading-6 text-ink-muted">{fa.connectionsLead}</p>
      <div className="grid gap-4 md:grid-cols-2 md:items-start">
        <LiaraCard data={data} reload={reload} />
        <GithubCard data={data} reload={reload} />
      </div>
    </main>
  );
}

export default function Page() {
  return (
    <AuthGate>
      <AppShell>
        <Connections />
      </AppShell>
    </AuthGate>
  );
}
