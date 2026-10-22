"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AuthGate } from "@/components/AuthGate";
import { AgentError, api } from "@/lib/api";
import { fa } from "@/lib/fa";

/** Tokens are pasted here, never in chat (hard rule 2): posted straight to the agent, checked, encrypted. */
function LiaraForm() {
  const [token, setToken] = useState("");
  const [team, setTeam] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.liaraConnection().then(
      (c) => setStatus(`${fa.connected(c.token_last4)}${c.account ? ` · ${c.account}` : ""}`),
      () => {},
    );
  }, []);

  return (
    <form
      className="rounded-[24px] bg-card p-6"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
          const r = await api.connectLiara(token, team);
          setToken("");
          setStatus(`${fa.connected(r.token_last4)}${r.account ? ` · ${r.account}` : ""}`);
        } catch (err) {
          setStatus(err instanceof AgentError ? err.message : fa.connectionLost);
        } finally {
          setBusy(false);
        }
      }}
    >
      <label htmlFor="liara" className="mb-2 block text-lg font-medium">
        {fa.liaraToken}
      </label>
      <p className="mb-4 text-[13px] text-ink-muted">{fa.liaraTokenHint}</p>
      <input
        id="liara"
        type="password"
        autoComplete="off"
        spellCheck={false}
        value={token}
        onChange={(e) => setToken(e.target.value)}
        className="mono mb-4 min-h-12 w-full rounded-[16px] border border-ink-faint bg-raised px-4 outline-none focus-visible:border-amber"
      />
      <label htmlFor="team" className="mb-2 block text-[15px]">
        {fa.teamId}
      </label>
      <p className="mb-2 text-[13px] text-ink-muted">{fa.teamIdHint}</p>
      <input
        id="team"
        autoComplete="off"
        spellCheck={false}
        value={team}
        onChange={(e) => setTeam(e.target.value)}
        className="mono mb-6 min-h-12 w-full rounded-[16px] border border-ink-faint bg-raised px-4 outline-none focus-visible:border-amber"
      />
      <button
        type="submit"
        disabled={!token || busy}
        className="pressable min-h-12 rounded-full bg-ink px-6 text-[15px] font-medium text-ground disabled:opacity-40"
      >
        {busy ? fa.approving : fa.save}
      </button>
      {status && <p className="mt-4 text-[13px] text-ink-muted">{status}</p>}
    </form>
  );
}

export default function Connections() {
  return (
    <AuthGate>
      <main className="mx-auto max-w-xl px-4 py-[calc(24px+env(safe-area-inset-top,0px))]">
        <Link href="/" className="pressable mb-6 inline-flex min-h-11 items-center rounded-full px-3 text-ink-muted hover:bg-raised">
          {fa.back}
        </Link>
        <h1 className="mb-6 text-2xl font-bold">{fa.settings}</h1>
        <LiaraForm />
      </main>
    </AuthGate>
  );
}
