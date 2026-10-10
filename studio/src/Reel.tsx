import React from 'react';
import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import type {ProjectT} from './schema';
import {AudioLayer, VideoLayer} from './layers/VideoLayer';
import {Captions} from './layers/Captions';
import {FloatingWords, Flash, Glass, Stat, Title} from './layers/Graphics';

export const Reel: React.FC<ProjectT> = ({layers}) => {
  const {fps} = useVideoConfig();
  return (
    <AbsoluteFill style={{background: '#000'}}>
      {/* a ordem do array é a ordem das camadas: o último fica por cima */}
      {layers.map((l) => (
        <Sequence key={l.id} name={`${l.type} · ${l.name}`} from={Math.round(l.start * fps)} durationInFrames={Math.max(1, Math.round(l.duration * fps))} layout="none">
          {l.type === 'video' && <VideoLayer l={l} />}
          {l.type === 'audio' && <AudioLayer l={l} />}
          {l.type === 'captions' && <Captions l={l} />}
          {l.type === 'glass' && <Glass l={l} />}
          {l.type === 'title' && <Title l={l} />}
          {l.type === 'stat' && <Stat l={l} />}
          {l.type === 'floatingWords' && <FloatingWords l={l} />}
          {l.type === 'flash' && <Flash l={l} />}
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
