import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {LayerT} from '../schema';
import {FONT, useLife} from './anim';

type Bc = Extract<LayerT, {type: 'barchart'}>;
type Rg = Extract<LayerT, {type: 'ring'}>;

const glassCard: React.CSSProperties = {background: 'rgba(14,14,22,0.62)', border: '2px solid rgba(255,255,255,0.22)', backdropFilter: 'blur(22px)', borderRadius: 36, boxShadow: '0 30px 80px rgba(0,0,0,0.45)'};

/** Gráfico de barras animado (placar). */
export const BarChart: React.FC<{l: Bc}> = ({l}) => {
  const {width, height, fps} = useVideoConfig();
  const frame = useCurrentFrame();
  const {enter, out} = useLife(l.duration);
  const max = Math.max(...l.items.map((i) => i.value), 1);
  const top = l.items.reduce((a, b) => (b.value > a.value ? b : a), l.items[0] || {value: 0, label: '', color: ''});
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div style={{position: 'absolute', top: l.y * height, width: l.w * width, padding: '34px 40px 38px', ...glassCard, opacity: out * Math.min(1, enter * 1.5), transform: `translateY(${(1 - enter) * 60}px)`, fontFamily: FONT, color: '#fff'}}>
        {l.title && <div style={{fontSize: 30, fontWeight: 800, letterSpacing: 4, textTransform: 'uppercase', opacity: 0.8, marginBottom: 24}}>{l.title}</div>}
        {l.items.map((it, i) => {
          const p = spring({frame: frame - Math.round((0.15 + i * 0.14) * fps), fps, config: {damping: 16, stiffness: 120}});
          const col = it.color || (it === top ? l.accent : 'rgba(255,255,255,0.55)');
          return (
            <div key={i} style={{marginBottom: 22}}>
              <div style={{display: 'flex', justifyContent: 'space-between', fontSize: 34, fontWeight: 700, marginBottom: 8}}>
                <span>{it.label}</span><span style={{color: col}}>{Math.round(it.value * Math.min(1, p))}{l.unit}</span>
              </div>
              <div style={{height: 26, borderRadius: 13, background: 'rgba(255,255,255,0.12)'}}>
                <div style={{width: `${(it.value / max) * 100 * Math.min(1, p)}%`, height: '100%', borderRadius: 13, background: col, boxShadow: it === top ? `0 0 28px ${col}` : 'none'}} />
              </div>
            </div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};

/** Anel de progresso com contagem. */
export const Ring: React.FC<{l: Rg}> = ({l}) => {
  const {width, height, fps} = useVideoConfig();
  const frame = useCurrentFrame();
  const {enter, out} = useLife(l.duration);
  const p = interpolate(frame, [4, fps * 1.5], [0, 1], {extrapolateRight: 'clamp', extrapolateLeft: 'clamp'});
  const eased = 1 - Math.pow(1 - p, 3);
  const R = l.size / 2 - 22, C = 2 * Math.PI * R;
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div style={{position: 'absolute', top: l.y * height, width: l.size, height: l.size, opacity: out * Math.min(1, enter * 1.5), transform: `scale(${0.85 + 0.15 * enter})`, fontFamily: FONT, color: '#fff'}}>
        <svg width={l.size} height={l.size} style={{transform: 'rotate(-90deg)', filter: `drop-shadow(0 0 22px ${l.color})`}}>
          <circle cx={l.size / 2} cy={l.size / 2} r={R} fill="rgba(14,14,22,0.55)" stroke="rgba(255,255,255,0.14)" strokeWidth={26} />
          <circle cx={l.size / 2} cy={l.size / 2} r={R} fill="none" stroke={l.color} strokeWidth={26} strokeLinecap="round" strokeDasharray={C} strokeDashoffset={C * (1 - (l.value / 100) * eased)} />
        </svg>
        <div style={{position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center'}}>
          <div style={{fontSize: l.size * 0.26, fontWeight: 800, lineHeight: 1}}>{Math.round(l.value * eased)}<span style={{fontSize: l.size * 0.13}}>{l.unit}</span></div>
          {l.label && <div style={{fontSize: l.size * 0.07, fontWeight: 700, letterSpacing: 3, textTransform: 'uppercase', opacity: 0.75, marginTop: 8}}>{l.label}</div>}
        </div>
      </div>
    </AbsoluteFill>
  );
};
