import React from 'react';
import {AbsoluteFill, interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {LayerT} from '../schema';

const FONT = 'Inter, Helvetica, Arial, sans-serif';
const useEnter = (dur: number) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const inn = spring({frame, fps, config: {damping: 14, stiffness: 140}});
  const out = interpolate(frame, [dur * fps - 8, dur * fps], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return {inn, out};
};

export const Glass: React.FC<{l: Extract<LayerT, {type: 'glass'}>}> = ({l}) => {
  const {width, height} = useVideoConfig();
  const {inn: inn0, out: out0} = useEnter(l.duration);
  const inn = l.enter ? inn0 : 1;
  const out = l.enter ? out0 : 1;
  return (
    <div style={{position: 'absolute', left: l.x * width, top: l.y * height, width: l.w * width, height: l.h * height,
      borderRadius: l.radius, backdropFilter: `blur(${l.blur}px) saturate(1.3)`, WebkitBackdropFilter: `blur(${l.blur}px) saturate(1.3)`,
      background: l.tint, border: `2px solid ${l.borderColor}`, boxShadow: '0 12px 50px rgba(0,0,0,0.35), inset 0 1px 0 rgba(255,255,255,0.35)',
      opacity: out * inn, transform: `scale(${0.94 + 0.06 * inn})`}} />
  );
};

export const Title: React.FC<{l: Extract<LayerT, {type: 'title'}>}> = ({l}) => {
  const {width, height} = useVideoConfig();
  const {inn, out} = useEnter(l.duration);
  const words = l.text.split(' ');
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div style={{position: 'absolute', top: l.y * height, width: width * 0.9, textAlign: 'center', fontFamily: FONT,
        opacity: out * inn, transform: `translateY(${(1 - inn) * 40}px) scale(${0.9 + 0.1 * inn})`}}>
        {l.tag ? <div style={{display: 'inline-block', padding: '10px 26px', borderRadius: 14, background: 'rgba(255,255,255,0.12)',
          border: '1.5px solid rgba(255,255,255,0.35)', backdropFilter: 'blur(14px)', color: l.accent, fontWeight: 700, fontSize: l.fontSize * 0.3,
          letterSpacing: 4, textTransform: 'uppercase', marginBottom: 18}}>{l.tag}</div> : null}
        <div style={{fontWeight: 900, fontSize: l.fontSize, lineHeight: 1.02, color: l.color, textShadow: '0 6px 30px rgba(0,0,0,0.5)'}}>
          {words.map((w, i) => (
            <span key={i} style={{color: l.accentLast && i === words.length - 1 ? l.accent : l.color}}>{w}{i < words.length - 1 ? ' ' : ''}</span>
          ))}
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const Stat: React.FC<{l: Extract<LayerT, {type: 'stat'}>}> = ({l}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const {inn, out} = useEnter(l.duration);
  const count = interpolate(frame, [6, fps * 1.4], [0, l.value], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  const bar = Math.min(1, count / Math.max(l.value, 1));
  return (
    <AbsoluteFill style={{alignItems: 'center'}}>
      <div style={{position: 'absolute', top: l.y * height, width: width * 0.62, padding: '30px 40px', borderRadius: 34, fontFamily: FONT,
        background: 'rgba(12,12,18,0.55)', border: '2px solid rgba(255,255,255,0.3)', backdropFilter: 'blur(20px)', color: l.color,
        opacity: out * inn, transform: `scale(${0.9 + 0.1 * inn})`}}>
        <div style={{fontSize: 34, fontWeight: 700, letterSpacing: 3, textTransform: 'uppercase', opacity: 0.85}}>{l.label}</div>
        <div style={{fontSize: 150, fontWeight: 900, lineHeight: 1.05, color: l.accent}}>{Math.round(count)}<span style={{fontSize: 70}}>{l.suffix}</span></div>
        <div style={{height: 16, borderRadius: 8, background: 'rgba(255,255,255,0.18)', marginTop: 14}}>
          <div style={{width: `${bar * 100}%`, height: '100%', borderRadius: 8, background: l.accent}} />
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const FloatingWords: React.FC<{l: Extract<LayerT, {type: 'floatingWords'}>}> = ({l}) => {
  const frame = useCurrentFrame();
  const {fps, width, height} = useVideoConfig();
  const {out} = useEnter(l.duration);
  return (
    <AbsoluteFill>
      {l.words.map((w, i) => {
        const a = (i * 137.5) % 360;
        const x = width * (0.18 + 0.64 * ((Math.sin(i * 2.3) + 1) / 2));
        const y = height * (0.06 + 0.2 * ((Math.cos(i * 1.7) + 1) / 2)) + Math.sin((frame + i * 20) / 30) * 8;
        const appear = spring({frame: frame - i * 4, fps, config: {damping: 14}});
        return <div key={i} style={{position: 'absolute', left: x, top: y, transform: `translate(-50%,-50%) rotate(${(a % 24) - 12}deg) scale(${appear})`,
          fontFamily: FONT, fontWeight: 800, fontSize: l.fontSize * (0.8 + ((i * 7) % 5) / 10), color: l.color, opacity: out * 0.85 * appear,
          textShadow: '0 4px 20px rgba(0,0,0,0.5)'}}>{w}</div>;
      })}
    </AbsoluteFill>
  );
};

export const Flash: React.FC<{l: Extract<LayerT, {type: 'flash'}>}> = ({l}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const o = interpolate(frame, [0, 3, l.duration * fps], [0, 0.9, 0], {extrapolateRight: 'clamp'});
  return <AbsoluteFill style={{background: l.color, opacity: o}} />;
};
