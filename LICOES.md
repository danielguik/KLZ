# Lições aprendidas (atualizar a cada vídeo)
- Whisper `small` erra nomes; `large-v3` + `initial_prompt` com termos do assunto acerta bem. Sempre revisar com o usuário nomes de marca (ex.: Doormaxx).
- Timestamps do Whisper próximos a silêncios são pouco confiáveis: usar o início real da fala (VAD/ rodada anterior) como âncora da dublagem.
- faster-whisper + `av` novo quebra com caminho de arquivo: passar array numpy (ffmpeg -f f32le).
- Rede da sessão: liberar huggingface.co dá Whisper e Piper locais, sem chave.
- Legendas antigas queimadas no vídeo: cobrir com cartão de vidro (blur 30 + tint escuro) um pouco maior que a área do texto.
- Legenda ASS: palavras ainda não faladas ficam invisíveis mas ocupam espaço -> a palavra atual aparece descentralizada. A melhorar (centralizar por palavra).
- `pkill -f` com o texto do próprio comando mata o shell. Não usar.
