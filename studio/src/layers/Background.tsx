import React from 'react';
import {AbsoluteFill, useCurrentFrame, useVideoConfig} from 'remotion';
import type {LayerT} from '../schema';

type B = Extract<LayerT, {type: 'background'}>;

/** Fundo animado (aurora / malha / sólido) com granulado de filme e vinheta. */
export const Background: React.FC<{l: B}> = ({l}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = (frame / fps) * l.speed;
  const blob = (cx: number, cy: number, r: number, color: string, ph: number) => {
    const x = 50 + cx * Math.sin(t * 0.55 + ph) * 30 + Math.cos(t * 0.31 + ph * 2) * 8;
    const y = 50 + cy * Math.cos(t * 0.42 + ph) * 34;
    return `radial-gradient(${r}% ${r * 0.8}% at ${x}% ${y}%, ${color} 0%, transparent 70%)`;
  };
  const bg =
    l.style === 'solid' ? l.c1
    : l.style === 'mesh'
      ? `linear-gradient(${130 + Math.sin(t * 0.3) * 25}deg, ${l.c1} 0%, ${l.c2} 55%, ${l.c3} 100%)`
      : [blob(1, 0.7, 70, l.c2 + 'cc', 0), blob(-1, 1, 60, l.c3 + '99', 2.1), blob(0.6, -1, 55, l.c2 + '88', 4.2), l.c1].join(',');
  return (
    <AbsoluteFill style={{background: bg}}>
      {l.grain > 0 && (
        <svg width="100%" height="100%" style={{position: 'absolute', inset: 0, opacity: l.grain, mixBlendMode: 'overlay'}}>
          <filter id={`n${l.id}`}><feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves="2" seed={Math.floor(frame / 2)} /></filter>
          <rect width="100%" height="100%" filter={`url(#n${l.id})`} />
        </svg>
      )}
      {l.vignette > 0 && <AbsoluteFill style={{background: `radial-gradient(ellipse at center, transparent 40%, rgba(0,0,0,${l.vignette}) 100%)`}} />}
    </AbsoluteFill>
  );
};
