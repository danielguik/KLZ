import React from 'react';
import {AbsoluteFill, OffthreadVideo, staticFile, useVideoConfig} from 'remotion';
import type {LayerT} from '../schema';
import {enterStyle, useLife} from './anim';

type V = Extract<LayerT, {type: 'videoCard'}>;
const url = (s: string) => (/^https?:/.test(s) ? s : staticFile(s));

/** Recorte do vídeo em um cartão (arredondado ou círculo) com borda, brilho e sombra; `zoom`+`foco` aproximam uma região. */
export const VideoCard: React.FC<{l: V}> = ({l}) => {
  const {width, height, fps} = useVideoConfig();
  const {enter, out} = useLife(l.duration);
  const st = enterStyle(l.enter, enter, out);
  const r = l.shape === 'circle' ? '50%' : l.radius;
  return (
    <AbsoluteFill style={{pointerEvents: 'none'}}>
      <div style={{position: 'absolute', left: l.x * width, top: l.y * height, width: l.w * width, height: l.h * height, ...st}}>
        <div style={{position: 'absolute', inset: 0, borderRadius: r, boxShadow: `0 30px 80px rgba(0,0,0,0.5), 0 0 90px ${l.glow}`, border: `${l.borderWidth}px solid ${l.borderColor}`, overflow: 'hidden', background: '#000'}}>
          <OffthreadVideo onError={() => undefined} src={url(l.src)} startFrom={Math.round(l.trimStart * fps)} volume={l.volume}
            style={{position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'cover', objectPosition: `${l.focusX * 100}% ${l.focusY * 100}%`,
              transform: `scale(${l.zoom})`, transformOrigin: `${l.focusX * 100}% ${l.focusY * 100}%`}} />
        </div>
      </div>
    </AbsoluteFill>
  );
};
