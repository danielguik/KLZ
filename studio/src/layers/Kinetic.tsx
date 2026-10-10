import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {LayerT} from '../schema';
import {FONT, useLife} from './anim';

type K = Extract<LayerT, {type: 'kinetic'}>;

/** Tipografia cinética em camadas: pilha de palavras, letreiro rolando (marquee) ou cascata. */
export const Kinetic: React.FC<{l: K}> = ({l}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const {out} = useLife(l.duration);
  const textStyle = (i: number): React.CSSProperties => ({
    fontFamily: FONT, fontWeight: 800, fontSize: l.fontSize, lineHeight: 0.95, letterSpacing: -3, whiteSpace: 'nowrap', textTransform: 'uppercase',
    color: l.outline ? 'transparent' : (i % 2 ? l.accent : l.color), WebkitTextStroke: l.outline ? `3px ${i % 2 ? l.accent : l.color}` : undefined,
  });
  if (l.mode === 'marquee') {
    const rows = Math.max(3, Math.round((height * 0.6) / (l.fontSize * 0.95)));
    const phrase = (l.words.join('  ·  ') + '  ·  ').repeat(6);
    return (
      <AbsoluteFill style={{opacity: out * l.opacity, transform: `rotate(${l.rotate}deg) scale(1.25)`}}>
        {Array.from({length: rows}, (_, r) => {
          const dir = r % 2 ? 1 : -1;
          const x = ((frame * l.speed * 3.2 * dir) % 2400);
          return <div key={r} style={{...textStyle(r), position: 'absolute', top: l.y * height + (r - rows / 2) * l.fontSize * 0.98, left: dir < 0 ? x : x - 2400}}>{phrase}</div>;
        })}
      </AbsoluteFill>
    );
  }
  const n = l.words.length;
  return (
    <AbsoluteFill style={{opacity: out * l.opacity, alignItems: 'center'}}>
      <div style={{position: 'absolute', top: l.y * height - (n * l.fontSize * 0.95) / 2, width, textAlign: 'center', transform: `rotate(${l.rotate * 0.3}deg)`}}>
        {l.words.map((w, i) => {
          const d = Math.round(i * 0.18 * fps);
          const p = spring({frame: frame - d, fps, config: {damping: 13, stiffness: 160, mass: 0.8}});
          const fromSide = l.mode === 'cascade' ? (i % 2 ? 1 : -1) * 700 * (1 - p) : 0;
          return (
            <div key={i} style={{...textStyle(i), display: 'block', transform: `translateX(${fromSide}px) translateY(${(1 - p) * 120}px) scale(${0.7 + 0.3 * p})`, opacity: Math.min(1, p * 1.6),
              filter: `blur(${(1 - p) * 14}px)`, textShadow: l.outline ? 'none' : '0 10px 40px rgba(0,0,0,0.35)'}}>{w}</div>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
