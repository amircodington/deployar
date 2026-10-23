/** Thin line icons (1.5px stroke, round caps, 20px grid), inline SVG so nothing loads from outside. */
const PATHS = {
  check: "M5 10.5l3.2 3.2L15 7",
  x: "M6 6l8 8M14 6l-8 8",
  info: "M10 9v5M10 6.2v.1M10 17.5a7.5 7.5 0 1 0 0-15 7.5 7.5 0 0 0 0 15z",
  hand: "M7 10V5.5a1.5 1.5 0 0 1 3 0V9m0-1.5a1.5 1.5 0 0 1 3 0V9m0-.5a1.5 1.5 0 0 1 3 0V12a5.5 5.5 0 0 1-5.5 5.5H10A5 5 0 0 1 5.6 15L4 12a1.4 1.4 0 0 1 2.4-1.5L7 11.5",
  arrow: "M15 10H5m0 0l4-4m-4 4l4 4",
  settings: "M10 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5zM16 10l1.5-1-1.5-2.6-1.8.4a5.5 5.5 0 0 0-1.3-.8L12.5 4h-3l-.4 1.9a5.5 5.5 0 0 0-1.3.8L6 6.4 4.5 9 6 10l-1.5 1L6 13.6l1.8-.4c.4.3.8.6 1.3.8L9.5 16h3l.4-1.9c.5-.2.9-.5 1.3-.8l1.8.4L17.5 11z",
  home: "M3.5 9.5L10 4l6.5 5.5V16a1 1 0 0 1-1 1h-3.5v-4.5h-4V17H4.5a1 1 0 0 1-1-1z",
  pulse: "M2.5 10h3l2-5 3 10 2-5h5",
  plug: "M7 3v3.5M13 3v3.5M5 6.5h10V9a5 5 0 0 1-10 0zM10 14v3",
  wallet: "M3.5 6.5a2 2 0 0 1 2-2h8.5v2M3.5 6.5v8a2 2 0 0 0 2 2h11v-10zM13.5 11.5h.1",
  box: "M10 2.8l6.5 3.6v7.2L10 17.2l-6.5-3.6V6.4zM3.5 6.4L10 10l6.5-3.6M10 10v7.2",
  git: "M6 4v9M6 13a2 2 0 1 0 0 4 2 2 0 0 0 0-4zM14 7a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM14 7c0 4-8 3-8 6",
  copy: "M7 7V4.5A1.5 1.5 0 0 1 8.5 3h7A1.5 1.5 0 0 1 17 4.5v7a1.5 1.5 0 0 1-1.5 1.5H13M4.5 7h7A1.5 1.5 0 0 1 13 8.5v7a1.5 1.5 0 0 1-1.5 1.5h-7A1.5 1.5 0 0 1 3 15.5v-7A1.5 1.5 0 0 1 4.5 7z",
  key: "M12.5 3a4.5 4.5 0 1 1-3.9 6.7L3 15.3V17h2.5v-1.5H7V14h1.5l1.8-1.8A4.5 4.5 0 0 1 12.5 3zM13.5 6.5h.1",
  refresh: "M16 10a6 6 0 1 1-1.8-4.3M16 3.5v3h-3",
  plus: "M10 4.5v11M4.5 10h11",
  eye: "M2.5 10S5.2 4.5 10 4.5 17.5 10 17.5 10 14.8 15.5 10 15.5 2.5 10 2.5 10zM10 12.3a2.3 2.3 0 1 0 0-4.6 2.3 2.3 0 0 0 0 4.6z",
  eyeOff: "M3 3l14 14M8.2 8.3a2.3 2.3 0 0 0 3.3 3.3M5.5 5.8C3.6 7.2 2.5 10 2.5 10s2.7 5.5 7.5 5.5c1.6 0 3-.6 4.1-1.4M8 4.7c.6-.1 1.3-.2 2-.2 4.8 0 7.5 5.5 7.5 5.5s-.7 1.4-2 2.8",
  chat: "M4 4.5h12a1 1 0 0 1 1 1v7.5a1 1 0 0 1-1 1H9l-4 3v-3H4a1 1 0 0 1-1-1V5.5a1 1 0 0 1 1-1z",
} as const;

export function Icon({ name, size = 20, className = "" }: { name: keyof typeof PATHS; size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" fill="none" aria-hidden="true" className={className}>
      <path d={PATHS[name]} stroke="currentColor" strokeWidth={1.5} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
