import React from 'react';
import {AbsoluteFill, Audio, OffthreadVideo, interpolate, staticFile, useCurrentFrame, useVideoConfig} from 'remotion';
import type {LayerT} from '../schema';

type V = Extract<LayerT, {type: 'video'}>;

export const VideoLayer: React.FC<{l: V}> = ({l}) => {
  const frame = useCurrentFrame();
  const {fps} = useVideoConfig();
  const t = frame / fps;
  // zoom em momentos-chave: sobe em 0.25s, segura e volta
  let scale = 1;
  for (const z of l.zoomPunches) {
    const s = interpolate(t, [z.at, z.at + 0.25, z.at + z.hold, z.at + z.hold + 0.3], [1, z.scale, z.scale, 1],
      {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
    scale = Math.max(scale, s);
  }
  return (
    <AbsoluteFill style={{transform: `scale(${scale})`, filter: `brightness(${l.brightness}) contrast(${l.contrast}) saturate(${l.saturate})`}}>
      <OffthreadVideo src={staticFile(l.src)} startFrom={Math.round(l.trimStart * fps)} volume={l.volume}
        style={{width: '100%', height: '100%', objectFit: 'cover'}} />
    </AbsoluteFill>
  );
};

export const AudioLayer: React.FC<{l: Extract<LayerT, {type: 'audio'}>}> = ({l}) => {
  const {fps} = useVideoConfig();
  return <Audio src={staticFile(l.src)} startFrom={Math.round(l.trimStart * fps)} volume={l.volume} playbackRate={l.rate} />;
};
