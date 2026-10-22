"use client";

import { useId, useState } from "react";
import { clockFa } from "@/lib/persian";

const W = 600;
const H = 160;

/** One series, one axis (dataviz): 2px line over a soft area, recessive grid, crosshair + tooltip on hover. */
export function LineChart({
  points,
  color,
  format,
  label,
}: {
  points: [number, number][];
  color: string;
  format: (v: number) => string;
  label: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const gradient = useId();
  if (points.length === 0) return null;

  const t0 = points[0][0];
  const t1 = points[points.length - 1][0];
  const max = Math.max(...points.map((p) => p[1])) * 1.15 || 1;
  const x = (t: number) => (t1 === t0 ? W / 2 : ((t - t0) / (t1 - t0)) * W);
  const y = (v: number) => H - (v / max) * H;
  const line = points.map(([t, v], i) => `${i ? "L" : "M"}${x(t).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const area = `${line}L${x(t1)},${H}L${x(t0)},${H}Z`;
  const h = hover === null ? null : points[hover];

  const onMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const t = t0 + ((e.clientX - r.left) / r.width) * (t1 - t0);
    let best = 0;
    for (let i = 1; i < points.length; i++) if (Math.abs(points[i][0] - t) < Math.abs(points[best][0] - t)) best = i;
    setHover(best);
  };

  return (
    <div dir="ltr" className="relative" onPointerMove={onMove} onPointerLeave={() => setHover(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className="reveal-x block h-40 w-full" role="img" aria-label={label}>
        <defs>
          <linearGradient id={gradient} x1="0" x2="0" y1="0" y2="1">
            <stop offset="0" stopColor={color} stopOpacity="0.28" />
            <stop offset="1" stopColor={color} stopOpacity="0" />
          </linearGradient>
        </defs>
        {[0.25, 0.5, 0.75].map((f) => (
          <line key={f} x1="0" x2={W} y1={H * f} y2={H * f} stroke="var(--line)" strokeDasharray="2 6" vectorEffect="non-scaling-stroke" />
        ))}
        <path d={area} fill={`url(#${gradient})`} />
        <path d={line} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
        {h && <line x1={x(h[0])} x2={x(h[0])} y1="0" y2={H} stroke="var(--ink-faint)" vectorEffect="non-scaling-stroke" />}
      </svg>
      {h && (
        <>
          <span
            className="pointer-events-none absolute size-2.5 -translate-x-1/2 -translate-y-1/2 rounded-full ring-2 ring-[var(--card)]"
            style={{ left: `${(x(h[0]) / W) * 100}%`, top: `${(y(h[1]) / H) * 100}%`, background: color }}
          />
          <span
            dir="rtl"
            className="pointer-events-none absolute top-0 z-10 whitespace-nowrap rounded-[12px] bg-raised px-3 py-1.5 text-[12px] shadow-shell"
            style={{
              left: `${(x(h[0]) / W) * 100}%`,
              transform: `translateX(${x(h[0]) > W * 0.7 ? "calc(-100% - 10px)" : "10px"})`,
            }}
          >
            <span className="block font-medium text-ink">{format(h[1])}</span>
            <span className="text-ink-faint">{clockFa(new Date(h[0] * 1000).toISOString())}</span>
          </span>
        </>
      )}
      <div className="mt-1 flex justify-between text-[11px] text-ink-faint">
        <span>{clockFa(new Date(t0 * 1000).toISOString())}</span>
        <span>{clockFa(new Date(t1 * 1000).toISOString())}</span>
      </div>
    </div>
  );
}
