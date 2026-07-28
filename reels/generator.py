#!/usr/bin/env python3
# Gerador diario do Reels 'Diretor Criativo CampoFort' -> roda no GitHub Actions.
# Fluxo: idempotencia -> historico (anti-repeticao) -> LLM -> autoavaliacao (>=9,5)
#        -> commit do .md -> registro no Supabase -> Telegram com link.
# Ajuste LLM_MODEL / provedor conforme o que o Boletim ja usa.

import os
import sys
import json
import base64
import html
import datetime
import zoneinfo
import requests
from supabase import create_client
import anthropic

BRT = zoneinfo.ZoneInfo('America/Sao_Paulo')
HOJE = datetime.datetime.now(BRT).date()
REPO = os.environ['GITHUB_REPOSITORY']
BRANCH = os.environ.get('GIT_BRANCH', 'main')
FORCE = os.environ.get('FORCE', 'false').lower() == 'true'
LLM_MODEL = os.environ.get('LLM_MODEL', 'claude-3-5-sonnet-latest')
MAX_TRIES = int(os.environ.get('MAX_TRIES', '4'))
GH_TOKEN = os.environ['GITHUB_TOKEN']
TG_TOKEN = os.environ['TELEGRAM_BOT_TOKEN']
TG_CHAT = os.environ.get('TELEGRAM_CHAT_ID', '8772182868')

sb = create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
client = anthropic.Anthropic(api_key=os.environ['ANTHROPIC_API_KEY'])

FORMATOS = [
    'mini documentario', 'storytelling', 'estudo de caso', 'comparacao visual',
    'curiosidade inesperada', 'bastidores', 'visita tecnica', 'experimento',
    'simulacao', 'calculo financeiro', 'antes e depois', 'observacao de campo',
    'erro encontrado em fazenda', 'detalhe que quase ninguem percebe', 'POV',
    'imersao', 'vlog tecnico', 'inspecao tecnica', 'raio-x da fazenda',
    'misterio', 'descoberta', 'quebra de expectativa', 'humor leve do campo',
]

# Baseline p/ nao repetir enquanto a tabela ainda nao tem historico (backfill depois).
BASELINE_USADOS = [
    'A PISTA NO CHAO | inspecao tecnica | escore fecal / PDR na seca (2026-07-25)',
    'ENTERREI R$ 50 NO COCHO NA FRENTE DO FAZENDEIRO | calculo financeiro | custo por arroba (2026-07-28)',
]


def parse_json(txt):
    txt = txt.strip()
    ini = txt.find('{')
    fim = txt.rfind('}')
    if ini == -1 or fim == -1:
        raise ValueError('Resposta do LLM sem JSON: ' + txt[:200])
    return json.loads(txt[ini:fim + 1])


def commit_file(path, conteudo, mensagem):
    url = 'https://api.github.com/repos/' + REPO + '/contents/' + path
    headers = {'Authorization': 'Bearer ' + GH_TOKEN, 'Accept': 'application/vnd.github+json'}
    sha = None
    g = requests.get(url, headers=headers, params={'ref': BRANCH}, timeout=30)
    if g.status_code == 200:
        sha = g.json().get('sha')
    body = {
        'message': mensagem,
        'content': base64.b64encode(conteudo.encode('utf-8')).decode('ascii'),
        'branch': BRANCH,
    }
    if sha:
        body['sha'] = sha
    r = requests.put(url, headers=headers, json=body, timeout=30)
    r.raise_for_status()
    return r.json()['content']['html_url']


def esc(s):
    return html.escape(str(s), quote=False)


# 1) Idempotencia: 1 roteiro por dia
ja = sb.table('reels_roteiros').select('data').eq('data', str(HOJE)).execute()
if ja.data and not FORCE:
    print('Ja existe roteiro de hoje (' + str(HOJE) + '). Encerrando.')
    sys.exit(0)

# 2) Historico (30 dias) para anti-repeticao
desde = str(HOJE - datetime.timedelta(days=30))
hist = (sb.table('reels_roteiros')
        .select('titulo,gancho,tema,formato')
        .gte('data', desde).order('data', desc=True).execute().data)
linhas_hist = []
for h in hist:
    linhas_hist.append('- ' + str(h.get('titulo')) + ' | ' + str(h.get('formato')) + ' | ' + str(h.get('tema')))
evitar = '\n'.join(BASELINE_USADOS + linhas_hist)

# 3) Formato do dia (semente = semana ISO + dia da semana)
sem = HOJE.isocalendar().week
formato_do_dia = FORMATOS[(sem + HOJE.weekday()) % len(FORMATOS)]

# 4) System prompt + pedido
aqui = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(aqui, 'prompts', 'diretor_criativo_system.md'), encoding='utf-8') as fp:
    system_prompt = fp.read()
user_msg = '\n'.join([
    'Data de hoje: ' + str(HOJE) + '.',
    'Formato sugerido do dia (semente): ' + formato_do_dia + '.',
    '',
    'NAO repita titulo, gancho, tema nem formato de nada desta lista ja usada:',
    evitar,
    '',
    'Responda SOMENTE com o JSON definido no system prompt.',
])


def gerar_uma():
    msg = client.messages.create(
        model=LLM_MODEL,
        max_tokens=4000,
        system=system_prompt,
        messages=[{'role': 'user', 'content': user_msg}],
    )
    txt = ''.join(getattr(b, 'text', '') for b in msg.content)
    return parse_json(txt)


# 5) Gerar + validar autoavaliacao (todas >= 9,5)
melhor = None
melhor_min = -1.0
for tentativa in range(1, MAX_TRIES + 1):
    try:
        r = gerar_uma()
    except Exception as e:
        print('Tentativa ' + str(tentativa) + ' falhou: ' + str(e))
        continue
    notas = [float(v) for v in r['autoavaliacao'].values()]
    print('Tentativa ' + str(tentativa) + ' - nota minima: ' + str(min(notas)))
    if min(notas) >= 9.5:
        melhor = r
        break
    if min(notas) > melhor_min:
        melhor_min = min(notas)
        melhor = r
if melhor is None:
    print('Falha: nenhum roteiro valido gerado.')
    sys.exit(1)
r = melhor

# 6) Salvar .md + commit no repo
nome = 'CampoFort-Roteiro-Reels-' + str(HOJE) + '.md'
path = 'roteiros/' + nome
arquivo_url = commit_file(path, r['corpo_md'], 'Roteiro Reels CampoFort ' + str(HOJE))
print('Commit OK: ' + arquivo_url)

# 7) Registrar no Supabase
sb.table('reels_roteiros').insert({
    'data': str(HOJE),
    'titulo': r.get('titulo'),
    'gancho': r.get('gancho'),
    'tema': r.get('tema'),
    'formato': r.get('formato', formato_do_dia),
    'duracao_seg': r.get('duracao_seg'),
    'arquivo_url': arquivo_url,
    'corpo_md': r.get('corpo_md'),
    'autoavaliacao': r.get('autoavaliacao'),
}).execute()

# 8) Telegram (compacto, HTML)
linhas = [
    '<b>🎬 Roteiro do dia — CampoFort</b>',
    '<b>' + esc(r.get('titulo')) + '</b>',
    '<i>Gancho (3s):</i> ' + esc(r.get('gancho')),
    'Duracao: ' + esc(r.get('duracao_seg')) + 's · Formato: ' + esc(r.get('formato', formato_do_dia)),
    '<a href="' + arquivo_url + '">Abrir roteiro completo</a>',
]
texto = '\n'.join(linhas)
resp = requests.post(
    'https://api.telegram.org/bot' + TG_TOKEN + '/sendMessage',
    json={'chat_id': TG_CHAT, 'text': texto, 'parse_mode': 'HTML', 'disable_web_page_preview': True},
    timeout=30,
)
resp.raise_for_status()
print('Telegram enviado. OK.')
