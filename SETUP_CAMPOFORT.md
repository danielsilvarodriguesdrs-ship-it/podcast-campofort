# SETUP CAMPOFORT — Guia Completo de Configuração

Depois de seguir estes passos, o boletim roda automaticamente toda quarta às 06h, sem computador ligado, e chega pelo Telegram com texto + áudio em voz clonada.

---

## PASSO 1 — Criar o Bot do Telegram

1. Abra o Telegram e pesquise **@BotFather**
2. Envie `/newbot`
3. Escolha um nome visível (ex: `CampoFort Boletim`)
4. Escolha um username (ex: `campofort_boletim_bot`)
5. O BotFather entrega um token no formato:
   ```
   1234567890:ABCDefGhijKLMnopQRSTuvWXyz
   ```
   **Guarde este token — é o TELEGRAM_BOT_TOKEN**

6. Para obter o seu TELEGRAM_CHAT_ID:
   - Abra o bot no Telegram e envie qualquer mensagem
   - Acesse no navegador:
     ```
     https://api.telegram.org/bot<SEU_TOKEN>/getUpdates
     ```
   - Procure o campo `"chat":{"id":XXXXXXXXX}` — esse número é o seu **TELEGRAM_CHAT_ID**

---

## PASSO 2 — Obter chave da OpenAI (áudio ~R$3/mês)

O áudio é gerado pela OpenAI TTS com a voz **onyx** — masculina, grave, natural, ideal para noticiário.

1. Acesse **platform.openai.com**
2. Faça login ou crie uma conta gratuita
3. Vá em **API Keys → Create new secret key**
4. Nomeie: `campofort-tts`
5. Copie a chave (começa com `sk-...`)
   **Este é o OPENAI_API_KEY**

> Custo estimado: ~US$0,55/mês (4 episódios × 5 min). Menos de R$3.

---

## PASSO 3 — Adicionar secrets no GitHub

1. Acesse seu repositório: `github.com/danielsilvarodriguesdrs-ship-it/podcast-campofort`
2. Vá em **Settings → Secrets and variables → Actions → New repository secret**
3. Adicione os 5 secrets abaixo (um por vez):

| Nome do Secret       | Onde encontrar                           |
|----------------------|------------------------------------------|
| `ANTHROPIC_API_KEY`  | console.anthropic.com → API Keys         |
| `OPENAI_API_KEY`     | platform.openai.com → API Keys (Passo 2) |
| `TELEGRAM_BOT_TOKEN` | @BotFather no Telegram (Passo 1)         |
| `TELEGRAM_CHAT_ID`   | getUpdates da API Telegram (Passo 1)     |

---

## PASSO 4 — Fazer push dos novos arquivos para o GitHub

No terminal (PowerShell), dentro da pasta do projeto:

```powershell
cd "C:\Users\danie\OneDrive\Documentos\Claude\Scheduled\podcast-agro-diario"
git add scripts/boletim_runner.py .github/workflows/boletim_campofort.yml
git commit -m "feat: novo pipeline Telegram + ElevenLabs voz clonada"
git push
```

---

## PASSO 5 — Testar manualmente

Após o push, teste sem esperar quarta-feira:

1. Acesse seu repositório no GitHub
2. Clique em **Actions → Boletim CampoFort Semanal**
3. Clique em **Run workflow → Run workflow**
4. Acompanhe os logs em tempo real

Se tudo estiver certo, em ~5 minutos você recebe no Telegram:
- A mensagem formatada com o boletim do dia
- O arquivo MP3 do podcast em sua voz

---

## PASSO 6 — Verificar chave Anthropic

Se ainda não tiver:
1. Acesse **console.anthropic.com**
2. Vá em **API Keys → Create Key**
3. Copie a chave (começa com `sk-ant-...`)
4. Adicione como secret `ANTHROPIC_API_KEY` no GitHub (Passo 3)

---

## Resumo dos arquivos criados

```
podcast-agro-diario/
├── scripts/
│   └── boletim_runner.py          ← script principal (toda a lógica)
├── .github/
│   └── workflows/
│       └── boletim_campofort.yml  ← agendamento GitHub Actions
└── SETUP_CAMPOFORT.md             ← este guia
```

## Cronograma de execução

| Horário     | O que acontece                          |
|-------------|----------------------------------------|
| 06:00 BRT   | GitHub Actions inicia automaticamente  |
| ~06:03 BRT  | Claude pesquisa cotações e gera texto  |
| ~06:06 BRT  | ElevenLabs gera o áudio em sua voz     |
| ~06:08 BRT  | Telegram recebe texto + MP3 do podcast |

> O computador não precisa estar ligado. O processo roda inteiramente na nuvem.
