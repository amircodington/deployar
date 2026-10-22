/** Thin line icons (1.5px stroke, round caps, 20px grid), inline SVG so nothing loads from outside. */
const PATHS = {
  check: "M5 10.5l3.2 3.2L15 7",
  x: "M6 6l8 8M14 6l-8 8",
  info: "M10 9v5M10 6.2v.1M10 17.5a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15z",
  hand: "M7 10V5.5a1.5 1.5 0 0 1 3 0V9m0-1.5a1.5 1.5 0 0 1 3 0V9m0-.5a1.5 1.5 0 0 1 3 0V12a5.5 5.5 0 0 1-5.5 5.5H10A5 5 0 0 1 5.6 15L4 12a1.4 1.4 0 0 1 2.4-1.5L7 11.5",
  arrow: "M15 10H5m0 0l4-4m-4 4l4 4",
  settings: "M10 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM16 10l1.5-1-1.5-2.6-1.8.4a5.5 5.5 0 0 0-1.3-.8L12.5 4h-3l-.4 1.9a5.5 5.5 0 0 0-1.3.8L6 6.4 4.5 9 6 10l-1.5 1L6 13.6l1.8-.4c.4.3.8.6 1.3.8L9.5 16h3l.4-1.9c.5-.2.9-.5 1.3-.8l1.8.4L17.5 11z",
} as const;

export function Icon({ name, size = 20, className = "" }: { name: keyof typeof PATHS; size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" aria-hidden="true" className={className}>
      <path d={PATHS[name]} stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
