import React from "react";

// ---- dữ liệu dòng thời gian do video-factory (narration.build_timeline) tạo ra ----
export type Word = { display: string; start: number; end: number };
export type Phrase = { from: number; to: number; start: number; end: number };
export type Scene = { type: string; start: number; end: number; [k: string]: any };
export type DiagramEl = { id: string; kind: string; [k: string]: any };
export type Diagram = { w: number; h: number; elements: DiagramEl[] };
export type Data = {
  meta: { series: string; ep: number | null; total: number | null; title: string };
  duration: number;
  scenes: Scene[];
  words: Word[];
  phrases: Phrase[];
  diagrams: Record<string, Diagram>;
  beats?: Beat[];   // ảnh nền theo từng câu kể (factory/beats.py), src nằm trong public/
};
export type Beat = { t0: number; t1: number; src: string };
export type Props = { data: Data; audio: string };

// ---- thời gian & easing ----
export const clamp = (x: number, a = 0, b = 1) => Math.max(a, Math.min(b, x));
export const out3 = (p: number) => 1 - Math.pow(1 - p, 3);
export const back = (p: number) => {
  const c1 = 1.70158, c3 = c1 + 1;
  return 1 + c3 * Math.pow(p - 1, 3) + c1 * Math.pow(p - 1, 2);
};
export const prog = (t: number, at: number, dur = 0.5) => clamp((t - at) / dur);

/** Hiện dần + trượt lên. */
export const up = (t: number, at: number, dur = 0.55): React.CSSProperties => {
  const e = out3(prog(t, at, dur));
  return { opacity: e, transform: `translateY(${(1 - e) * 40}px)` };
};
/** Bật nảy (scale). */
export const pop = (t: number, at: number, dur = 0.55, from = 0.55): React.CSSProperties => {
  const p = prog(t, at, dur);
  const b = p <= 0 ? 0 : back(p);
  return { opacity: clamp(p * 2.5), transform: `scale(${from + (1 - from) * b})` };
};
/** Cường độ phát sáng 0→1→0 trong 2 giây kể từ `at`. */
export const glow = (t: number, at: number) => (t >= at && t <= at + 2 ? Math.sin((Math.PI * (t - at)) / 2) : 0);

// ---- bảng màu nền tối ----
export const C = {
  bg0: "#060A18", bg1: "#0B1433", ink: "#F8FAFC", muted: "#94A3B8", line: "rgba(255,255,255,.14)",
  card: "rgba(255,255,255,.06)", violet: "#8B5CF6", cyan: "#22D3EE", amber: "#F59E0B",
  green: "#22C55E", blue: "#3B82F6", purple: "#A855F7", red: "#EF4444",
};
export const FONT = "BVP, 'Segoe UI', sans-serif";

// ---- icon nét mảnh (viewBox 24) ----
const PATHS: Record<string, string> = {
  globe: '<circle cx="12" cy="12" r="9.5"/><path d="M2.5 12h19M12 2.5c2.8 3 4 6.2 4 9.5s-1.2 6.5-4 9.5c-2.8-3-4-6.2-4-9.5s1.2-6.5 4-9.5z"/>',
  gateway: '<path d="M3.5 20.5V9.5L12 3.5l8.5 6v11"/><path d="M8.5 20.5v-6.5h7v6.5"/><path d="M12 14v6.5"/>',
  nat: '<path d="M6 18L18 6"/><path d="M9 6h9v9"/><path d="M4 12v8h8" opacity=".5"/>',
  server: '<rect x="3.5" y="3.5" width="17" height="7" rx="2"/><rect x="3.5" y="13.5" width="17" height="7" rx="2"/><path d="M7.5 7h.01M7.5 17h.01M11 7h5M11 17h5"/>',
  database: '<ellipse cx="12" cy="5.5" rx="7.5" ry="3"/><path d="M4.5 5.5v13c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-13"/><path d="M4.5 12c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3"/>',
  balance: '<circle cx="12" cy="4.5" r="2"/><circle cx="5" cy="19" r="2"/><circle cx="12" cy="19" r="2"/><circle cx="19" cy="19" r="2"/><path d="M12 6.5V17M12 10.5L5.8 17.2M12 10.5l6.2 6.7"/>',
  bulb: '<path d="M9 18h6M10 21.5h4"/><path d="M12 2.5a6.5 6.5 0 0 0-3.8 11.8c.5.4.8 1 .8 1.7V17h6v-1c0-.7.3-1.3.8-1.7A6.5 6.5 0 0 0 12 2.5z"/>',
  x: '<path d="M6.5 6.5l11 11M17.5 6.5l-11 11"/>',
  shield: '<path d="M12 2.5l8 3v6c0 5-3.4 8.6-8 10-4.6-1.4-8-5-8-10v-6z"/>',
  lock: '<rect x="4.5" y="10.5" width="15" height="10" rx="2"/><path d="M8 10.5V7a4 4 0 0 1 8 0v3.5"/>',
  down: '<path d="M12 4v15M5.5 12.5L12 19l6.5-6.5"/>',
};
export const Icon: React.FC<{ name: string; size: number; color: string; width?: number }> = ({ name, size, color, width = 2 }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="none" stroke={color} strokeWidth={width}
    strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: PATHS[name] || "" }} />
);


/** Bounded, frame-driven scene entrance presets for the prompt editor. */
export function sceneEntrance(t: number, s: Scene): React.CSSProperties {
  const duration = Math.min(0.5, Math.max(1 / 30, (s.end - s.start) / 3));
  const p = s.start <= 0.001 ? 1 : out3(clamp((t - s.start) / duration));
  switch (s.animation) {
    case "fade": return { opacity: p };
    case "zoom": return { opacity: p, transform: `scale(${0.92 + p * 0.08})` };
    case "slide": return { opacity: p, transform: `translateX(${(1 - p) * 70}px)` };
    default: return { opacity: p, transform: `translateY(${(1 - p) * 40}px)` };
  }
}
