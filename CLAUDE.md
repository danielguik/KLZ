# KLZ Studio — como editar vídeos por conversa

O usuário fala português (BR). Responda sempre em português, curto e honesto sobre limites.
O projeto é um editor de vídeo por camadas (Remotion). O estado de cada vídeo é UM arquivo JSON; você edita o JSON e renderiza.

## Pré-requisito
O servidor precisa estar rodando: `bash server/start.sh` (na 1ª vez `bash server/install.sh`).
Ele imprime a URL com `?token=...`. O token também fica em `server/data/token.txt`.
Se não estiver rodando, suba em segundo plano e avise o usuário. API em `http://127.0.0.1:8000`, header `X-KLZ-Token: <token>`.

## Fluxo de um pedido ("diminui esse texto", "troca o fundo", "segura essa cena 2 s a mais")
1. `GET /api/projects` → escolha o projeto (se houver mais de um, pergunte qual).
2. `GET /api/projects/{pid}` → leia `layers` (cada camada tem `id`, `name`, `type`, `start`, `duration` e campos do tipo; veja `studio/src/schema.ts`, que é a fonte da verdade de todos os campos).
3. Altere SÓ o que foi pedido e grave: `PUT /api/projects/{pid}/layers` com `{"layers": [...]}` (envie a lista inteira). A ordem da lista = ordem de empilhamento (último = por cima).
4. Renderize: `POST /api/projects/{pid}/render` com `{"scale":0.75,"crf":18}` → devolve um job; consulte `GET /api/projects/{pid}/jobs` até terminar (leva ~5 min por minuto de vídeo).
5. O MP4 fica em `GET /api/projects/{pid}/renders` (arquivo em `server/data/<pid>/render/`). Diga o caminho ao usuário.
6. Antes de entregar, extraia 2–3 quadros com ffmpeg nos instantes alterados e olhe-os. Não entregue sem olhar.

## Mapeando pedidos comuns
- Texto menor/maior: `fontSize` da camada (title/stat/kinetic/textBehind). `textBehind` tem `fit` que ajusta à largura; desligue para respeitar `fontSize`.
- Segurar cena: aumente `duration` da camada; se for o vídeo base, avise que precisa estender o vídeo (congelar quadro) — pergunte.
- Trocar fundo: camada `background` (`style`: aurora|mesh|solid, `c1..c3`). O estilo padrão NÃO gera fundo (só efeitos por cima do vídeo); só adicione fundo se o usuário pedir.
- Mover: `x`,`y`,`w`,`h` são frações 0–1 da tela (9:16).
- Texto atrás da pessoa: camada `textBehind` + `POST /api/projects/{pid}/layers/{lid}/cutout` (gera o recorte, é um job). Use 1–2 vezes por vídeo, não sempre.
- Camadas `auto: true` (áudio das frases, vidro que cobre a legenda antiga, legendas) são geradas pelo servidor. Ajustes manuais (volume, x/y/w/h, blur, tint) são preservados; não apague essas camadas.
- O vidro `cover` deve ficar ACIMA dos recortes na ordem (o recorte carrega a legenda antiga queimada).

## Dublagem (frases e vozes)
- Texto em inglês de uma frase: `PUT /api/projects/{pid}/phrases/{phid}`; depois "Refazer voz" só dessa frase: `POST /api/projects/{pid}/voice` (não refaz as outras).
- Sincronia com a boca: `POST /api/projects/{pid}/lips` recalcula as janelas; a voz começa onde a boca começa.
- Tradução automática precisa de `ANTHROPIC_API_KEY` no ambiente; sem chave, você mesmo traduz (naturalmente, sem literalismo) e grava nas frases.
- Nunca peça ao usuário para colar chaves de API no chat.

## Regras
- Não entregue algo que você sabe que está ruim; diga o defeito.
- Mudanças só no que foi pedido. Depois de renderizar, informe o que mudou e os limites (ex.: áudio não ouvido, só medido).
- Código: ver README.md e LICOES.md (lições aprendidas) antes de mexer em `server/` ou `studio/`. Depois de mexer em `studio/src`, rode `npm run build:player` (dentro de `studio/`).
