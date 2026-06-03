#!/usr/bin/env python3
"""
Pipeline Cloud CampoFort - GitHub Actions
Toda quarta-feira 07h Brasilia, sem depender do PC.

Fluxo:
  1. Coleta dados (AwesomeAPI, BCB, scraping agro)
  2. Gera boletim + roteiro + mensagem Telegram via Claude Haiku
  3. Gera MP3 via Azure Neural TTS (fallback: Edge TTS)
  4. Sobe MP3 para GitHub Releases
  5. Atualiza docs/podcast_feed.xml (RSS Spotify via GitHub Pages)
  6. Envia mensagem Telegram com link Spotify

Secrets GitHub (Settings > Secrets > Actions):
  ANTHROPIC_API_KEY    - Claude API
  TELEGRAM_BOT_TOKEN   - @BotFather
  TELEGRAM_CHAT_ID     - seu ID pessoal
  AZURE_SPEECH_KEY     - Azure Cognitive Services (tier F0 gratis)
  AZURE_SPEECH_REGION  - ex: brazilsouth
  SPOTIFY_URL          - URL do show no Spotify (quando configurado)
  GITHUB_TOKEN         - automatico nas Actions
"""

import asyncio
import json
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import formatdate
from pathlib import Path

import anthropic
import edge_tts
import requests
from bs4 import BeautifulSoup

# ── Configuracoes ─────────────────────────────────────────────────────────────

GITHUB_REPO  = os.environ.get("GITHUB_REPO", "danielsilvarodriguesdrs-ship-it/podcast-campofort")
RELEASE_TAG  = "audio"

ANTHROPIC_KEY   = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN  = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT   = os.environ.get("TELEGRAM_CHAT_ID", "")
GITHUB_TOKEN    = os.environ.get("GITHUB_TOKEN", "")
SPOTIFY_URL     = os.environ.get("SPOTIFY_URL", "")
AZURE_KEY       = os.environ.get("AZURE_SPEECH_KEY", "")
AZURE_REGION    = os.environ.get("AZURE_SPEECH_REGION", "brazilsouth")
AZURE_VOICE     = "pt-BR-ToniNeural"    # masculino, firme, jornalistico
EDGE_VOICE      = "pt-BR-AntonioNeural" # fallback

BRT         = timezone(timedelta(hours=-3))
NOW         = datetime.now(BRT)
DATE_BR     = NOW.strftime("%d/%m/%Y")
DATE_FILE   = NOW.strftime("%Y%m%d")
DATE_ISO    = NOW.strftime("%Y-%m-%d")
WEEKDAY_PT  = ["Segunda-feira","Terca-feira","Quarta-feira",
               "Quinta-feira","Sexta-feira","Sabado","Domingo"][NOW.weekday()]

BOLETIM_PATH   = Path(f"boletim_semanal_campofort_{DATE_FILE}.md")
ROTEIRO_PATH   = Path(f"roteiro_podcast_campofort_{DATE_FILE}.md")
MP3_PATH       = Path(f"podcast_campofort_{DATE_FILE}.mp3")
TG_PATH        = Path(f"mensagem_telegram_{DATE_FILE}.txt")
RSS_PATH       = Path("docs/podcast_feed.xml")
EPISODIOS_PATH = Path("episodios.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# ── 1. Coleta de Dados ────────────────────────────────────────────────────────

def get_dollar() -> str:
    try:
        r = requests.get("https://economia.awesomeapi.com.br/json/last/USD-BRL", timeout=10)
        d = r.json()["USDBRL"]
        return f"R$ {float(d['bid']):.2f} ({float(d['pctChange']):+.2f}% no dia)"
    except Exception as e:
        return f"indisponivel ({e})"


def get_dollar_history(days: int = 5) -> str:
    """Retorna historico do dolar em formato tabulado para o prompt."""
    try:
        r = requests.get(
            f"https://economia.awesomeapi.com.br/json/daily/USD-BRL/{days}",
            timeout=10)
        linhas = []
        for row in reversed(r.json()):
            dt  = datetime.fromtimestamp(int(row["timestamp"]), tz=BRT).strftime("%d/%m")
            bid = float(row["bid"])
            pct = float(row["pctChange"])
            seta = "up" if pct > 0 else ("down" if pct < 0 else "flat")
            linhas.append(f"{dt}|R$ {bid:.2f}|{pct:+.2f}%|{seta}")
        return "\n".join(linhas)
    except Exception as e:
        return f"indisponivel ({e})"


def get_selic() -> str:
    try:
        r = requests.get(
            "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json",
            timeout=10)
        return f"{float(r.json()[0]['valor']):.2f}% ao ano"
    except Exception as e:
        return f"indisponivel ({e})"


def fetch_page_text(url: str, max_chars: int = 3000) -> str:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        for tag in soup(["script","style","nav","header","footer","aside","form","button"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return re.sub(r"\n{3,}", "\n\n", text)[:max_chars]
    except Exception as e:
        return f"[erro: {e}]"


def gather_market_data() -> dict:
    print("  -> Dolar e Selic...")
    raw = {
        "dollar":         get_dollar(),
        "dollar_history": get_dollar_history(5),
        "selic":          get_selic(),
    }
    sources = {
        "boi_go_mt": [
            "https://www.noticiasagricolas.com.br/cotacoes/boi-gordo",
            "https://www.canalrural.com.br/cotacoes/boi/",
        ],
        "milho": ["https://www.noticiasagricolas.com.br/cotacoes/milho"],
        "soja":  ["https://www.noticiasagricolas.com.br/cotacoes/soja"],
        "politica_revistaoeste": [
            "https://revistaoeste.com/agronegocio/",
            "https://revistaoeste.com/politica/",
        ],
        "regulatorio": [
            "https://www.noticiasagricolas.com.br/noticias/boi",
            "https://www.canalrural.com.br/pecuaria/",
        ],
    }
    for key, urls in sources.items():
        texts = []
        for url in urls:
            print(f"  -> {url}")
            texts.append(fetch_page_text(url))
            time.sleep(1)
        raw[key] = "\n---\n".join(texts)
    return raw


# ── 2. Geracao de Conteudo via Claude ─────────────────────────────────────────

SYSTEM_PROMPT = (
    "Voce e o gerador do Boletim Semanal CampoFort, apresentado por Daniel Rodrigues.\n\n"
    "REGRAS INVIOLAVEIS - VALEM PARA OS TRES OUTPUTS (boletim, roteiro, telegram):\n"
    "- Cotacoes de boi gordo, milho e soja SEMPRE para Goias E Mato Grosso lado a lado\n"
    "- Politica da semana: cite SOMENTE fontes da Revista Oeste (revistaoeste.com)\n"
    "- FORMATO DE VALORES: use SEMPRE digitos + unidade em todos os textos:\n"
    "    CORRETO: R$ 321,50/@  |  R$ 64,50/sc  |  R$ 5,02  |  14,50% ao ano\n"
    "    PROIBIDO: 'trezentos e vinte', 'quatorze virgula', 'cinco reais e dois centavos'\n"
    "- Tom: autoridade tecnica, firme, direto, didatico\n"
    "- Telegram: 2500-3500 chars, *negrito*, _italico_"
)


def _fmt_historico(raw: str) -> str:
    """Converte historico bruto em texto legivel para o prompt."""
    linhas = []
    for line in raw.strip().split("\n"):
        parts = line.split("|")
        if len(parts) == 4:
            dt, bid, pct, seta = parts
            emoji = {"up": "[alta]", "down": "[queda]", "flat": "[estavel]"}.get(seta, "")
            linhas.append(f"  {dt}: {bid} ({pct}) {emoji}")
    return "\n".join(linhas) if linhas else "  indisponivel"


def _build_user_msg(data: dict) -> str:
    hist = _fmt_historico(data.get("dollar_history", ""))

    instrucoes_boletim = (
        "REGRA DE OURO: valores SEMPRE em digitos (R$ X,XX/@ ou R$ X,XX/sc ou X,XX% ao ano).\n"
        "NUNCA escreva valores por extenso em nenhuma secao.\n\n"
        "Estrutura obrigatoria:\n"
        "- Cabecalho: data e nome\n"
        "- BOI GORDO GOIAS / MATO GROSSO: preco R$/@ GO e MT, diferencial, analise\n"
        "- MILHO GOIAS / MATO GROSSO: preco R$/sc, analise\n"
        "- SOJA GOIAS / MATO GROSSO: preco R$/sc, analise\n"
        "- DOLAR E SELIC: mini-grafico dos 5 dias (ex: 02/06: R$ 5,02 [alta]), impacto\n"
        "- POLITICA DA SEMANA - Revista Oeste: destaque principal com URL\n"
        "- PANORAMA REGULATORIO E COMERCIAL\n"
        "- PROJECOES PROXIMA SEMANA\n"
        "- Assinatura com placeholder [LINK DO PODCAST]"
    )

    instrucoes_roteiro = (
        "ABERTURA OBRIGATORIA (palavra por palavra):\n"
        "'Bom dia, produtor e produtora rural. "
        "Este e o Boletim Informativo CampoFort, apresentado por Daniel Rodrigues.'\n"
        "Em seguida: 'Hoje e " + WEEKDAY_PT + ", " + DATE_BR + ". Vamos aos mercados.'\n\n"
        "FORMATO DE VALORES: digitos com unidade.\n"
        "CORRETO: 'R$ 321,50 por arroba', '14,50% ao ano', 'R$ 5,02 por dolar'\n"
        "PROIBIDO: 'trezentos e vinte', 'quatorze virgula'\n\n"
        "SECAO MACRO: apresente com tendencia didatica.\n"
        "Exemplo: 'O dolar encerrou hoje a R$ 5,02. Nos ultimos cinco dias, oscilou "
        "entre R$ 4,98 e R$ 5,04, acumulando alta de 0,8%. Para o produtor que exporta, "
        "isso significa [impacto pratico].'\n\n"
        "POLITICA: antes de cada destaque importante, diga 'DESTAQUE:' em voz firme.\n\n"
        "ENCERRAMENTO OBRIGATORIO:\n"
        "'Nutricao estrategica. Resultado no campo. Ate a proxima quarta-feira.'"
    )

    instrucoes_telegram = (
        "2500-3500 caracteres. *negrito* para titulos e valores. _italico_ para analises.\n\n"
        "SECAO MACRO - inclua mini-grafico com emojis de direcao:\n"
        "*DOLAR - ULTIMOS 5 DIAS*\n"
        "`DD/MM: R$ X,XX` (use emoji apropriado: 📈 alta | 📉 queda | ➡️ estavel)\n\n"
        "SECAO POLITICA - cada noticia da Revista Oeste em linha separada com ▶️\n\n"
        "FINAL OBRIGATORIO antes da assinatura:\n"
        "*Ouca o episodio completo:*\n"
        "[LINK_SPOTIFY]\n\n"
        "_Daniel Rodrigues | CampoFort_\n"
        "_Nutricao estrategica. Resultado no campo._"
    )

    return (
        f"Data de hoje: {WEEKDAY_PT}, {DATE_BR}\n\n"
        f"DADOS COLETADOS:\n"
        f"Dolar hoje: {data['dollar']}\n"
        f"Selic: {data['selic']}\n\n"
        f"Historico dolar (5 dias uteis):\n{hist}\n\n"
        f"BOI GORDO (GO e MT):\n{data['boi_go_mt'][:2500]}\n\n"
        f"MILHO:\n{data['milho'][:1500]}\n\n"
        f"SOJA:\n{data['soja'][:1500]}\n\n"
        f"POLITICA (Revista Oeste):\n{data['politica_revistaoeste'][:2000]}\n\n"
        f"REGULATORIO:\n{data['regulatorio'][:1500]}\n\n"
        "---\n"
        "Gere os tres conteudos no formato JSON exato abaixo.\n"
        "Nao adicione nenhum texto fora do JSON.\n\n"
        '{{\n'
        '  "boletim_md": "<markdown completo>",\n'
        '  "roteiro_narracao": "<texto TTS 4-5 min>",\n'
        '  "mensagem_telegram": "<mensagem Telegram completa>"\n'
        '}}\n\n'
        f"=== INSTRUCOES boletim_md ===\n{instrucoes_boletim}\n\n"
        f"=== INSTRUCOES roteiro_narracao ===\n{instrucoes_roteiro}\n\n"
        f"=== INSTRUCOES mensagem_telegram ===\n{instrucoes_telegram}"
    )


def generate_content(data: dict) -> dict:
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=6000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _build_user_msg(data)}]
    )
    raw = response.content[0].text.strip()
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m:
        raise ValueError(f"Claude nao retornou JSON valido:\n{raw[:400]}")
    result = json.loads(m.group())
    if "mensagem_whatsapp" in result and "mensagem_telegram" not in result:
        result["mensagem_telegram"] = result.pop("mensagem_whatsapp")
    return result


# ── 3. Geracao de Audio ───────────────────────────────────────────────────────
#
# Prioridade:
#   1. Azure Neural TTS (pt-BR-ToniNeural) - qualidade premium, F0 gratis
#   2. Edge TTS (pt-BR-AntonioNeural)      - fallback sem configuracao

def _limpar_texto(text: str) -> str:
    text = re.sub(r"#{1,6}\s+", "", text)
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)
    text = re.sub(r"_{1,2}([^_]+)_{1,2}", r"\1", text)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
    return text.strip()


def _build_ssml(text: str) -> str:
    import xml.sax.saxutils as su
    safe = su.escape(text)
    return (
        "<speak version='1.0' xml:lang='pt-BR' "
        "xmlns='http://www.w3.org/2001/10/synthesis'>"
        f"<voice name='{AZURE_VOICE}'>"
        "<prosody rate='-8%' pitch='-2%'>"
        f"{safe}"
        "</prosody></voice></speak>"
    )


def generate_audio_azure(text: str, path: Path) -> bool:
    if not AZURE_KEY:
        return False
    url = f"https://{AZURE_REGION}.tts.speech.microsoft.com/cognitiveservices/v1"
    headers = {
        "Ocp-Apim-Subscription-Key": AZURE_KEY,
        "Content-Type":              "application/ssml+xml",
        "X-Microsoft-OutputFormat":  "audio-24khz-160kbitrate-mono-mp3",
        "User-Agent":                "CampoFort-Pipeline/1.0",
    }
    try:
        r = requests.post(url, headers=headers,
                          data=_build_ssml(text).encode("utf-8"), timeout=120)
        if r.status_code == 200:
            path.write_bytes(r.content)
            print(f"  OK Azure TTS ({AZURE_VOICE}) - {len(r.content)//1024} KB")
            return True
        print(f"  ✗ Azure TTS {r.status_code}: {r.text[:200]}")
        return False
    except Exception as e:
        print(f"  ✗ Azure TTS erro: {e}")
        return False


async def _edge_async(text: str, path: Path) -> None:
    comm = edge_tts.Communicate(text, voice=EDGE_VOICE)
    await comm.save(str(path))


def generate_audio_edge(text: str, path: Path) -> None:
    asyncio.run(_edge_async(text, path))
    print(f"  OK Edge TTS ({EDGE_VOICE}) - fallback")


def generate_audio(roteiro_text: str, path: Path) -> None:
    text = _limpar_texto(roteiro_text)
    if AZURE_KEY:
        print(f"  Usando Azure Neural TTS ({AZURE_VOICE})...")
        if generate_audio_azure(text, path):
            return
        print("  Fallback para Edge TTS...")
    generate_audio_edge(text, path)


# ── 4. GitHub Releases ────────────────────────────────────────────────────────

def get_or_create_release(gh_headers: dict) -> dict:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{RELEASE_TAG}"
    r = requests.get(url, headers=gh_headers)
    if r.status_code == 200:
        return r.json()
    r = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/releases",
        headers=gh_headers,
        json={"tag_name": RELEASE_TAG, "name": "Episodios CampoFort",
              "draft": False, "prerelease": False}
    )
    r.raise_for_status()
    return r.json()


def upload_mp3(mp3_path: Path) -> str:
    gh = {
        "Authorization":           f"Bearer {GITHUB_TOKEN}",
        "Accept":                  "application/vnd.github+json",
        "X-GitHub-Api-Version":    "2022-11-28",
    }
    release = get_or_create_release(gh)
    for asset in release.get("assets", []):
        if asset["name"] == mp3_path.name:
            requests.delete(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/assets/{asset['id']}",
                headers=gh)
            time.sleep(1)
    upload_url = release["upload_url"].split("{")[0]
    with open(mp3_path, "rb") as f:
        r = requests.post(f"{upload_url}?name={mp3_path.name}",
                          headers={**gh, "Content-Type": "audio/mpeg"}, data=f)
    r.raise_for_status()
    return r.json()["browser_download_url"]


# ── 5. RSS Feed ───────────────────────────────────────────────────────────────

def _sub(parent, tag, text=None, **attrib):
    el = ET.SubElement(parent, tag, **attrib)
    if text:
        el.text = text
    return el


def update_rss(audio_url: str, titulo: str, descricao: str,
               duracao_seg: int, mp3_size: int) -> None:
    ET.register_namespace("itunes",  "http://www.itunes.com/dtds/podcast-1.0.dtd")
    ET.register_namespace("content", "http://purl.org/rss/1.0/modules/content/")
    ns = "http://www.itunes.com/dtds/podcast-1.0.dtd"
    RSS_PATH.parent.mkdir(parents=True, exist_ok=True)

    if RSS_PATH.exists():
        tree = ET.parse(RSS_PATH)
        root = tree.getroot()
        channel = root.find("channel")
    else:
        root    = ET.Element("rss", version="2.0",
                             attrib={"xmlns:itunes": ns,
                                     "xmlns:content": "http://purl.org/rss/1.0/modules/content/"})
        channel = ET.SubElement(root, "channel")
        _sub(channel, "title",       "Boletim CampoFort")
        _sub(channel, "link",        "https://campofort.com.br")
        _sub(channel, "description", "Boletim semanal — Goias e Mato Grosso.")
        _sub(channel, "language",    "pt-BR")
        ET.SubElement(channel, f"{{{ns}}}author").text   = "Daniel Rodrigues — CampoFort"
        ET.SubElement(channel, f"{{{ns}}}explicit").text = "false"
        cat = ET.SubElement(channel, f"{{{ns}}}category", text="Business")
        ET.SubElement(cat, f"{{{ns}}}category", text="Agriculture")

    item = ET.Element("item")
    _sub(item, "title",       titulo)
    _sub(item, "description", descricao)
    _sub(item, "pubDate",     formatdate(NOW.timestamp()))
    _sub(item, "guid",        f"campofort-{DATE_FILE}", isPermaLink="false")
    ET.SubElement(item, "enclosure",
                  url=audio_url, length=str(mp3_size), type="audio/mpeg")
    ET.SubElement(item, f"{{{ns}}}duration").text = str(duracao_seg)
    ET.SubElement(item, f"{{{ns}}}summary").text  = descricao

    existing = channel.find("item")
    pos = list(channel).index(existing) if existing is not None else len(list(channel))
    channel.insert(pos, item)
    tree2 = ET.ElementTree(root)
    ET.indent(tree2, space="  ")
    tree2.write(RSS_PATH, encoding="utf-8", xml_declaration=True)


def update_episodios_json(audio_url: str, titulo: str, descricao: str,
                          duracao_seg: int) -> None:
    data = {}
    if EPISODIOS_PATH.exists():
        data = json.loads(EPISODIOS_PATH.read_text(encoding="utf-8"))
    episodios = [e for e in data.get("episodios", []) if e.get("data") != DATE_ISO]
    episodios.insert(0, {
        "data": DATE_ISO, "titulo": titulo, "descricao": descricao,
        "duracao_seg": duracao_seg, "audio_url": audio_url, "mp3_local": MP3_PATH.name,
    })
    data["episodios"] = episodios
    EPISODIOS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")


# ── 6. Telegram ───────────────────────────────────────────────────────────────

def send_telegram(message: str) -> bool:
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print("  ✗ Secrets do Telegram nao configurados.")
        return False
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    parts   = [message[i:i+4000] for i in range(0, len(message), 4000)]
    success = True
    for i, part in enumerate(parts, 1):
        try:
            r = requests.post(api_url, json={
                "chat_id":    TELEGRAM_CHAT,
                "text":       part,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False,
            }, timeout=30)
            if r.status_code == 200:
                print(f"  OK Telegram parte {i}/{len(parts)}")
            else:
                print(f"  ✗ Telegram {r.status_code}: {r.text[:200]}")
                success = False
        except Exception as e:
            print(f"  ✗ Telegram erro: {e}")
            success = False
        if len(parts) > 1:
            time.sleep(1)
    return success


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*55}")
    print(f"  PIPELINE CAMPOFORT - {DATE_BR}")
    print(f"{'='*55}\n")

    if BOLETIM_PATH.exists():
        print(f"Boletim {BOLETIM_PATH} ja existe. Encerrando.")
        return

    # 1. Dados
    print("[1/6] Coletando dados de mercado...")
    data = gather_market_data()
    print(f"  OK Dolar: {data['dollar']} | Selic: {data['selic']}")

    # 2. Conteudo
    print("\n[2/6] Gerando conteudo via Claude Haiku...")
    content  = generate_content(data)
    titulo   = f"Boletim CampoFort - {DATE_BR}"
    descricao = titulo

    BOLETIM_PATH.write_text(content["boletim_md"], encoding="utf-8")
    roteiro_full = (
        f"# Roteiro Podcast CampoFort - {DATE_BR}\n"
        f"**Voz:** pt-BR-ToniNeural (Azure) | fallback: pt-BR-AntonioNeural\n"
        f"**Duracao-alvo:** 4-5 minutos\n\n---\n\n"
        f"## ROTEIRO PARA NARRACAO\n\n"
        f"{content['roteiro_narracao']}\n\n---\n\n"
        f"## BLOCOS CRONOMETRADOS\n"
        f"1. Abertura 15s | 2. Boi 60s | 3. Milho 50s | 4. Soja 35s\n"
        f"5. Macro 40s | 6. Politica 55s | 7. Panorama 40s | 8. Projecoes+Encerramento 50s\n"
    )
    ROTEIRO_PATH.write_text(roteiro_full, encoding="utf-8")
    print(f"  OK {BOLETIM_PATH} | {ROTEIRO_PATH}")

    # 3. Audio
    print("\n[3/6] Gerando audio...")
    generate_audio(content["roteiro_narracao"], MP3_PATH)
    mp3_size = MP3_PATH.stat().st_size
    print(f"  OK {MP3_PATH} ({mp3_size // 1024} KB)")

    # 4. GitHub Releases
    print("\n[4/6] Subindo MP3 para GitHub Releases...")
    if not GITHUB_TOKEN:
        print("  ✗ GITHUB_TOKEN ausente.")
        audio_url = "[PENDENTE]"
        upload_ok = False
    else:
        audio_url = upload_mp3(MP3_PATH)
        print(f"  OK {audio_url}")
        upload_ok = True

    # 5. RSS
    print("\n[5/6] Atualizando RSS e episodios.json...")
    duracao_seg = max(240, int(mp3_size / 24000))
    update_rss(audio_url, titulo, descricao, duracao_seg, mp3_size)
    update_episodios_json(audio_url, titulo, descricao, duracao_seg)
    print(f"  OK {RSS_PATH} e {EPISODIOS_PATH}")

    # 6. Telegram
    print("\n[6/6] Enviando via Telegram...")
    spotify_link = SPOTIFY_URL if SPOTIFY_URL else (
        audio_url + " _(Spotify em configuracao)_")
    tg_message = (content["mensagem_telegram"]
                  .replace("[LINK_AUDIO]", audio_url)
                  .replace("[LINK_SPOTIFY]", spotify_link))
    TG_PATH.write_text(tg_message, encoding="utf-8")

    tg_sent = False
    if TELEGRAM_TOKEN and TELEGRAM_CHAT:
        tg_sent = send_telegram(tg_message)
    else:
        print("  ✗ Secrets Telegram ausentes. Mensagem em", TG_PATH)

    print(f"\n{'='*55}")
    print("  PIPELINE CONCLUIDO")
    print(f"  Boletim:  {BOLETIM_PATH}")
    print(f"  Audio:    {MP3_PATH}")
    print(f"  RSS:      {RSS_PATH}")
    print(f"  Telegram: {'OK Enviado' if tg_sent else 'Salvo em ' + str(TG_PATH)}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
