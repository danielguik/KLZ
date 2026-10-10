import {z} from 'zod';

const base = {
  id: z.string(),
  name: z.string().describe('Nome da camada (aparece na timeline)'),
  start: z.number().min(0).describe('Início (s)'),
  duration: z.number().min(0.1).describe('Duração (s)'),
};

export const Word = z.object({
  text: z.string(),
  start: z.number().describe('s, relativo ao início da camada'),
  end: z.number(),
  key: z.boolean().default(false).describe('palavra-chave (destaque)'),
  p: z.number().default(0).describe('índice da frase (grupos não cruzam frases)'),
});

const Enter = z.enum(['pop', 'rise', 'slide', 'fade', 'none']).default('pop').describe('animação de entrada');

export const Layer = z.discriminatedUnion('type', [
  z.object({
    ...base, type: z.literal('background'),
    style: z.enum(['aurora', 'mesh', 'solid']).default('aurora'),
    c1: z.string().default('#0b0b14'), c2: z.string().default('#5b2bd9'), c3: z.string().default('#ff6a3d'),
    speed: z.number().min(0).max(4).default(1), grain: z.number().min(0).max(1).default(0.18), vignette: z.number().min(0).max(1).default(0.55),
  }),
  z.object({
    ...base, type: z.literal('videoCard'),
    src: z.string(), trimStart: z.number().min(0).default(0), volume: z.number().min(0).max(1).default(0),
    x: z.number().default(0.06), y: z.number().default(0.3), w: z.number().default(0.88), h: z.number().default(0.5),
    shape: z.enum(['rounded', 'circle']).default('rounded'), radius: z.number().default(48),
    borderColor: z.string().default('rgba(255,255,255,0.35)'), borderWidth: z.number().default(3), glow: z.string().default('rgba(120,80,255,0.45)'),
    zoom: z.number().min(1).max(4).default(1).describe('recorte: aproxima a região'), focusX: z.number().min(0).max(1).default(0.5), focusY: z.number().min(0).max(1).default(0.5),
    enter: Enter,
  }),
  z.object({
    ...base, type: z.literal('kinetic'),
    words: z.array(z.string()), mode: z.enum(['stack', 'marquee', 'cascade']).default('stack'),
    fontSize: z.number().default(150), y: z.number().default(0.5), color: z.string().default('#ffffff'), accent: z.string().default('#ffb020'),
    outline: z.boolean().default(false), speed: z.number().default(1), rotate: z.number().default(-6), opacity: z.number().min(0).max(1).default(1),
  }),
  z.object({
    ...base, type: z.literal('barchart'),
    title: z.string().default(''), items: z.array(z.object({label: z.string(), value: z.number(), color: z.string().default('')})),
    y: z.number().default(0.15), w: z.number().default(0.84), accent: z.string().default('#ffb020'), unit: z.string().default('%'),
  }),
  z.object({
    ...base, type: z.literal('ring'),
    value: z.number().min(0).max(100).default(70), label: z.string().default(''), y: z.number().default(0.2), size: z.number().default(420),
    color: z.string().default('#ffb020'), unit: z.string().default('%'),
  }),
  z.object({
    ...base, type: z.literal('lowerthird'),
    name: z.string(), role: z.string().default(''), y: z.number().default(0.7), side: z.enum(['left', 'right']).default('left'),
    color: z.string().default('#ffffff'), accent: z.string().default('#ffb020'),
  }),
  z.object({
    ...base, type: z.literal('callout'),
    text: z.string(), tx: z.number().default(0.5).describe('alvo X (0–1)'), ty: z.number().default(0.5).describe('alvo Y (0–1)'),
    lx: z.number().default(0.7), ly: z.number().default(0.3), color: z.string().default('#ffb020'), delay: z.number().default(0),
  }),
  z.object({
    ...base, type: z.literal('grid3d'),
    color: z.string().default('#7c5cff'), speed: z.number().default(1), horizon: z.number().min(0).max(1).default(0.55), opacity: z.number().min(0).max(1).default(0.8),
  }),
  z.object({
    ...base, type: z.literal('shape'),
    kind: z.enum(['rect', 'circle', 'line']).default('rect'), x: z.number().default(0.1), y: z.number().default(0.1), w: z.number().default(0.3), h: z.number().default(0.1),
    fill: z.string().default('rgba(255,255,255,0.12)'), stroke: z.string().default('rgba(255,255,255,0.5)'), strokeWidth: z.number().default(3), radius: z.number().default(24),
    anim: z.enum(['pulse', 'draw', 'none']).default('draw'),
  }),
  z.object({
    ...base, type: z.literal('transition'),
    kind: z.enum(['wipe', 'bars', 'iris', 'glitch', 'flash', 'fadeblack']).default('wipe'), color: z.string().default('#7c5cff'), color2: z.string().default('#ffb020'),
  }),
  z.object({
    ...base, type: z.literal('video'),
    src: z.string().describe('arquivo em public/'),
    trimStart: z.number().min(0).default(0).describe('cortar o início (s)'),
    volume: z.number().min(0).max(1).default(1),
    brightness: z.number().min(0).max(2).default(1),
    contrast: z.number().min(0).max(2).default(1),
    saturate: z.number().min(0).max(2).default(1),
    zoomPunches: z.array(z.object({
      at: z.number().describe('s (relativo à camada)'),
      scale: z.number().min(1).max(2).default(1.15),
      hold: z.number().default(0.8),
    })).default([]).describe('Zoom em momentos-chave'),
  }),
  z.object({
    ...base, type: z.literal('audio'),
    src: z.string(), trimStart: z.number().min(0).default(0),
    volume: z.number().min(0).max(1).default(1),
    rate: z.number().min(0.5).max(2).default(1).describe('velocidade'),
  }),
  z.object({
    ...base, type: z.literal('captions'),
    words: z.array(Word),
    fontSize: z.number().min(20).max(160).default(64),
    y: z.number().min(0).max(1).default(0.8).describe('posição vertical (0 topo, 1 base)'),
    color: z.string().default('#ffffff'),
    highlight: z.string().default('#ffb020'),
    maxChars: z.number().default(18),
    maxWords: z.number().default(3),
    variant: z.enum(['pop', 'box', 'outline']).default('pop').describe('estilo da legenda'),
  }),
  z.object({
    ...base, type: z.literal('glass'),
    x: z.number().describe('0–1 da largura'), y: z.number(), w: z.number(), h: z.number(),
    enter: z.boolean().default(true).describe('animação de entrada'),
    radius: z.number().default(36), blur: z.number().min(0).max(80).default(28),
    tint: z.string().default('rgba(10,10,14,0.45)'), borderColor: z.string().default('rgba(255,255,255,0.45)'),
  }),
  z.object({
    ...base, type: z.literal('title'),
    text: z.string(), tag: z.string().default('').describe('chip pequeno acima'),
    y: z.number().default(0.18), fontSize: z.number().default(96),
    color: z.string().default('#ffffff'), accent: z.string().default('#ffb020'),
    accentLast: z.boolean().default(true).describe('última palavra colorida'),
  }),
  z.object({
    ...base, type: z.literal('stat'),
    label: z.string(), value: z.number(), suffix: z.string().default('%'),
    y: z.number().default(0.2), color: z.string().default('#ffffff'), accent: z.string().default('#ffb020'),
  }),
  z.object({
    ...base, type: z.literal('floatingWords'),
    words: z.array(z.string()), color: z.string().default('#ffffff'), fontSize: z.number().default(54),
  }),
  z.object({
    ...base, type: z.literal('flash'),
    color: z.string().default('#ffffff'),
  }),
]);

export const Project = z.object({
  fps: z.number().default(30),
  width: z.number().default(1080),
  height: z.number().default(1920),
  durationSec: z.number(),
  layers: z.array(Layer),
});
export type ProjectT = z.infer<typeof Project>;
export type LayerT = z.infer<typeof Layer>;
