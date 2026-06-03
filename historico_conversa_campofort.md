
# Histórico Completo — Projeto CampoFort Boletim Informativo
**Data:** 27/05/2026  
**Participantes:** Daniel Rodrigues (CEO CampoFort) + Claude (Cowork)  
**Projeto:** Automação completa do Boletim Semanal CampoFort

---

## PARTE 1 — Execução da Tarefa Agendada (Boletim 27/05/2026)

### Contexto
O sistema executou automaticamente a tarefa agendada `boletim-semanal-campofort` toda quarta-feira. O pipeline Cowork gerava:
1. Boletim semanal (markdown)
2. Roteiro do podcast (TTS)
3. Mensagem WhatsApp
4. Tentativa de envio via WhatsApp Web (Chrome)

### O que foi gerado nesta execução
- **`boletim_semanal_campofort_20260527.md`** — Boletim completo com:
  - 🐂 Boi Gordo: GO R$ 322,50/@ • MT R$ 341,00/@
  - 🌽 Milho: GO R$ 62,50/sc • MT R$ 42,50/sc
  - 🌱 Soja: GO R$ 112,80/sc (Sul Goiano) • MT ~R$ 100,50/sc
  - 💵 Dólar: ~R$ 5,00 | Selic: 14,50%
  - 🏛️ Política (Revista Oeste): "Agro resiste sem apoio federal"
  - 📌 Regulatório: Ministro André de Paula em Pequim negocia 33 novas plantas
- **`roteiro_podcast_campofort_20260527.md`** — Roteiro TTS 4-5 min (pt-BR-AntonioNeural)
- **`mensagem_whatsapp_20260527.txt`** — Mensagem formatada com placeholder [LINK DO PODCAST]
- **`episodios.json`** — Atualizado com entrada do episódio 27/05/2026

### Problema identificado na execução
`link_audio.txt` ainda apontava para episódio antigo (20260512). O áudio de hoje não foi gerado pois o pipeline de áudio (`gerar_audio_campofort.ps1`) depende do PC local estar ligado. Sistema caiu no fallback — **WhatsApp NÃO foi enviado**.

---

## PARTE 2 — Feedback de Daniel + Diagnóstico do Problema

### Mensagem de Daniel
> "Muito bom o que está sendo construído, porém não está chegando no WhatsApp. Precisamos ajustar isso para otimizar e automatizar, sem eu precisar ficar entrando em Drive, copiando e colando textos, além do áudio do podcast que nunca foi para o Spotify mesmo eu tendo a conta. Precisamos ajustar isso talvez em um App, pois as vezes combinamos um horário e o meu pc estará desligado ou em modo dormência. Volto a dizer, precisamos ajustar isso de uma vez por todas ou largamos isso de mão."

### Diagnóstico dos problemas raiz
| Problema | Causa |
|----------|-------|
| WhatsApp não chegava | Automação via WhatsApp Web (Chrome) é frágil e exige PC ligado + QR code ativo |
| Spotify nunca recebeu episódio | Spotify for Podcasters nunca foi configurado com o RSS feed |
| Áudio não gerado na nuvem | `gerar_audio_campofort.ps1` usa Edge TTS local — não roda sem PC |
| PC em modo dormência quebra tudo | Pipeline inteiro dependia do Windows Task Scheduler local |

### Perguntas feitas a Daniel
1. **WhatsApp:** pessoal ou Business? → **Pessoal**
2. **Budget mensal:** quanto investe? → **Prefiro zero custo**
3. **Spotify:** foi cadastrado? → **Não sei / não lembro**

---

## PARTE 3 — Nova Arquitetura: 100% Nuvem, Zero PC

### Decisão de design
Migrar TODO o pipeline para **GitHub Actions** — servidor da Microsoft/GitHub que roda na nuvem, sempre ligado, sem custo para uso básico.

### Stack escolhida (custo total: ~R$ 0,25/mês)

| Componente | Ferramenta | Custo |
|------------|-----------|-------|
| Agendador | GitHub Actions (cron) | Grátis |
| Coleta de dados | AwesomeAPI (USD) + BCB (Selic) + scraping | Grátis |
| Geração de conteúdo | Claude Haiku API | ~R$ 0,25/mês |
| Geração de áudio | edge-tts (Python package) | Grátis |
| Hospedagem MP3 | GitHub Releases | Grátis |
| RSS → Spotify | GitHub Pages | Grátis |
| Notificação celular | Telegram Bot API | Grátis |

### Arquivos criados
```
podcast-agro-diario/
├── pipeline_cloud.py              ← Pipeline completo (Python)
├── requirements_cloud.txt         ← Dependências
├── SETUP_CLOUD.md                 ← Guia de setup passo-a-passo
└── .github/
    └── workflows/
        └── boletim_campofort.yml  ← GitHub Actions (cron toda quarta 08h Brasília)
```

### Como o pipeline funciona
```
Toda quarta 08:00 Brasília
        ↓
GitHub Actions acorda (sem PC)
        ↓
Coleta: dólar (AwesomeAPI) + Selic (BCB API) + preços agro (scraping)
        ↓
Claude Haiku → gera boletim + roteiro + mensagem Telegram
        ↓
Edge TTS → gera MP3 (pt-BR-AntonioNeural)
        ↓
GitHub Releases → hospeda MP3, gera link público
        ↓
podcast_feed.xml → RSS atualizado → Spotify publica episódio automaticamente
        ↓
Telegram Bot → mensagem com link do podcast chega no celular
        ↓
Arquivos commitados no repositório (histórico mantido)
```

---

## PARTE 4 — Limpeza da Pasta do Projeto

### Situação encontrada
- **36 arquivos**, **3,7 MB** — maioria obsoleta

### O que foi removido (22 arquivos)
| Arquivo | Motivo |
|---------|--------|
| `executar_pipeline_quarta.ps1` | Windows Task Scheduler → substituído por GitHub Actions |
| `gerar_audio_campofort.ps1` | TTS local → Edge TTS roda na nuvem |
| `gerar_rss_feed.ps1` | RSS local → `pipeline_cloud.py` faz isso |
| `publicar_episodio.ps1` | Publicação Spotify local → substituído |
| `setup_windows_scheduler.ps1` | Configuração agendador Windows → inútil |
| `setup_spotify.md` | Guia antigo → `SETUP_CLOUD.md` é o atual |
| `setup_google_calendar.md` | Google Calendar nunca foi integrado |
| `webapp_index.html` | Webapp de 1068 linhas não utilizado |
| `noticias_agro_20260506.md` | Arquivo avulso de 06/05, sem uso |
| `link_audio.txt` | Ponte entre scripts locais → não precisa mais |
| `podcast_campofort_20260511.mp3` | Cópia local 1,8MB → já no GitHub Releases |
| `podcast_campofort_20260512.mp3` | Cópia local 1,8MB → já no GitHub Releases |
| `boletim_semanal_campofort_20260507.md` | Histórico antigo (+3 semanas) |
| `boletim_semanal_campofort_20260512.md` | Histórico antigo (+2 semanas) |
| `boletim_semanal_campofort_20260513.md` | Histórico antigo (+2 semanas) |
| `roteiro_podcast_campofort_20260507.md` | Histórico antigo |
| `roteiro_podcast_campofort_20260511.md` | Roteiro órfão (sem boletim correspondente) |
| `roteiro_podcast_campofort_20260512.md` | Histórico antigo |
| `roteiro_podcast_campofort_20260513.md` | Histórico antigo |
| `mensagem_whatsapp_20260507.txt` | Histórico antigo |
| `mensagem_whatsapp_20260512.txt` | Histórico antigo |
| `mensagem_whatsapp_20260513.txt` | Histórico antigo |

### Resultado final
- **12 arquivos**, **100 KB** — pasta enxuta e funcional

```
podcast-agro-diario/
├── .github/workflows/boletim_campofort.yml
├── pipeline_cloud.py
├── requirements_cloud.txt
├── SETUP_CLOUD.md
├── SKILL.md                          ← não mexer (Cowork)
├── episodios.json
├── podcast_feed.xml
├── boletim_semanal_campofort_20260520.md
├── boletim_semanal_campofort_20260527.md
├── roteiro_podcast_campofort_20260520.md
├── roteiro_podcast_campofort_20260527.md
├── mensagem_whatsapp_20260520.txt
└── mensagem_whatsapp_20260527.txt
```

---

## PARTE 5 — Troca de WhatsApp por Telegram

### Problema com CallMeBot
Daniel tentou ativar o CallMeBot (serviço gratuito de WhatsApp) mas não conseguiu enviar mensagem para o número de ativação.

### Solução: Telegram Bot API
- Gratuito, sem limite de mensagens
- API oficial e estável
- Suporta formatação Markdown (negrito, itálico, links)
- Mensagens de até 4096 caracteres (vs ~1200 do WhatsApp)

### Mudanças no pipeline
- **`pipeline_cloud.py`**: função `send_whatsapp()` substituída por `send_telegram()`
- **`.github/workflows/boletim_campofort.yml`**: secret `CALLMEBOT_APIKEY` substituído por `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID`
- **`SETUP_CLOUD.md`**: Passo 1 reescrito com instruções do BotFather

---

## PARTE 6 — Setup Pendente (Daniel precisa executar)

### Secrets necessários no GitHub
Acesse: **github.com/danielsilvarodriguesdrs-ship-it/podcast-campofort → Settings → Secrets and variables → Actions**

| Secret | Como obter |
|--------|-----------|
| `ANTHROPIC_API_KEY` | console.anthropic.com → API Keys → Create Key |
| `TELEGRAM_BOT_TOKEN` | Telegram → @BotFather → /newbot → copiar o token |
| `TELEGRAM_CHAT_ID` | Abrir `https://api.telegram.org/botSEU_TOKEN/getUpdates` após enviar /start para o bot |

### Passo 1 — Criar bot no Telegram (pendente)
1. Abra o Telegram → pesquise `@BotFather`
2. Envie `/newbot`
3. Nome: `CampoFort Boletim`
4. Username: `campofort_boletim_bot` (ou similar, deve terminar em `bot`)
5. BotFather entrega o **token** → guardar
6. Abrir o bot criado → clicar **Iniciar**
7. Acessar no navegador: `https://api.telegram.org/botSEU_TOKEN/getUpdates`
8. Encontrar o **Chat ID** no campo `"chat" → "id"`

### Passo 2 — Chave Anthropic
- Acesse: **console.anthropic.com → API Keys → Create Key**
- Nome sugerido: `campofort-pipeline`

### Passo 3 — Configurar secrets no GitHub
- 3 secrets a adicionar (ver tabela acima)

### Passo 4 — Habilitar GitHub Pages (RSS para Spotify)
- Repo → Settings → Pages → Source: `main` branch, pasta `/(root)`
- URL do RSS após ativar: `https://danielsilvarodriguesdrs-ship-it.github.io/podcast-campofort/podcast_feed.xml`

### Passo 5 — Cadastrar podcast no Spotify for Podcasters
- Acesse: **podcasters.spotify.com**
- "I have an existing podcast" → cole a URL do RSS acima
- Preencha: nome "Boletim CampoFort", categoria Business/Agriculture

### Passo 6 — Push dos arquivos para o GitHub
```powershell
cd "C:\Users\danie\OneDrive\Documentos\Claude\Scheduled\podcast-agro-diario"

git add pipeline_cloud.py requirements_cloud.txt .github/workflows/boletim_campofort.yml SETUP_CLOUD.md

git commit -m "feat: pipeline cloud com GitHub Actions, Edge TTS e Telegram"

git push
```

### Passo 7 — Teste manual
- GitHub → Actions → Boletim CampoFort Semanal → **Run workflow**
- Resultado esperado: mensagem chega no Telegram com link do podcast

---

## Repositório GitHub
**URL:** `https://github.com/danielsilvarodriguesdrs-ship-it/podcast-campofort`  
**Tag de áudio:** `audio` (GitHub Releases)  
**RSS feed:** `https://danielsilvarodriguesdrs-ship-it.github.io/podcast-campofort/podcast_feed.xml`

---

## Contatos e referências úteis
- **Console Anthropic (API Key):** https://console.anthropic.com
- **Spotify for Podcasters:** https://podcasters.spotify.com
- **GitHub Actions:** https://github.com/danielsilvarodriguesdrs-ship-it/podcast-campofort/actions
- **GitHub Secrets:** https://github.com/danielsilvarodriguesdrs-ship-it/podcast-campofort/settings/secrets/actions
- **GitHub Pages:** https://github.com/danielsilvarodriguesdrs-ship-it/podcast-campofort/settings/pages

---

*Histórico gerado em 27/05/2026 — CampoFort × Claude Cowork*
