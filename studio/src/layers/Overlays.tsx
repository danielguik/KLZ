import React from 'react';
import {AbsoluteFill, interpolate, random, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {LayerT} from '../schema';
import {FONT, ease, easeInOut, useLife} from './anim';

type L3 = Extract<LayerT, {type: 'lowerthird'}>;
type Co = Extract<LayerT, {type: 'callout'}>;
type G3 = Extract<LayerT, {type: 'grid3d'}>;
type Sh = Extract<LayerT, {type: 'shape'}>;
type Tr = Extract<LayerT, {type: 'transition'}>;

/** Identificação do falante: barra que cresce + nome e cargo entrando por máscara. */
export const LowerThird: React.FC<{l: L3}> = ({l}) => {
  const {width, height, fps} = useVideoConfig();
  const frame = useCurrentFrame();
  const inP = ease(frame / (0.5 * fps)), outP = ease((l.duration * fps - frame) / (0.4 * fps));
  const p = Math.min(inP, outP);
  const right = l.side === 'right';
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', top: l.y * height, [right ? 'right' : 'left']: width * 0.06, display: 'flex', flexDirection: right ? 'row-reverse' : 'row', gap: 22, alignItems: 'stretch', fontFamily: FONT, opacity: Math.min(1, p * 2)}}>
        <div style={{width: 10, borderRadius: 5, background: l.accent, transform: `scaleY(${p})`, transformOrigin: 'top', boxShadow: `0 0 24px ${l.accent}`}} />
        <div style={{overflow: 'hidden', padding: '4px 0'}}>
          <div style={{fontSize: 64, fontWeight: 800, color: l.color, lineHeight: 1.05, transform: `translateY(${(1 - p) * 90}px)`, textShadow: '0 6px 24px rgba(0,0,0,0.55)', textAlign: right ? 'right' : 'left'}}>{l.name}</div>
          {l.role && <div style={{fontSize: 34, fontWeight: 700, color: l.accent, letterSpacing: 3, textTransform: 'uppercase', marginTop: 6, transform: `translateY(${(1 - p) * 70}px)`, textShadow: '0 4px 18px rgba(0,0,0,0.55)', textAlign: right ? 'right' : 'left'}}>{l.role}</div>}
        </div>
      </div>
    </AbsoluteFill>
  );
};

/** Seta/legenda apontando para um ponto do vídeo: o traço se desenha, o ponto pulsa e o rótulo aparece. */
export const Callout: React.FC<{l: Co}> = ({l}) => {
  const {width, height, fps} = useVideoConfig();
  const frame = useCurrentFrame();
  const f = frame - Math.round(l.delay * fps);
  const dot = spring({frame: f, fps, config: {damping: 12}});
  const line = ease(f / (0.55 * fps) - 0.15);
  const lab = spring({frame: f - Math.round(0.45 * fps), fps, config: {damping: 13, stiffness: 160}});
  const out = interpolate(frame, [l.duration * fps - 9, l.duration * fps], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const tx = l.tx * width, ty = l.ty * height, lx = l.lx * width, ly = l.ly * height;
  const ex = lx, d = `M ${tx} ${ty} L ${ex} ${ly} `; // a linha vai até o centro do rótulo (que fica por cima)
  const len = Math.hypot(ex - tx, ly - ty);
  const pulse = (frame % 40) / 40;
  return (
    <AbsoluteFill style={{opacity: out}}>
      <svg width={width} height={height} style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
        <circle cx={tx} cy={ty} r={14 + pulse * 40} fill="none" stroke={l.color} strokeWidth={3} opacity={(1 - pulse) * dot} />
        <circle cx={tx} cy={ty} r={13 * dot} fill={l.color} style={{filter: `drop-shadow(0 0 14px ${l.color})`}} />
        <path d={d} stroke={l.color} strokeWidth={4} fill="none" strokeLinecap="round" strokeDasharray={len} strokeDashoffset={len * (1 - line)} style={{filter: `drop-shadow(0 0 8px ${l.color})`}} />
      </svg>
      <div style={{position: 'absolute', left: lx, top: ly, transform: `translate(-50%, -50%) scale(${0.8 + 0.2 * lab})`, transformOrigin: 'center', opacity: Math.min(1, lab * 1.5),
        padding: '16px 28px', borderRadius: 18, background: 'rgba(14,14,22,0.72)', border: `2px solid ${l.color}`, backdropFilter: 'blur(14px)', color: '#fff', fontFamily: FONT, fontWeight: 800, fontSize: 40, whiteSpace: 'nowrap', boxShadow: `0 10px 40px rgba(0,0,0,0.45), 0 0 30px ${l.color}55`}}>{l.text}</div>
    </AbsoluteFill>
  );
};

/** Piso em perspectiva (grade neon) em movimento. */
export const Grid3d: React.FC<{l: G3}> = ({l}) => {
  const {width, height, fps} = useVideoConfig();
  const {frame, out} = useLife(l.duration);
  const off = (frame * 2.2 * l.speed) % 120;
  return (
    <AbsoluteFill style={{opacity: out * l.opacity, overflow: 'hidden', perspective: 900, perspectiveOrigin: '50% 0%'}}>
      <div style={{position: 'absolute', left: '-50%', top: l.horizon * height, width: '200%', height: height * 1.4, transformOrigin: '50% 0%', transform: 'rotateX(68deg)',
        backgroundImage: `linear-gradient(${l.color} 3px, transparent 3px), linear-gradient(90deg, ${l.color} 3px, transparent 3px)`, backgroundSize: '120px 120px', backgroundPosition: `0 ${off}px`,
        filter: `drop-shadow(0 0 10px ${l.color})`, WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, #000 45%)', maskImage: 'linear-gradient(to bottom, transparent 0%, #000 45%)'}} />
    </AbsoluteFill>
  );
};

/** Forma animada (retângulo, círculo ou linha). */
export const Shape: React.FC<{l: Sh}> = ({l}) => {
  const {width, height, fps} = useVideoConfig();
  const {frame, enter, out} = useLife(l.duration);
  const x = l.x * width, y = l.y * height, w = l.w * width, h = l.h * height;
  const pulse = l.anim === 'pulse' ? 1 + Math.sin(frame / fps * 4) * 0.03 : 1;
  const draw = l.anim === 'draw' ? ease(frame / (0.8 * fps)) : 1;
  const per = l.kind === 'circle' ? Math.PI * Math.min(w, h) : 2 * (w + h);
  return (
    <AbsoluteFill style={{opacity: out}}>
      <svg width={width} height={height} style={{position: 'absolute', inset: 0, overflow: 'visible'}}>
        {l.kind === 'line'
          ? <line x1={x} y1={y} x2={x + w} y2={y + h} stroke={l.stroke} strokeWidth={l.strokeWidth} strokeLinecap="round" strokeDasharray={Math.hypot(w, h)} strokeDashoffset={Math.hypot(w, h) * (1 - draw)} />
          : l.kind === 'circle'
            ? <ellipse cx={x + w / 2} cy={y + h / 2} rx={(w / 2) * pulse * enter} ry={(h / 2) * pulse * enter} fill={l.fill} stroke={l.stroke} strokeWidth={l.strokeWidth} strokeDasharray={per} strokeDashoffset={per * (1 - draw)} />
            : <rect x={x} y={y} width={w * pulse} height={h * pulse} rx={l.radius} fill={l.fill} stroke={l.stroke} strokeWidth={l.strokeWidth} strokeDasharray={per} strokeDashoffset={per * (1 - draw)} opacity={enter} />}
      </svg>
    </AbsoluteFill>
  );
};

/** Transições de cena: cobre a tela no meio e revela de novo (wipe, barras, íris, glitch, flash, fade para preto). */
export const Transition: React.FC<{l: Tr}> = ({l}) => {
  const {width, height, fps} = useVideoConfig();
  const frame = useCurrentFrame();
  const p = Math.min(1, Math.max(0, frame / Math.max(1, l.duration * fps)));
  const cover = Math.sin(Math.PI * p); // 0 → 1 → 0
  if (l.kind === 'flash') return <AbsoluteFill style={{background: '#fff', opacity: Math.pow(cover, 2)}} />;
  if (l.kind === 'fadeblack') return <AbsoluteFill style={{background: '#000', opacity: cover}} />;
  if (l.kind === 'iris') {
    const r = (1 - cover) * Math.hypot(width, height);
    return <AbsoluteFill style={{background: l.color, clipPath: 'none', WebkitMaskImage: `radial-gradient(circle at 50% 50%, transparent ${r}px, #000 ${r + 2}px)`, maskImage: `radial-gradient(circle at 50% 50%, transparent ${r}px, #000 ${r + 2}px)`}} />;
  }
  if (l.kind === 'bars') {
    const n = 6;
    return (
      <AbsoluteFill>
        {Array.from({length: n}, (_, i) => {
          const q = easeInOut(Math.min(1, Math.max(0, cover * 1.6 - i * 0.12)));
          return <div key={i} style={{position: 'absolute', left: (i * width) / n, width: width / n + 1, top: 0, height: height * q, background: i % 2 ? l.color2 : l.color}} />;
        })}
      </AbsoluteFill>
    );
  }
  if (l.kind === 'glitch') {
    const s = Math.floor(frame / 1.5);
    return (
      <AbsoluteFill style={{opacity: cover > 0.05 ? 1 : 0}}>
        {Array.from({length: 9}, (_, i) => {
          const y = random(`y${s}${i}`) * height, h = 20 + random(`h${s}${i}`) * 140, dx = (random(`x${s}${i}`) - 0.5) * 140 * cover;
          return <div key={i} style={{position: 'absolute', left: dx, width, top: y, height: h, background: i % 3 === 0 ? l.color : i % 3 === 1 ? l.color2 : '#fff', opacity: 0.55 * cover, mixBlendMode: 'screen'}} />;
        })}
      </AbsoluteFill>
    );
  }
  // wipe: painel diagonal cruzando a tela
  const x = interpolate(easeInOut(p), [0, 1], [-width * 1.3, width * 1.3]);
  return (
    <AbsoluteFill style={{overflow: 'hidden'}}>
      <div style={{position: 'absolute', top: -height * 0.2, height: height * 1.4, width: width * 1.4, left: x, background: `linear-gradient(100deg, ${l.color}, ${l.color2})`, transform: 'skewX(-14deg)', boxShadow: '0 0 120px rgba(0,0,0,0.5)'}} />
    </AbsoluteFill>
  );
};
