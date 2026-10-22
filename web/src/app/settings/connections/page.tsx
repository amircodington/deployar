"use client";

import Link from "next/link";
import { useState } from "react";
import { AuthGate } from "@/components/AuthGate";
import { AgentError, api } from "@/lib/api";
import { fa } from "@/lib/fa";

/** Tokens are pasted here, never in chat (hard rule 2). The Liara endpoint lands in B-08. */
export default function Connections() {
  const [token, setToken] = useState("");
  const [result, setResult] = useState<string | null>(null);
  return (
    <AuthGate>
      <main className="mx-auto max-w-xl px-4 py-[calc(24px+env(safe-area-inset-top,0px))]">
        <Link href="/" className="pressable mb-6 inline-flex min-h-11 items-center rounded-full px-3 text-ink-muted hover:bg-raised">
          {fa.back}
        </Link>
        <h1 className="mb-6 text-2xl font-bold">{fa.settings}</h1>
        <form
          className="rounded-[24px] bg-card p-6"
          onSubmit={async (e) => {
            e.preventDefault();
            setResult(null);
            try {
              const r = await api.connectLiara(token);
              setToken("");
              setResult(`…${r.token_last4}`);
            } catch (err) {
              setResult(err instanceof AgentError ? err.message : fa.connectionLost);
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
          <button type="submit" disabled={!token} className="pressable min-h-12 rounded-full bg-ink px-6 text-[15px] font-medium text-ground disabled:opacity-40">
            {fa.save}
          </button>
          {result && <p className="mt-4 text-[13px] text-ink-muted">{result}</p>}
        </form>
      </main>
    </AuthGate>
  );
}
