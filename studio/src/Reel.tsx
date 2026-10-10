import React from 'react';
import '@fontsource/manrope/700.css';
import '@fontsource/manrope/800.css';
import {AbsoluteFill, Sequence, useVideoConfig} from 'remotion';
import type {ProjectT} from './schema';
import {AudioLayer, VideoLayer} from './layers/VideoLayer';
import {Captions} from './layers/Captions';
import {FloatingWords, Flash, Glass, Stat, Title} from './layers/Graphics';
import {Background} from './layers/Background';
import {TextBehind} from './layers/TextBehind';
import {VideoCard} from './layers/VideoCard';
import {Kinetic} from './layers/Kinetic';
import {BarChart, Ring} from './layers/Charts';
import {Callout, Grid3d, LowerThird, Shape, Transition} from './layers/Overlays';

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
          {l.type === 'textBehind' && <TextBehind l={l} />}
          {l.type === 'background' && <Background l={l} />}
          {l.type === 'videoCard' && <VideoCard l={l} />}
          {l.type === 'kinetic' && <Kinetic l={l} />}
          {l.type === 'barchart' && <BarChart l={l} />}
          {l.type === 'ring' && <Ring l={l} />}
          {l.type === 'lowerthird' && <LowerThird l={l} />}
          {l.type === 'callout' && <Callout l={l} />}
          {l.type === 'grid3d' && <Grid3d l={l} />}
          {l.type === 'shape' && <Shape l={l} />}
          {l.type === 'transition' && <Transition l={l} />}
        </Sequence>
      ))}
    </AbsoluteFill>
  );
};
