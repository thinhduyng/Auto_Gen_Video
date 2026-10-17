import { loadFont } from "@remotion/fonts";
import React from "react";
import { AbsoluteFill, Audio, Img, staticFile, useCurrentFrame, useVideoConfig } from "remotion";
import { DiagramLayer, sceneAlpha } from "./Diagram";
import { Beat, C, FONT, Props, Scene, clamp, out3, sceneEntrance } from "./lib";
import { BulletsScene, Captions, CompareScene, Head, NextScene, StatScene, TipScene, TitleScene } from "./Scenes";

loadFont({ family: "BVP", url: staticFile("fonts/BeVietnamPro-Medium.ttf"), weight: "500" });
loadFont({ family: "BVP", url: staticFile("fonts/BeVietnamPro-Bold.ttf"), weight: "700" });

const Background: React.FC<{ t: number }> = ({ t }) => (
  <>
    <AbsoluteFill style={{ background: `radial-gradient(1200px 1000px at 50% 30%, ${C.bg1} 0%, ${C.bg0} 70%)` }} />
    <div style={{ position: "absolute", left: -600, right: -600, bottom: -80, height: 900, transform: "perspective(800px) rotateX(66deg)", transformOrigin: "bottom",
      backgroundImage: "linear-gradient(rgba(139,92,246,.35) 2px, transparent 2px), linear-gradient(90deg, rgba(139,92,246,.35) 2px, transparent 2px)",
      backgroundSize: "110px 110px", backgroundPosition: `0 ${t * 40}px`, opacity: 0.45,
      WebkitMaskImage: "linear-gradient(0deg, rgba(0,0,0,.95), transparent 80%)" }} />
    <div style={{ position: "absolute", width: 900, height: 900, borderRadius: "50%", left: 90 + Math.sin(t / 3) * 120, top: 420 + Math.cos(t / 4) * 90,
      background: "radial-gradient(circle, rgba(139,92,246,.22), transparent 65%)" }} />
    <div style={{ position: "absolute", width: 700, height: 700, borderRadius: "50%", left: 380 + Math.cos(t / 5) * 140, top: 1000 + Math.sin(t / 3.5) * 80,
      background: "radial-gradient(circle, rgba(34,211,238,.14), transparent 65%)" }} />
  </>
);

// Ảnh theo câu kể: mờ chuyển 0,45 s, zoom chậm trong suốt câu, phủ lớp tối để chữ trắng vẫn rõ
const SCRIM = "linear-gradient(180deg, rgba(6,10,24,.78) 0%, rgba(6,10,24,.50) 30%, rgba(6,10,24,.56) 62%, rgba(6,10,24,.88) 100%)";
const BeatLayer: React.FC<{ beats: Beat[]; t: number }> = ({ beats, t }) => (
  <>
    {beats.map((b, i) => {
      const fin = b.t0 <= 0.01 ? 1 : clamp((t - b.t0) / 0.45);
      const a = fin * (1 - clamp((t - b.t1) / 0.45));
      if (a <= 0) return null;
      const zoom = 1.03 + 0.07 * clamp((t - b.t0) / Math.max(1, b.t1 - b.t0));
      return (
        <AbsoluteFill key={i} style={{ opacity: a, overflow: "hidden" }}>
          <Img src={staticFile(b.src)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${zoom})`, filter: "brightness(.84)" }} />
          <AbsoluteFill style={{ background: SCRIM }} />
        </AbsoluteFill>
      );
    })}
  </>
);

const Header: React.FC<{ props: Props; t: number }> = ({ props, t }) => {
  const m = props.data.meta;
  return (
    <>
      <div style={{ position: "absolute", top: 0, left: 0, height: 10, width: 1080 * clamp(t / props.data.duration),
        background: `linear-gradient(90deg, ${C.cyan}, ${C.violet})`, boxShadow: `0 0 18px ${C.violet}` }} />
      <div style={{ position: "absolute", top: 92, left: 70, right: 70, display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14, padding: "14px 26px", borderRadius: 999, border: "2px solid rgba(255,255,255,.14)",
          background: "rgba(255,255,255,.06)", fontWeight: 700, fontSize: 29, letterSpacing: ".06em", color: C.ink }}>
          <span style={{ width: 14, height: 14, borderRadius: "50%", background: C.violet, boxShadow: `0 0 12px ${C.violet}` }} />{m.series || "HỌC NHANH"}
        </div>
        {m.ep ? <div style={{ fontWeight: 700, fontSize: 30, color: C.muted, letterSpacing: ".08em" }}>TẬP <b style={{ color: C.ink }}>{String(m.ep).padStart(2, "0")}</b>{m.total ? ` / ${m.total}` : ""}</div> : null}
      </div>
    </>
  );
};

function renderScene(s: Scene, t: number, props: Props) {
  switch (s.type) {
    case "title": return <TitleScene s={s} t={t} data={props.data} />;
    case "bullets": return <BulletsScene s={s} t={t} />;
    case "compare": return <CompareScene s={s} t={t} />;
    case "stat": return <StatScene s={s} t={t} />;
    case "diagram": return <Head s={s} t={t} />;
    case "tip": return <TipScene s={s} t={t} />;
    case "next": return <NextScene s={s} t={t} />;
    default: return null;
  }
}

export const Academic: React.FC<Props> = (props) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  const { scenes, diagrams } = props.data;

  // các cảnh diagram liền nhau dùng chung một lớp sơ đồ, không tắt/bật giữa các bước
  const groups: { id: string; start: number; end: number }[] = [];
  for (const s of scenes) {
    if (s.type !== "diagram") continue;
    const last = groups[groups.length - 1];
    if (last && last.id === s.diagram && Math.abs(last.end - s.start) < 0.01) last.end = s.end;
    else groups.push({ id: s.diagram, start: s.start, end: s.end });
  }

  return (
    <AbsoluteFill style={{ fontFamily: FONT, color: C.ink, overflow: "hidden" }}>
      <Background t={t} />
      <BeatLayer beats={props.data.beats || []} t={t} />
      <Header props={props} t={t} />
      {scenes.map((s, i) => {
        const a = sceneAlpha(t, s.start, s.end);
        if (a <= 0) return null;
        const entrance = sceneEntrance(t, s);
        return (
          <div key={i} style={{ position: "absolute", left: 70, right: 70, top: 220, height: 1180, ...entrance, opacity: a * Number(entrance.opacity ?? 1) }}>
            {renderScene(s, t, props)}
          </div>
        );
      })}
      {groups.map((g, i) => {
        const a = sceneAlpha(t, g.start, g.end);
        const active = scenes.find((s) => s.diagram === g.id && t >= s.start && t < s.end);
        const entrance = active?.animation && active.animation !== "default" ? sceneEntrance(t, active) : {};
        return a > 0 ? <AbsoluteFill key={i} style={entrance}><DiagramLayer diagram={diagrams[g.id]} scenes={scenes} id={g.id} t={t} opacity={a} /></AbsoluteFill> : null;
      })}
      <Captions data={props.data} t={t} />
      {props.audio ? <Audio src={staticFile(props.audio)} /> : null}
    </AbsoluteFill>
  );
};
