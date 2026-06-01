# Setup CampoFort Cloud — Guia Completo

> Após este setup, o boletim roda **toda quarta às 08h** automaticamente.
> Você não precisa estar no computador. O PC pode estar desligado.

---

## O que você precisará fazer (uma única vez)

| # | Tarefa | Tempo estimado |
|---|--------|---------------|
| 1 | Ativar CallMeBot no WhatsApp | 2 min |
| 2 | Obter chave da API Anthropic | 5 min |
| 3 | Configurar segredos no GitHub | 5 min |
| 4 | Habilitar GitHub Pages | 2 min |
| 5 | Cadastrar RSS no Spotify for Podcasters | 10 min |
| 6 | Fazer push dos arquivos novos | 5 min |
| 7 | Testar rodando manualmente | 5 min |

---

## PASSO 1 — Criar Bot no Telegram (gratuito, 2 minutos)

O Telegram Bot API envia mensagens diretamente para você, sem limite e sem custo.

### 1.1 — Criar o bot
1. Abra o **Telegram** no celular ou computador
2. Pesquise por `@BotFather` e abra a conversa
3. Envie o comando: `/newbot`
4. Quando perguntar o **nome** do bot, responda: `CampoFort Boletim`
5. Quando perguntar o **username**, responda: `campofort_boletim_bot`
   _(se esse nome já existir, tente `campofort_daniel_bot` ou similar — precisa terminar em `bot`)_
6. O BotFather responde com um **token** no formato:
   ```
   1234567890:ABCdefGHIjklMNOpqrSTUvwxYZ
   ```
   **Guarde esse token** — você vai usar no Passo 3.

### 1.2 — Descobrir seu Chat ID
1. Pesquise pelo username que você criou (ex: `@campofort_boletim_bot`) e **inicie uma conversa** com ele (clique em "Iniciar" ou envie `/start`)
2. No navegador, abra este endereço (substitua `SEU_TOKEN` pelo token do passo anterior):
   ```
   https://api.telegram.org/botSEU_TOKEN/getUpdates
   ```
3. Você verá um JSON. Procure pelo campo `"id"` dentro de `"chat"`. Esse número é o seu **Chat ID**.
   Exemplo: `"id": 987654321`
4. **Guarde esse número** — você vai usar no Passo 3.

> 💡 Se o JSON aparecer vazio (`"result":[]`), envie qualquer mensagem para o bot no Telegram e recarregue a página.

---

## PASSO 2 — Chave da API Anthropic

1. Acesse: **https://console.anthropic.com**
2. Faça login com sua conta (ou crie gratuitamente)
3. Vá em **API Keys** → **Create Key**
4. Nomeie: `campofort-pipeline`
5. Copie a chave (começa com `sk-ant-...`)

> 💡 **Custo**: Claude Haiku custa ~$0,003 por boletim = **menos de R$ 0,25/mês**

---

## PASSO 3 — Configurar Segredos no GitHub

1. Acesse: **https://github.com/danielsilvarodriguesdrs-ship-it/podcast-campofort**
2. Vá em **Settings** → **Secrets and variables** → **Actions**
3. Clique **New repository secret** e adicione cada um:

| Nome do Secret | Valor |
|----------------|-------|
| `ANTHROPIC_API_KEY` | Sua chave do Passo 2 (começa com `sk-ant-...`) |
| `TELEGRAM_BOT_TOKEN` | O token do Passo 1.1 (ex: `1234567890:ABCdef...`) |
| `TELEGRAM_CHAT_ID` | O número do Passo 1.2 (ex: `987654321`) |

> O `GITHUB_TOKEN` é automático — não precisa criar.

---

## PASSO 4 — Habilitar GitHub Pages (RSS para Spotify)

1. No repositório, vá em **Settings** → **Pages**
2. Em **Source**, selecione: `Deploy from a branch`
3. Em **Branch**, selecione: `main` → pasta `/ (root)`
4. Clique **Save**

Após salvar, aguarde 1-2 minutos. A URL do seu RSS feed será:
```
https://danielsilvarodriguesdrs-ship-it.github.io/podcast-campofort/podcast_feed.xml
```

> Guarde essa URL — você precisará no Passo 5.

---

## PASSO 5 — Cadastrar Podcast no Spotify for Podcasters

1. Acesse: **https://podcasters.spotify.com**
2. Faça login com sua conta Spotify
3. Clique **Get started** → **I have an existing podcast**
4. Em **RSS feed URL**, cole:
   ```
   https://danielsilvarodriguesdrs-ship-it.github.io/podcast-campofort/podcast_feed.xml
   ```
5. Siga os passos de verificação (Spotify pede que você confirme que é dono do feed)
6. Complete o cadastro com: nome "Boletim CampoFort", categoria "Business/Agriculture"

> Após cadastrar, o Spotify verifica o feed automaticamente. Novos episódios aparecem em **até 1 hora** após o pipeline rodar.

---

## PASSO 6 — Push dos Arquivos Novos

Abra o PowerShell na pasta do projeto e rode:

```powershell
cd "C:\Users\danie\OneDrive\Documentos\Claude\Scheduled\podcast-agro-diario"

git add pipeline_cloud.py requirements_cloud.txt .github/workflows/boletim_campofort.yml SETUP_CLOUD.md

git commit -m "feat: pipeline cloud com GitHub Actions, Edge TTS e CallMeBot"

git push
```

---

## PASSO 7 — Testar Manualmente

1. No GitHub, vá em: **Actions** → **Boletim CampoFort Semanal**
2. Clique **Run workflow** → **Run workflow**
3. Acompanhe o log em tempo real (dura ~3-5 minutos)
4. Verifique:
   - ✅ Boletim e roteiro commitados no repositório
   - ✅ MP3 disponível no Releases (tag `audio`)
   - ✅ WhatsApp recebido no celular
   - ✅ `podcast_feed.xml` atualizado

---

## Como o sistema funciona depois do setup

```
Toda quarta-feira 08:00 Brasília
          ↓
   GitHub Actions acorda
          ↓
   Coleta dados: dólar (AwesomeAPI), Selic (BCB), preços agro (scraping)
          ↓
   Claude Haiku gera: boletim + roteiro + mensagem WhatsApp
          ↓
   Edge TTS gera o MP3 (voz pt-BR-AntonioNeural)
          ↓
   MP3 sobe para GitHub Releases (link público gerado)
          ↓
   RSS atualizado → Spotify publica o episódio automaticamente
          ↓
   CallMeBot envia WhatsApp com o link do podcast
          ↓
   Arquivos commitados no repositório (histórico mantido)
```

---

## Solução de Problemas

| Problema | Solução |
|----------|---------|
| Telegram não chega | Verifique TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID nos Secrets. Certifique-se que enviou /start para o bot antes |
| Spotify não atualiza | Confirme que GitHub Pages está ativo e a URL do RSS é acessível |
| Action falha no Claude | Verifique ANTHROPIC_API_KEY e saldo na conta Anthropic |
| Áudio sem som | Revise o roteiro gerado — edge-tts pode falhar com caracteres especiais |
| Action não dispara | O cron do GitHub pode atrasar até 30 min em dias de alta carga |

---

## Verificar o feed RSS manualmente

Acesse no navegador:
```
https://danielsilvarodriguesdrs-ship-it.github.io/podcast-campofort/podcast_feed.xml
```

Se aparecer XML com seus episódios, o Spotify conseguirá ler. Se der 404, o GitHub Pages ainda não foi ativado.

---

*Setup criado em 27/05/2026 — CampoFort × Claude Cowork*
