import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';

export const FONT = "'Manrope', 'Helvetica Neue', Helvetica, Arial, sans-serif";
export type EnterKind = 'pop' | 'rise' | 'slide' | 'fade' | 'none';

/** progresso 0..1 da entrada (mola) e opacidade de saída nos últimos frames da camada */
export function useLife(durationSec: number, delaySec = 0, cfg = {damping: 15, stiffness: 150, mass: 0.9}) {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const enter = spring({frame: frame - Math.round(delaySec * fps), fps, config: cfg});
  const out = interpolate(frame, [durationSec * fps - 9, durationSec * fps], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
  return {frame, fps, enter, out, t: frame / fps};
}

export function enterStyle(kind: EnterKind, p: number, out = 1): {opacity: number; transform: string} {
  const o = Math.min(1, p * 1.4) * out;
  switch (kind) {
    case 'rise': return {opacity: o, transform: `translateY(${(1 - p) * 90}px) scale(${0.96 + 0.04 * p})`};
    case 'slide': return {opacity: o, transform: `translateX(${(1 - p) * -160}px)`};
    case 'fade': return {opacity: Math.min(1, p) * out, transform: 'none'};
    case 'none': return {opacity: out, transform: 'none'};
    default: return {opacity: o, transform: `scale(${0.88 + 0.12 * p})`};
  }
}

export const ease = (t: number) => 1 - Math.pow(1 - Math.min(1, Math.max(0, t)), 3);
export const easeInOut = (t: number) => { const x = Math.min(1, Math.max(0, t)); return x < 0.5 ? 4 * x * x * x : 1 - Math.pow(-2 * x + 2, 3) / 2; };
