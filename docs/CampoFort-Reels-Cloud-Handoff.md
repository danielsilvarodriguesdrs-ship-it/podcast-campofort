# CampoFort — Migração do "Diretor Criativo" (Reels diário) para a nuvem
### Documento de handoff para continuar no VS Code
_Gerado em 28/07/2026 · Autor do contexto: sessão Cowork · Destino: repositório do Boletim (GitHub Actions + Supabase)_

---

## 0. TL;DR (o que fazer no VS Code)

Migrar a tarefa agendada **`diretor-criativo-campofort`** (que hoje roda no PC do Daniel e falha quando a máquina está desligada) para a **mesma infraestrutura de nuvem do Boletim**: **GitHub Actions** (cron diário) + **Supabase** (histórico/anti-repetição) + **Telegram Bot API** (entrega). O roteiro completo passa a ser **um arquivo `.md` versionado no GitHub**, e o Telegram recebe uma **mensagem compacta com o link** do arquivo. Nada mais depende do computador estar ligado às 5h30.

**Ordem sugerida de execução (detalhada na seção 12):** confirmar segredos já existentes no repo → criar tabela no Supabase → adicionar `generator.py` + workflow → testar via `workflow_dispatch` → validar Telegram → **desativar a tarefa local**.

---

## 1. Por que estamos migrando (o problema)

- A tarefa `diretor-criativo-campofort` está **agendada para 05:35 (horário de Brasília), todo dia** (cron `30 5 * * *`), e **roda localmente no PC do Daniel**.
- Tarefas locais só executam com **a máquina ligada e o Cowork disponível**. Em 28/07, as tarefas da manhã só rodaram por volta das **11:40 BRT** (≈14:40 UTC) — sinal clássico de PC dormindo no horário: a execução atrasa (ou não ocorre) até a máquina acordar.
- Consequência real observada: o **roteiro foi criado no Drive** (parte robusta), mas a **mensagem do Telegram não chegou** de forma automática — o Daniel teve que pedir o reenvio manual.
- **Meta:** rodar 100% na nuvem, sem depender do PC, replicando o padrão que o **Boletim** já usa desde 01/07/2026.

---

## 2. Decisões já tomadas (confirmadas pelo Daniel)

| Tema | Decisão |
|---|---|
| **Acesso ao setup atual** | Daniel passará a **URL do repositório GitHub** do Boletim. |
| **Repositório** | **Mesmo repositório do Boletim** — reaproveitar os segredos (Telegram, Supabase, chave de IA) já configurados. |
| **Como ler o roteiro no campo** | **Arquivo no GitHub + link no Telegram** (abre formatado no celular). **Abandonar o Google Doc na nuvem** (evita ter que configurar conta de serviço Google). |

> Observação: a busca de anti-repetição hoje é feita via título de Google Docs no Drive. Na nuvem, isso passa a ser feito via **Supabase** (e/ou listando os arquivos em `roteiros/` do repo). Ver seção 4.3.

---

## 3. Histórico técnico / estado atual (fatos coletados)

**Tarefas agendadas existentes (via scheduler local):**

| taskId | Agenda | Cron | Estado | Observação |
|---|---|---|---|---|
| `diretor-criativo-campofort` | 05:35, todo dia | `30 5 * * *` | ativa (local) | **é a que vamos migrar** |
| `boletim-semanal-campofort` | 06:03, quarta | `0 6 * * 3` | ativa (local, mas **entrega real via GitHub Actions**) | **é o padrão a espelhar** |
| `resumo-matinal` | 06:07, seg–sex | `0 6 * * 1-5` | ativa (local) | não faz parte deste escopo |

**Sobre o Boletim (padrão a copiar):** a descrição da tarefa diz _"envio consolidado no GitHub Actions — Telegram, terça gera / quarta 06h envia, autônomo"_. **O SKILL.md local do Boletim está DESATIVADO** e descreve apenas o pipeline antigo (WhatsApp Web + PowerShell de áudio) — **não** é a fonte da verdade da nuvem. A configuração real (workflow `boletim_campofort.yml`, script, uso do Supabase, segredos) **está neste repositório** (`podcast-campofort`) — leia lá dentro (no VS Code) para espelhar 1:1.

**Ambiente Cowork atual:** conectados via Zapier estão Telegram, Gmail, WhatsApp e (a partir de 28/07) **GitHub**. Não há conector de Supabase — a parte de banco segue no VS Code.

**Entrega do Telegram hoje (Cowork):** feita via Zapier. **Na nuvem trocamos por chamada direta à Telegram Bot API** (`sendMessage`) usando o **bot token** (mesmo já usado pelo Boletim).

**Roteiros recentes (para o anti-repetição — NÃO repetir tema/gancho/formato):**

| Data | Título | Formato / semente | Tema técnico |
|---|---|---|---|
| 2026-07-25 (sáb) | **A PISTA NO CHÃO** | Inspeção técnica / mistério e descoberta | Escore fecal como diagnóstico; falta de PDR na seca |
| 2026-07-28 (ter) | **ENTERREI R$ 50 NO COCHO NA FRENTE DO FAZENDEIRO** | Simulação / cálculo financeiro com experimento visual | Custo por arroba vs. preço do saco; proteico-energético na transição águas–seca |

---

## 4. Arquitetura alvo (nuvem)

```
GitHub Actions (cron 08:35 UTC = 05:35 BRT, diário)
        |
        v
  generator.py
   1) idempotência: já existe roteiro de hoje? (Supabase) -> se sim, encerra
   2) lê últimos ~30 dias (Supabase) -> lista de títulos/ganchos/temas/formatos a EVITAR
   3) escolhe formato do dia pela semente (dia da semana)
   4) chama LLM (system prompt = "Diretor Criativo CampoFort") -> roteiro + autoavaliação
   5) valida autoavaliação (todas as notas >= 9,5; senão regenera)
   6) grava roteiros/CampoFort-Roteiro-Reels-AAAA-MM-DD.md -> commit & push (GITHUB_TOKEN)
   7) insere linha no Supabase (histórico)
   8) monta mensagem compacta HTML -> Telegram Bot API sendMessage (com link do arquivo)
```

### 4.1 Gatilho e fuso
- GitHub Actions usa **UTC**. Brasília é **UTC−3** (sem horário de verão). **05:35 BRT = 08:35 UTC** -> cron **`35 8 * * *`**.
- Incluir `workflow_dispatch` para disparo manual/teste.
- (Opcional) `concurrency` para evitar dois disparos simultâneos.

### 4.2 Motor de geração (LLM)
- O gerador precisa "pensar criativamente" sozinho na nuvem -> **chamar uma API de LLM**.
- **A CONFIRMAR no repo:** qual provedor/modelo o Boletim já usa e **o nome do secret** (provável `ANTHROPIC_API_KEY` com um modelo Claude, mas pode ser outro). **Reaproveitar o mesmo** para não criar custo/credencial nova.
- O gerador deve pedir **saída estruturada em JSON** (título, gancho, duração, formato, `corpo_md`, notas de autoavaliação) para facilitar o parsing e a validação do >= 9,5.

### 4.3 Anti-repetição (substitui a busca no Drive)
- Fonte primária: tabela **`reels_roteiros`** no Supabase (seção 9.1). Consultar os últimos 30 dias e injetar títulos/ganchos/temas/formatos no prompt como **lista de proibições**.
- Reforço opcional: listar os arquivos em `roteiros/` do próprio repo (git) como segunda camada.
- **Idempotência:** `data` é única na tabela -> se já houver linha de hoje, o job encerra (espelha o "PASSO 0 — verificar duplicata" do Boletim). Variável `FORCE=1` no `workflow_dispatch` permite forçar regeração.

### 4.4 Saída e leitura no campo
- Arquivo versionado: `roteiros/CampoFort-Roteiro-Reels-AAAA-MM-DD.md`.
- Link enviado no Telegram = URL do arquivo no GitHub (`blob` renderiza Markdown bonito no celular). Alternativa: GitHub Pages (fase 2).

### 4.5 Contrato do Telegram (mensagem compacta — manter idêntico ao de hoje)
- Endpoint: `POST https://api.telegram.org/bot<TELEGRAM_BOT_TOKEN>/sendMessage`
- Corpo: `chat_id=8772182868`, `parse_mode=HTML`, `disable_web_page_preview=true`, `text=<mensagem>`
- **Só** as tags `<b>`, `<i>`, `<a href="URL">`. Escapar `<`, `>`, `&` no texto dinâmico. Máx **4096** caracteres.

**Template (idêntico ao contrato atual):**
```
<b>🎬 Roteiro do dia — CampoFort</b>
<b>{TÍTULO}</b>
<i>Gancho (3s):</i> {GANCHO EM 1 LINHA}
Duração: {SEG}s · Formato: {FORMATO DO DIA}
<a href="{LINK_DO_ARQUIVO_NO_GITHUB}">Abrir roteiro completo</a>
```
> `chat_id` de destino confirmado nesta migração: **`8772182868`**.

---

## 5. Especificação funcional do roteiro (o gerador DEVE reproduzir isto)

> Recomendação: **commitar o prompt original** (o SKILL.md da tarefa `diretor-criativo-campofort`) como **system prompt** do gerador, trocando apenas a seção de *entrega* (Google Doc -> arquivo GitHub; Zapier -> Bot API).

**Persona:** Diretor Criativo, Estrategista de Conteúdo, Copywriter e Especialista em Crescimento Orgânico no Instagram, foco no agronegócio brasileiro. Missão: **1 ideia inédita/dia** de Reels para o Instagram da **CampoFort** (representante da **Cria Bem Nutrição Animal**). Tudo em **PT-BR**.

**Sobre o Daniel:** Zootecnista, mestrando em Produção Animal, Consultor Técnico Comercial. Posicionamento: **não** é influenciador; é **especialista técnico que vive o campo**. Objetivo não é seguidores — é **autoridade, confiança e relacionamento** para que produtores procurem a CampoFort espontaneamente.

**Público:** pecuaristas, produtores, confinadores, gerentes de fazenda, veterinários, zootecnistas, técnicos, estudantes de ciências agrárias. **Linguagem simples**.

**Estrutura obrigatória (nesta ordem exata):**
1. Título
2. Objetivo psicológico (gatilhos; por que prende; por que assistem até o fim)
3. Tempo (duração ideal em segundos)
4. Gancho inicial (primeiros 3s; **nunca começar falando**; interrupção de padrão)
5. Cenas (descrição de cada uma)
6. Narração (exatamente o que falar; natural, sem parecer propaganda)
7. Texto na tela (todas as legendas com o momento exato)
8. Sons (ambiente: passos, gado, trator, silagem, pássaros, porteira, cocho — nunca só música)
9. Música (só o estilo, nunca música específica)
10. Movimentos de câmera (travelling, POV, drone, close, plano aberto/detalhe, slow motion, hyperlapse, time lapse, entrada/saída)
11. Emoção
12. CTA (natural, que inicie conversa — nunca "segue para mais dicas")
13. Legenda do post (storytelling + valor + autoridade + CTA)
14. Hashtags (alcance amplo, médio e nichado)
15. Melhor horário (para produtores rurais brasileiros)
16. Estratégia (por que tem potencial de viralização)

**Variação de formato por dia (semente = dia da semana):** mini documentário, storytelling, estudo de caso, comparação visual, curiosidade inesperada, bastidores, visita técnica, experimento, simulação, cálculo financeiro, antes e depois, observação de campo, erro encontrado em fazenda, detalhe que quase ninguém percebe, POV, imersão, vlog técnico, inspeção técnica, raio-x da fazenda, mistério, descoberta, quebra de expectativa, humor leve do campo.

**Proibido:** "Você sabia?", "Você faz isso?", "Você conhece?", "3 dicas", "5 erros", "Top 10", "Mitos e verdades", listas comuns, conteúdo genérico/clichê de influenciador, frases motivacionais, polêmica, clickbait mentiroso.

**Embasamento:** dados técnicos corretos e, quando citados, apoiados em fontes sérias (Embrapa, SciELO/ABMVZ, CEPEA/ESALQ, Detmann & Paulino). Manter a preferência do Daniel por **rigor científico**.

**Autoavaliação obrigatória (0–10):** Originalidade · Retenção · Compartilhamento · Facilidade de gravação · Autoridade · Geração de novos clientes. **Se qualquer nota < 9,5 -> revisar e regenerar** antes de publicar.

**Lembrete final (1 linha):** lembrar o Daniel de **enviar os vídeos e fotos gravados para a etapa de formatação** (edição vertical 9:16, cortes, legendas queimadas e capa).

---

## 6. Estrutura de arquivos proposta no repositório

```
podcast-campofort/
├─ .github/workflows/
│   ├─ boletim_campofort.yml         # já existe
│   └─ reels-campofort.yml           # NOVO (seção 9.2)
├─ reels/
│   ├─ generator.py                  # NOVO (seção 9.3)
│   ├─ prompts/
│   │   └─ diretor_criativo_system.md  # NOVO: system prompt (base = SKILL.md atual, entrega adaptada)
│   └─ requirements.txt              # NOVO: anthropic (ou provedor usado), supabase, requests
├─ roteiros/
│   └─ CampoFort-Roteiro-Reels-AAAA-MM-DD.md   # gerado diariamente (commitado)
└─ (infra/segredos já existentes do Boletim)
```

---

## 7. Segredos necessários (Actions -> Settings -> Secrets and variables -> Actions)

| Secret | Uso | Origem |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Enviar via Bot API | **reaproveitar** o do Boletim |
| `TELEGRAM_CHAT_ID` | Destino (`8772182868`) | secret ou fixo no código |
| `SUPABASE_URL` | Conexão Supabase | **reaproveitar**/confirmar |
| `SUPABASE_SERVICE_ROLE_KEY` | Insert/select server-side | **reaproveitar**/confirmar |
| `ANTHROPIC_API_KEY` _(ou o provedor do Boletim)_ | Geração do roteiro | **CONFIRMAR** nome exato no repo |
| `GITHUB_TOKEN` | Commit do `.md` | **automático** (usar `permissions: contents: write`) |

---

## 8. Pendências a resolver no VS Code

1. **Provedor/modelo de LLM** e **nome do secret** já usados pelo Boletim (para reaproveitar).
2. **Nomes exatos** dos secrets de Supabase e Telegram já cadastrados.
3. **Backfill opcional:** importar para `reels_roteiros` os títulos/ganchos/temas dos roteiros já feitos (25/07 e 28/07 + Drive).
4. **Estilo do link:** `blob` do GitHub vs. GitHub Pages (fase 2).
5. **Desativar a tarefa local** só depois de 1–2 execuções de nuvem bem-sucedidas.

---

## 9. Esboços de código (rascunhos para refinar no VS Code)

### 9.1 Supabase — schema (SQL)
```sql
create table if not exists reels_roteiros (
  id           bigint generated always as identity primary key,
  data         date        not null unique,           -- 1 por dia (idempotência)
  titulo       text        not null,
  gancho       text,
  tema         text,
  formato      text,
  duracao_seg  integer,
  arquivo_url  text,
  corpo_md     text,
  autoavaliacao jsonb,
  created_at   timestamptz not null default now()
);
create index if not exists idx_reels_roteiros_data on reels_roteiros (data desc);
```

### 9.2 GitHub Actions — `.github/workflows/reels-campofort.yml`
```yaml
name: Reels CampoFort (diario)

on:
  schedule:
    - cron: "35 8 * * *"      # 05:35 BRT (UTC-3)
  workflow_dispatch:
    inputs:
      force:
        description: "Forcar regeracao mesmo se ja houver roteiro hoje"
        type: boolean
        default: false

permissions:
  contents: write

concurrency:
  group: reels-campofort
  cancel-in-progress: false

jobs:
  gerar-e-enviar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Instalar dependencias
        run: pip install -r reels/requirements.txt
      - name: Gerar roteiro + enviar Telegram
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}   # confirmar provedor
          SUPABASE_URL: ${{ secrets.SUPABASE_URL }}
          SUPABASE_SERVICE_ROLE_KEY: ${{ secrets.SUPABASE_SERVICE_ROLE_KEY }}
          TELEGRAM_BOT_TOKEN: ${{ secrets.TELEGRAM_BOT_TOKEN }}
          TELEGRAM_CHAT_ID: "8772182868"
          GITHUB_REPOSITORY: ${{ github.repository }}
          FORCE: ${{ inputs.force }}
        run: python reels/generator.py
      - name: Commitar roteiro do dia
        run: |
          git config user.name  "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add roteiros/*.md
          git commit -m "Roteiro Reels CampoFort $(date -u +%F)" || echo "nada a commitar"
          git push
```

### 9.3 Gerador — `reels/generator.py` (esqueleto)
```python
import os, sys, json, html, datetime, zoneinfo, requests
from supabase import create_client
# import anthropic  # ou o SDK do provedor confirmado no repo

BRT = zoneinfo.ZoneInfo("America/Sao_Paulo")
HOJE = datetime.datetime.now(BRT).date()
REPO = os.environ["GITHUB_REPOSITORY"]           # "usuario/repo"
FORCE = os.environ.get("FORCE", "false") == "true"

sb = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_ROLE_KEY"])

# 1) idempotencia
existe = sb.table("reels_roteiros").select("data").eq("data", str(HOJE)).execute()
if existe.data and not FORCE:
    print("Roteiro de hoje ja existe. Encerrando."); sys.exit(0)

# 2) historico p/ anti-repeticao (30 dias)
desde = str(HOJE - datetime.timedelta(days=30))
hist = sb.table("reels_roteiros").select("titulo,gancho,tema,formato") \
         .gte("data", desde).order("data", desc=True).execute().data
evitar = "\n".join(f"- {h['titulo']} | {h.get('formato')} | {h.get('tema')}" for h in hist)

# 3) formato do dia pela semente (dia da semana)
FORMATOS = ["mini documentario","estudo de caso","experimento","observacao de campo",
            "calculo financeiro","inspecao tecnica","antes e depois"]  # ajustar lista completa
formato_do_dia = FORMATOS[HOJE.weekday() % len(FORMATOS)]

# 4) chamar LLM com system prompt (arquivo) pedindo JSON estruturado
system_prompt = open("reels/prompts/diretor_criativo_system.md", encoding="utf-8").read()
user_msg = f"""Data: {HOJE}. Formato sugerido do dia: {formato_do_dia}.
NAO repita nada desta lista (titulos/formatos/temas ja usados):
{evitar or '(sem historico ainda)'}
Responda em JSON com as chaves: titulo, gancho, duracao_seg, formato, corpo_md,
autoavaliacao (objeto com 6 notas 0-10). corpo_md = roteiro completo em Markdown
na estrutura obrigatoria de 16 blocos."""

def gerar():
    # TODO: trocar pelo SDK do provedor confirmado; exigir JSON de volta
    ...

# 5) validar autoavaliacao (todas >= 9.5), regenerar ate N vezes
for _ in range(3):
    r = gerar()
    if all(float(v) >= 9.5 for v in r["autoavaliacao"].values()):
        break

# 6) gravar arquivo (o commit e feito pelo step do workflow)
nome = f"CampoFort-Roteiro-Reels-{HOJE}.md"
os.makedirs("roteiros", exist_ok=True)
open(f"roteiros/{nome}", "w", encoding="utf-8").write(r["corpo_md"])
arquivo_url = f"https://github.com/{REPO}/blob/main/roteiros/{nome}"

# 7) registrar no Supabase
sb.table("reels_roteiros").insert({
    "data": str(HOJE), "titulo": r["titulo"], "gancho": r["gancho"],
    "tema": r.get("tema"), "formato": r["formato"], "duracao_seg": r["duracao_seg"],
    "arquivo_url": arquivo_url, "corpo_md": r["corpo_md"], "autoavaliacao": r["autoavaliacao"],
}).execute()

# 8) Telegram (compacto, HTML, escapando texto dinamico)
def esc(s): return html.escape(str(s), quote=False)
texto = (
    "<b>🎬 Roteiro do dia — CampoFort</b>\n"
    f"<b>{esc(r['titulo'])}</b>\n"
    f"<i>Gancho (3s):</i> {esc(r['gancho'])}\n"
    f"Duracao: {esc(r['duracao_seg'])}s · Formato: {esc(r['formato'])}\n"
    f'<a href="{esc(arquivo_url)}">Abrir roteiro completo</a>'
)
requests.post(
    f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage",
    json={"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": texto,
          "parse_mode": "HTML", "disable_web_page_preview": True}, timeout=30
).raise_for_status()
print("OK:", arquivo_url)
```

### 9.4 `reels/requirements.txt`
```
requests
supabase
# anthropic            # (ou o SDK do provedor de IA confirmado no repo)
```

---

## 10. Adaptação do prompt original (o que muda vs. a tarefa local)

| Seção do SKILL.md local | Na nuvem |
|---|---|
| "Procure no Google Drive documentos 'CampoFort – Roteiro Reels –'…" | Ler histórico do **Supabase** (30 dias) + opcional lista de `roteiros/`. |
| "Salve como arquivo .md na pasta de saída" | Gravar em `roteiros/` e **commitar no GitHub**. |
| "Salve também cópia como Google Doc" | **Remover** — link do GitHub cumpre o papel. |
| "Envie ao Telegram via Zapier" | **Telegram Bot API** direta (`sendMessage`). |
| `chat_id`, formato HTML, template compacto | **Mantidos idênticos** (seção 4.5). |
| Autoavaliação >= 9,5, proibições, 16 blocos, variação por dia | **Mantidos** — regras do system prompt + validação no código. |

---

## 11. Desativar a tarefa local (só após validar a nuvem)

Depois de **1–2 execuções de nuvem bem-sucedidas** (arquivo commitado + Telegram recebido), desativar/remover a tarefa local `diretor-criativo-campofort` para não duplicar:
- Via ferramenta de tarefas agendadas do Cowork (`enabled:false` ou excluir), **ou**
- Marcar o SKILL.md local como `DESATIVADA (AAAA-MM-DD): migrado para GitHub Actions` — mesmo padrão do Boletim.

---

## 12. Roteiro de execução no VS Code (passo a passo)

1. **Abrir `podcast-campofort`** e ler: `boletim_campofort.yml`, script do Boletim, uso do Supabase e **nomes exatos dos secrets**.
2. **Criar a tabela** `reels_roteiros` no Supabase (SQL da seção 9.1).
3. **Adicionar arquivos:** `reels/generator.py`, `reels/prompts/diretor_criativo_system.md`, `reels/requirements.txt`, `.github/workflows/reels-campofort.yml`.
4. **Ajustar o `generator.py`** ao provedor de IA real (SDK + modelo + parsing do JSON).
5. **Conferir/adicionar secrets** que faltarem (seção 7).
6. **Testar:** rodar por `workflow_dispatch` com `force:true` -> verificar arquivo commitado + Telegram recebido.
7. **(Opcional) Backfill** dos roteiros 25/07 e 28/07 na tabela.
8. **Validar 1 execução agendada real** (05:35 BRT).
9. **Desativar a tarefa local** (seção 11).

---

## 13. Prompt pronto para colar no Claude Code (VS Code)

```
Contexto: este repo (podcast-campofort) ja roda o "Boletim CampoFort" via GitHub Actions + Supabase + Telegram.
Quero adicionar, no MESMO repo, um job diario equivalente para o "Diretor Criativo — Reels CampoFort",
usando docs/CampoFort-Reels-Cloud-Handoff.md como especificacao.

Tarefas:
1) Leia .github/workflows/boletim_campofort.yml e o script do Boletim e me diga os NOMES EXATOS dos secrets
   ja usados (Telegram bot token, Supabase URL/side key, e a chave/modelo de IA).
2) Crie a tabela Supabase `reels_roteiros` (schema no handoff, secao 9.1).
3) Crie reels/generator.py, reels/prompts/diretor_criativo_system.md, reels/requirements.txt e
   .github/workflows/reels-campofort.yml conforme o handoff, REAPROVEITANDO os secrets existentes
   e o MESMO provedor de IA do Boletim.
4) O gerador deve: garantir 1 roteiro/dia (idempotencia), evitar repeticao pelos ultimos 30 dias,
   validar autoavaliacao (todas as notas >= 9,5, senao regerar), commitar
   roteiros/CampoFort-Roteiro-Reels-AAAA-MM-DD.md e enviar a mensagem compacta HTML ao Telegram
   (chat_id 8772182868) com o LINK do arquivo no GitHub.
5) Rode em modo de teste (workflow_dispatch, force=true) e ajuste ate o Telegram chegar.
Nao desative a tarefa local ainda — faremos isso apos 1–2 execucoes de nuvem bem-sucedidas.
```

---

_Fim do handoff. Fonte da verdade da nuvem = repositorio `podcast-campofort` (a ser lido no VS Code). Este documento consolida o historico e as decisoes desta sessao para retomar o trabalho sem perder contexto._
