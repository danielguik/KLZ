import React from 'react';
import {createRoot} from 'react-dom/client';
import {Player, PlayerRef} from '@remotion/player';
import {Reel} from './Reel';
import {Project, ProjectT} from './schema';

/** Prévia da interface: o MESMO componente usado no render final (o que você vê é o que sai no vídeo). */
export function mount(el: HTMLElement) {
  const root = createRoot(el);
  const ref = React.createRef<PlayerRef>();
  let props: ProjectT | null = null;
  const draw = () => {
    if (!props) return;
    root.render(
      <Player ref={ref} component={Reel} inputProps={props} durationInFrames={Math.max(1, Math.round(props.durationSec * props.fps))} fps={props.fps}
        compositionWidth={props.width} compositionHeight={props.height} controls={false} clickToPlay={false} doubleClickToFullscreen={false}
        style={{width: '100%', height: '100%'}} numberOfSharedAudioTags={40} acknowledgeRemotionLicense loop={false} />,
    );
  };
  return {
    /** aplica os valores padrão do esquema (zod) e redesenha */
    update(p: unknown) { props = Project.parse(p); draw(); },
    play() { ref.current?.play(); },
    pause() { ref.current?.pause(); },
    seekTo(frame: number) { ref.current?.seekTo(frame); },
    frame() { return ref.current?.getCurrentFrame() ?? 0; },
    playing() { return ref.current?.isPlaying() ?? false; },
  };
}
