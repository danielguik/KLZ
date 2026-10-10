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

export const Layer = z.discriminatedUnion('type', [
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
