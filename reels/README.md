# Reels CampoFort - automacao na nuvem (GitHub Actions + Supabase + Telegram)

Gera 1 roteiro de Reels por dia, sem depender do PC do Daniel ligado. Espelha o padrao do Boletim.
Especificacao completa: `docs/CampoFort-Reels-Cloud-Handoff.md`.

## Arquivos
- `reels/generator.py` - gera o roteiro (LLM), valida autoavaliacao (>=9,5), commita o .md, registra no Supabase e envia o Telegram com o link.
- `reels/prompts/diretor_criativo_system.md` - system prompt (persona + regras + formato de saida JSON).
- `reels/requirements.txt` - dependencias.
- `reels/reels-campofort.yml` - workflow. **Mova para `.github/workflows/reels-campofort.yml`.**

## Passo a passo (VS Code)

1. **Mover o workflow:** `reels/reels-campofort.yml` -> `.github/workflows/reels-campofort.yml`.
2. **Confirmar o provedor de IA do Boletim.** Se for Anthropic (Claude), ja funciona. Senao, ajuste `generator.py` e `requirements.txt`. Defina a variavel de repositorio `LLM_MODEL` (Settings -> Secrets and variables -> Actions -> Variables) com o modelo correto (ex.: um modelo Claude atual).
3. **Criar a tabela no Supabase** (SQL Editor):

```sql
create table if not exists reels_roteiros (
  id bigint generated always as identity primary key,
  data date not null unique,
  titulo text not null,
  gancho text,
  tema text,
  formato text,
  duracao_seg integer,
  arquivo_url text,
  corpo_md text,
  autoavaliacao jsonb,
  created_at timestamptz not null default now()
);
create index if not exists idx_reels_roteiros_data on reels_roteiros (data desc);
```

4. **Secrets (Actions):** `ANTHROPIC_API_KEY` (ou o provedor do Boletim), `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `TELEGRAM_BOT_TOKEN`. Reaproveite os que ja existem do Boletim. `TELEGRAM_CHAT_ID` ja esta fixo no workflow (8772182868). `GITHUB_TOKEN` e automatico.
5. **Testar:** Actions -> Reels CampoFort -> Run workflow (force = true). Confira: arquivo novo em `roteiros/` + mensagem no Telegram.
6. **Ativar a agenda:** descomente o bloco `schedule` no workflow (`35 8 * * *` = 05:35 BRT).
7. **(Opcional) Backfill:** insira na tabela os roteiros ja feitos (25/07 e 28/07) para o anti-repeticao comecar com memoria.
8. **Desativar a tarefa local** `diretor-criativo-campofort` so depois de 1 a 2 execucoes de nuvem bem-sucedidas.

## Observacoes
- O `generator.py` commita o `.md` via API do GitHub e so entao envia o Telegram, entao o link ja funciona quando a mensagem chega.
- Idempotencia: 1 roteiro por dia (coluna `data` unica). Use `force = true` para regenerar no mesmo dia.
- Fuso: o cron do GitHub Actions e em UTC. `35 8 * * *` = 05:35 no horario de Brasilia (UTC-3).
