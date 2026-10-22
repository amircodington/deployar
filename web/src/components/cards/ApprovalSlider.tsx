"use client";

import { useRef } from "react";
import { Icon } from "@/components/Icon";
import { fa } from "@/lib/fa";

const PAD = 4;
const COMPLETE_AT = 0.8; // of the track
const FLICK = 0.6; // px/ms: a quick flick past 30% also counts

/** The one deliberate gesture in the product (brand: ApprovalSlider). Drag right→left (RTL) or
 * focus and press Enter. UX only: the server re-checks the signed one-time approval. */
export function ApprovalSlider({ onApprove, disabled = false }: { onApprove: () => void; disabled?: boolean }) {
  const track = useRef<HTMLDivElement>(null);
  const knob = useRef<HTMLButtonElement>(null);
  const label = useRef<HTMLSpanElement>(null);
  const drag = useRef<{ x: number; t: number; max: number; d: number } | null>(null);

  // Transform and opacity are written directly: no React render per pointer move (animation-performance).
  function place(d: number, animate: boolean) {
    const k = knob.current;
    if (!k || !label.current || !drag.current) return;
    k.style.transition = animate ? "transform 240ms var(--ease-out)" : "none";
    k.style.transform = `translateX(${-d}px)`;
    label.current.style.opacity = String(1 - d / drag.current.max);
  }

  function onPointerDown(e: React.PointerEvent<HTMLButtonElement>) {
    if (disabled || drag.current || !track.current || !knob.current) return; // ignore a second finger
    e.currentTarget.setPointerCapture(e.pointerId);
    const max = track.current.clientWidth - knob.current.offsetWidth - PAD * 2;
    drag.current = { x: e.clientX, t: performance.now(), max, d: 0 };
  }

  function onPointerMove(e: React.PointerEvent<HTMLButtonElement>) {
    const g = drag.current;
    if (!g) return;
    g.d = Math.min(Math.max(g.x - e.clientX, 0), g.max); // leftward is forward in RTL
    place(g.d, false);
  }

  function onPointerUp() {
    const g = drag.current;
    if (!g) return;
    const velocity = g.d / Math.max(performance.now() - g.t, 1);
    const done = g.d >= g.max * COMPLETE_AT || (velocity > FLICK && g.d > g.max * 0.3);
    place(done ? g.max : 0, true);
    drag.current = done ? g : null;
    if (done) onApprove();
  }

  return (
    <div
      ref={track}
      className={`relative h-14 rounded-full border border-ink-faint bg-raised p-1 ${disabled ? "opacity-60" : ""}`}
    >
      <span ref={label} className="pointer-events-none absolute inset-0 grid place-items-center text-[15px] text-ink-muted">
        {fa.approveHint}
      </span>
      <button
        ref={knob}
        type="button"
        disabled={disabled}
        aria-label={`${fa.approveHint}، ${fa.approveKeyboard}`}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !disabled) onApprove();
        }}
        style={{ touchAction: "pan-y" }}
        className="relative grid size-12 cursor-grab place-items-center rounded-full bg-gradient-to-l from-amber to-[#ffd08a] text-on-amber outline-none focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-2 focus-visible:ring-offset-amber-soft active:cursor-grabbing"
      >
        <Icon name="arrow" />
      </button>
    </div>
  );
}
