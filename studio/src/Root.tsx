import React from 'react';
import {Composition} from 'remotion';
import {Reel} from './Reel';
import {Project, ProjectT} from './schema';
import demo from './projects/door.json';

// Projeto de exemplo para o Studio do Remotion. O render real do KLZ Studio passa as camadas por --props.
const DEFAULT: ProjectT = Project.parse(demo);

export const Root: React.FC = () => (
  <Composition
    id="Reel"
    component={Reel}
    schema={Project}
    defaultProps={DEFAULT}
    width={DEFAULT.width}
    height={DEFAULT.height}
    fps={DEFAULT.fps}
    durationInFrames={Math.round(DEFAULT.durationSec * DEFAULT.fps)}
    calculateMetadata={({props}: {props: ProjectT}) => ({
      durationInFrames: Math.max(1, Math.round(props.durationSec * props.fps)), fps: props.fps, width: props.width, height: props.height,
    })}
  />
);
