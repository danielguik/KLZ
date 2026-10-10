import React from 'react';
import {AbsoluteFill, Img, interpolate, useCurrentFrame, useVideoConfig} from 'remotion';
import type {LayerT} from '../schema';
import {FONT, ease, useLife} from './anim';

type T = Extract<LayerT, {type: 'textBehind'}>;

/** Texto grande ATRÁS da pessoa: o texto fica sobre o vídeo e o recorte da pessoa (PNG com transparência) fica por cima dele. */
export const TextBehind: React.FC<{l: T}> = ({l}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const {out} = useLife(l.duration);
  const inP = ease(frame / (0.7 * fps));
  const lines = l.text.split('\n');
  const longest = Math.max(1, ...lines.map((x) => x.length));
  const size = l.fit ? Math.min(l.fontSize, (0.94 * width) / (0.66 * longest)) : l.fontSize;
  const idx = Math.max(0, Math.min(Math.max(0, l.frames - 1), Math.round((frame / fps) * l.cutFps)));
  const url = l.cutout ? l.cutout.replace('{n}', String(idx).padStart(5, '0')) : '';
  const drift = interpolate(frame, [0, l.duration * fps], [0, -40]);
  const txt: React.CSSProperties = {
    fontFamily: FONT, fontWeight: 800, fontSize: size, lineHeight: 0.9, letterSpacing: -size * 0.03, textTransform: 'uppercase', whiteSpace: 'nowrap',
    color: l.variant === 'outline' ? 'transparent' : l.color, WebkitTextStroke: l.variant === 'outline' ? `${Math.max(3, size * 0.02)}px ${l.color}` : undefined,
    backgroundImage: l.variant === 'gradient' ? `linear-gradient(180deg, ${l.color} 0%, ${l.accent} 100%)` : undefined,
    WebkitBackgroundClip: l.variant === 'gradient' ? 'text' : undefined, backgroundClip: l.variant === 'gradient' ? 'text' : undefined,
    WebkitTextFillColor: l.variant === 'gradient' ? 'transparent' : undefined, textShadow: l.variant === 'solid' ? '0 12px 60px rgba(0,0,0,0.35)' : 'none',
  };
  return (
    <AbsoluteFill>
      <div style={{position: 'absolute', top: l.y * height, left: 0, width, textAlign: 'center', opacity: out * l.opacity * Math.min(1, inP * 1.5),
        transform: `translateY(${(l.rise ? (1 - inP) * 120 : 0) + drift}px) scale(${l.rise ? 1.12 - 0.12 * inP : 1})`, filter: l.rise ? `blur(${(1 - inP) * 14}px)` : undefined}}>
        {lines.map((ln, i) => <div key={i} style={txt}>{ln}</div>)}
      </div>
      {url && <Img src={url} style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', opacity: out > 0.02 ? 1 : 0,
        filter: `brightness(${l.brightness}) contrast(${l.contrast}) saturate(${l.saturate})`}} />}
    </AbsoluteFill>
  );
};
