import React from 'react';
import {AbsoluteFill, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import type {LayerT} from '../schema';

type C = Extract<LayerT, {type: 'captions'}>;
type W = C['words'][number];

function group(words: W[], maxChars: number, maxWords: number): W[][] {
  const out: W[][] = [];
  let cur: W[] = [];
  for (const w of words) {
    const chars = cur.reduce((a, x) => a + x.text.length + 1, 0) + w.text.length;
    if (cur.length && (cur.length >= maxWords || chars > maxChars || w.p !== cur[cur.length - 1].p)) {
      out.push(cur);
      cur = [];
    }
    cur.push(w);
  }
  if (cur.length) out.push(cur);
  return out;
}

export const Captions: React.FC<{l: C}> = ({l}) => {
  const frame = useCurrentFrame();
  const {fps, height} = useVideoConfig();
  const t = frame / fps;
  const groups = React.useMemo(() => group(l.words, l.maxChars, l.maxWords), [l.words, l.maxChars, l.maxWords]);
  const g = groups.find((gr) => t >= gr[0].start - 0.02 && t <= gr[gr.length - 1].end + 0.12);
  if (!g) return null;
  return (
    <AbsoluteFill style={{justifyContent: 'flex-start', alignItems: 'center'}}>
      <div style={{position: 'absolute', top: l.y * height, transform: 'translateY(-50%)', width: '92%', textAlign: 'center',
        fontFamily: 'Inter, Helvetica, Arial, sans-serif', fontWeight: 800, fontSize: l.fontSize, lineHeight: 1.1,
        textShadow: '0 4px 18px rgba(0,0,0,0.55)', letterSpacing: -1}}>
        {g.map((w, i) => {
          const spoken = t >= w.start;
          const pop = spoken ? spring({frame: frame - Math.round(w.start * fps), fps, config: {damping: 12, stiffness: 220, mass: 0.6}}) : 0;
          const isCur = spoken && t < w.end;
          const color = w.key && spoken ? l.highlight : l.color;
          return (
            <span key={i} style={{display: 'inline-block', margin: '0 0.16em', color, opacity: spoken ? 1 : 0.32,
              transform: `scale(${spoken ? 0.82 + 0.18 * pop + (isCur ? 0.06 : 0) : 1})`}}>
              {w.text}
            </span>
          );
        })}
      </div>
    </AbsoluteFill>
  );
};
