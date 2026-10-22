"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "@/components/Icon";
import { fa } from "@/lib/fa";

const NAV = [
  { href: "/", label: fa.nav.home, icon: "home" },
  { href: "/monitor", label: fa.nav.monitor, icon: "pulse" },
  { href: "/settings/connections", label: fa.nav.settings, icon: "plug" },
] as const;

/** The device shell (brand: one large rounded shell on a darker ground) with the three places of the app. */
export function AppShell({ children }: { children: React.ReactNode }) {
  const path = usePathname();
  return (
    <div className="mx-auto flex min-h-dvh max-w-[1320px] flex-col md:p-6">
      <div className="flex flex-1 flex-col bg-shell md:rounded-[36px] md:shadow-shell">
        <header className="flex items-center gap-3 px-4 pb-2 pt-[calc(14px+env(safe-area-inset-top,0px))] md:px-8 md:pt-7">
          <Link href="/" className="pressable flex items-center gap-2.5 rounded-full pe-2">
            <span className="grid size-9 place-items-center rounded-[12px] bg-amber text-on-amber" aria-hidden="true">
              <Icon name="box" size={18} />
            </span>
            <span className="text-[15px] font-bold">{fa.brand}</span>
          </Link>
          <span className="flex-1" />
          <nav className="flex gap-1 rounded-full bg-card p-1" aria-label={fa.brand}>
            {NAV.map((n) => {
              const active = n.href === "/" ? path === "/" || path.startsWith("/p/") : path.startsWith(n.href);
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  aria-current={active ? "page" : undefined}
                  className={`pressable flex min-h-10 items-center gap-1.5 rounded-full px-3 text-[14px] transition-colors duration-150 sm:px-4 ${
                    active ? "bg-raised text-ink" : "text-ink-muted hover:text-ink"
                  }`}
                >
                  <Icon name={n.icon} size={18} />
                  <span className={active ? "" : "hidden sm:inline"}>{n.label}</span>
                </Link>
              );
            })}
          </nav>
        </header>
        {children}
      </div>
    </div>
  );
}
