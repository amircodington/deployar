"use client";

import { useEffect, useState } from "react";
import { AgentError, api } from "@/lib/api";
import { fa } from "@/lib/fa";

/** Single-user passphrase login (BUILD.md defaults); everything else waits behind it. */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<"checking" | "in" | "out">("checking");
  const [pass, setPass] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.me().then(() => setState("in"), () => setState("out"));
  }, []);

  if (state === "checking") return <div className="min-h-dvh" />;
  if (state === "in") return <>{children}</>;

  return (
    <main className="grid min-h-dvh place-items-center px-4">
      <form
        className="rise w-full max-w-sm rounded-[36px] bg-shell p-8 shadow-shell"
        onSubmit={async (e) => {
          e.preventDefault();
          setError(null);
          try {
            await api.login(pass);
            setState("in");
          } catch (err) {
            setError(err instanceof AgentError ? err.message : fa.loginFailed);
          }
        }}
      >
        <p className="text-[32px] font-light leading-10 text-ink-faint">{fa.brand}</p>
        <h1 className="mb-6 text-[32px] font-extrabold leading-10">{fa.loginTitle}</h1>
        <label className="mb-2 block text-[13px] text-ink-muted" htmlFor="pass">
          {fa.passphrase}
        </label>
        <input
          id="pass"
          type="password"
          autoComplete="current-password"
          value={pass}
          onChange={(e) => setPass(e.target.value)}
          className="mb-2 min-h-12 w-full rounded-[16px] border border-ink-faint bg-raised px-4 outline-none focus-visible:border-amber"
        />
        <p className="mb-6 text-[13px] leading-5 text-ink-muted">
          {fa.loginHint.map((part, i) => (i % 2 ? <span key={i} className="mono"> {part} </span> : part))}
        </p>
        {error && <p className="mb-4 text-[13px] text-red">{error}</p>}
        <button type="submit" className="pressable min-h-12 w-full rounded-full bg-ink text-[15px] font-medium text-ground">
          {fa.enter}
        </button>
      </form>
    </main>
  );
}
