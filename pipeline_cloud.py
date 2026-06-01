#!/usr/bin/env python3
"""
Pipeline Cloud CampoFort
Roda em GitHub Actions — sem dependência de PC local.

Fluxo:
  1. Coleta dados (AwesomeAPI, BCB, scraping de sites agro)
  2. Gera boletim, roteiro e mensagem Telegram via Claude Haiku
  3. Gera MP3 via Edge TTS (pt-BR-AntonioNeural)
  4. Sobe MP3 para GitHub Releases
  5. Atualiza podcast_feed.xml (RSS) e episodios.json
  6. Envia mensagem via Telegram Bot API (gratuito, sem limite)

Segredos necessários no GitHub Repository Settings → Secrets:
  - ANTHROPIC_API_KEY
  - TELEGRAM_BOT_TOKEN   (obtido via @BotFather no Telegram)
  - TELEGRAM_CHAT_ID     (seu ID pessoal — veja SETUP_CLOUD.md)
  - GITHUB_TOKEN         (automático nas Actions)
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

# ── Configurações ────────────────────────────────────────────────────────────
GITHUB_REPO    = os.environ.get("GITHUB_REPO", "danielsilvarodriguesdrs-ship-it/podcast-campofort")
RELEASE_TAG    = "audio"
VOICE          = "pt-BR-AntonioNeural"

ANTHROPIC_KEY  = os.environ.get("ANTHROPIC_API_KEY", "")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")
GITHUB_TOKEN   = os.environ.get("GITHUB_TOKEN", "")

BRT            = timezone(timedelta(hours=-3))
NOW            = datetime.now(BRT)
DATE_BR        = NOW.strftime("%d/%m/%Y")
DATE_FILE      = NOW.strftime("%Y%m%d")
DATE_ISO       = NOW.strftime("%Y-%m-%d")
WEEKDAY_PT     = ["Segunda-feira","Terça-feira","Quarta-feira","Quinta-feira",
                   "Sexta-feira","Sábado","Domingo"][NOW.weekday()]

BOLETIM_PATH   = Path(f"boletim_semanal_campofort_{DATE_FILE}.md")
ROTEIRO_PATH   = Path(f"roteiro_podcast_campofort_{DATE_FILE}.md")
MP3_PATH       = Path(f"podcast_campofort_{DATE_FILE}.mp3")
TG_PATH        = Path(f"mensagem_telegram_{DATE_FILE}.txt")
RSS_PATH       = Path("podcast_feed.xml")
EPISODIOS_PATH = Path("episodios.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# ── 1. Coleta de Dados ───────────────────────────────────────────────────────

def get_dollar() -> str:
    """Cotação USD/BRL via AwesomeAPI (sem chave, grátis)."""
    try:
        r = requests.get("https://economia.awesomeapi.com.br/json/last/USD-BRL",
                         timeout=10)
        d = r.json()["USDBRL"]
        bid = float(d["bid"])
        pct = float(d["pctChange"])
        return f"R$ {bid:.2f} ({pct:+.2f}% no dia)"
    except Exception as e:
        return f"indisponível ({e})"


def get_selic() -> str:
    """Taxa Selic via API pública do BCB."""
    try:
        r = requests.get(
            "https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json",
            timeout=10)
        val = float(r.json()[0]["valor"])
        return f"{val:.2f}% a.a."
    except Exception as e:
        return f"indisponível ({e})"


def fetch_page_text(url: str, max_chars: int = 3000) -> str:
    """Baixa uma página e retorna o texto limpo (sem JS — páginas estáticas)."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")
        for tag in soup(["script", "style", "nav", "header", "footer",
                          "aside", "form", "button"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        # Compacta linhas em branco
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:max_chars]
    except Exception as e:
        return f"[erro ao buscar {url}: {e}]"


def gather_market_data() -> dict:
    """Coleta dados de mercado de fontes públicas."""
    print("  → Dólar e Selic...")
    dollar = get_dollar()
    selic  = get_selic()

    sources = {
        "boi_go_mt": [
            "https://www.noticiasagricolas.com.br/cotacoes/boi-gordo",
            "https://www.canalrural.com.br/cotacoes/boi/",
        ],
        "milho": [
            "https://www.noticiasagricolas.com.br/cotacoes/milho",
        ],
        "soja": [
            "https://www.noticiasagricolas.com.br/cotacoes/soja",
        ],
        "politica_revistaoeste": [
            "https://revistaoeste.com/agronegocio/",
            "https://revistaoeste.com/politica/",
        ],
        "regulatorio": [
            "https://www.noticiasagricolas.com.br/noticias/boi",
            "https://www.canalrural.com.br/pecuaria/",
        ],
    }

    raw = {"dollar": dollar, "selic": selic}
    for key, urls in sources.items():
        texts = []
        for url in urls:
            print(f"  → {url}")
            texts.append(fetch_page_text(url))
            time.sleep(1)
        raw[key] = "\n---\n".join(texts)

    return raw


# ── 2. Geração de Conteúdo via Claude ───────────────────────────────────────

SYSTEM_PROMPT = """Você é Daniel Rodrigues, CEO da CampoFort, especialista em nutrição e
planejamento de gado de corte. Escreve o Boletim Semanal CampoFort toda quarta-feira.

REGRAS INVIOLÁVEIS:
- Cotações de boi gordo, milho e soja SEMPRE para Goiás E Mato Grosso lado a lado
- Política da semana: cite SOMENTE fontes da Revista Oeste (revistaoeste.com)
- Roteiro TTS: escreva números e símbolos por extenso (sem R$, %, /, @)
- Tom: autoridade técnica, firme, direto, sem floreios
- Boletim: use emojis de seção (🐂 🌽 🌱 💵 🏛️ 📈 🔎)
- Telegram: 2500-3500 caracteres, bold com *asteriscos*, itálico com _underline_"""


def generate_content(data: dict) -> dict:
    """Usa Claude Haiku para gerar boletim, roteiro e mensagem WhatsApp."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)

    user_msg = f"""Data de hoje: {WEEKDAY_PT}, {DATE_BR}

DADOS COLETADOS:
Dólar: {data['dollar']}
Selic: {data['selic']}

BOI GORDO (GO e MT):
{data['boi_go_mt'][:2500]}

MILHO:
{data['milho'][:1500]}

SOJA:
{data['soja'][:1500]}

POLÍTICA (Revista Oeste):
{data['politica_revistaoeste'][:2000]}

REGULATÓRIO / COMERCIAL:
{data['regulatorio'][:1500]}

---
Gere os três conteúdos no formato JSON exato abaixo. Não adicione texto fora do JSON.

{{
  "boletim_md": "<markdown completo do boletim semanal>",
  "roteiro_narracao": "<texto corrido 4-5 min TTS, sem $/%/@ — APENAS o texto narrável, sem títulos de seção>",
  "mensagem_telegram": "<mensagem Telegram 2500-3500 chars com emojis, *bold* e _itálico_, cobrindo todas as seções do boletim de forma completa e detalhada — BOI GO/MT, MILHO GO/MT, SOJA GO/MT, MACRO, POLÍTICA (Revista Oeste), PANORAMA e PROJEÇÕES; inclua [LINK_AUDIO] no final antes da assinatura>"
}}

Para o boletim_md, siga exatamente esta estrutura de seções:
📋 Cabeçalho (data, nome, cargo)
🐂 BOI GORDO — GOIÁS / MATO GROSSO (preços, diferencial, análise)
🌽 MILHO — GOIÁS / MATO GROSSO (preços, análise)
🌱 SOJA — GOIÁS / MATO GROSSO (preços, análise)
💵 DÓLAR & SELIC (valores, impacto)
🏛️ POLÍTICA DA SEMANA — Revista Oeste (destaque com URL)
📈 PANORAMA REGULATÓRIO/COMERCIAL
🔎 PROJEÇÕES — PRÓXIMA SEMANA
Assinatura com placeholder [LINK DO PODCAST]

Para o roteiro_narracao, inicie com "Bom dia, produtor." e termine com "Nutrição estratégica. Resultado no campo. Até a próxima."
Estrutura: abertura → boi → milho → soja → macro → política → panorama → projeções → encerramento."""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=6000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}]
    )

    raw = response.content[0].text.strip()

    # Extrai JSON mesmo se vier com markdown code fences
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if not json_match:
        raise ValueError(f"Claude não retornou JSON válido:\n{raw[:500]}")

    result = json.loads(json_match.group())
    # Suporte retrocompatível: se Claude devolveu chave antiga, renomeia
    if "mensagem_whatsapp" in result and "mensagem_telegram" not in result:
        result["mensagem_telegram"] = result.pop("mensagem_whatsapp")
    return result


# ── 3. Geração de Áudio via Edge TTS ────────────────────────────────────────

async def _generate_audio_async(text: str, path: Path) -> None:
    communicate = edge_tts.Communicate(text, voice=VOICE)
    await communicate.save(str(path))


def generate_audio(roteiro_text: str, path: Path) -> None:
    """Gera MP3 a partir do roteiro de narração."""
    # Limpa marcadores que não devem ser lidos
    text = re.sub(r"#{1,6}\s", "", roteiro_text)
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}", r"\1", text)  # remove markdown bold/italic
    text = re.sub(r"`[^`]+`", "", text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", text)  # links → texto
    text = text.strip()
    asyncio.run(_generate_audio_async(text, path))


# ── 4. GitHub Releases — Upload do MP3 ──────────────────────────────────────

def get_or_create_release(gh_headers: dict) -> dict:
    """Retorna a release pelo tag, criando se não existir."""
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{RELEASE_TAG}"
    r = requests.get(url, headers=gh_headers)
    if r.status_code == 200:
        return r.json()

    # Cria a release
    r = requests.post(
        f"https://api.github.com/repos/{GITHUB_REPO}/releases",
        headers=gh_headers,
        json={
            "tag_name": RELEASE_TAG,
            "name": "Episódios CampoFort",
            "body": "Episódios do Boletim CampoFort",
            "draft": False,
            "prerelease": False,
        }
    )
    r.raise_for_status()
    return r.json()


def upload_mp3(mp3_path: Path) -> str:
    """Sobe MP3 para GitHub Releases e retorna URL pública."""
    gh_headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    release = get_or_create_release(gh_headers)

    # Remove asset com mesmo nome se já existir
    for asset in release.get("assets", []):
        if asset["name"] == mp3_path.name:
            requests.delete(
                f"https://api.github.com/repos/{GITHUB_REPO}/releases/assets/{asset['id']}",
                headers=gh_headers
            )
            time.sleep(1)

    # Upload
    upload_url = release["upload_url"].split("{")[0]
    with open(mp3_path, "rb") as f:
        r = requests.post(
            f"{upload_url}?name={mp3_path.name}",
            headers={**gh_headers, "Content-Type": "audio/mpeg"},
            data=f,
        )
    r.raise_for_status()
    return r.json()["browser_download_url"]


# ── 5. RSS Feed (Spotify) ────────────────────────────────────────────────────

def build_rss_url() -> str:
    owner = GITHUB_REPO.split("/")[0]
    repo  = GITHUB_REPO.split("/")[1]
    return f"https://{owner}.github.io/{repo}/podcast_feed.xml"


def update_rss(audio_url: str, titulo: str, descricao: str,
               duracao_seg: int, mp3_size: int) -> None:
    """Adiciona novo episódio ao podcast_feed.xml existente (ou cria do zero)."""

    # Namespace iTunes
    ET.register_namespace("itunes",  "http://www.itunes.com/dtds/podcast-1.0.dtd")
    ET.register_namespace("content", "http://purl.org/rss/1.0/modules/content/")

    itunes_ns = "http://www.itunes.com/dtds/podcast-1.0.dtd"

    if RSS_PATH.exists():
        tree = ET.parse(RSS_PATH)
        root = tree.getroot()
        channel = root.find("channel")
    else:
        root   = ET.Element("rss", version="2.0", attrib={
            "xmlns:itunes":  itunes_ns,
            "xmlns:content": "http://purl.org/rss/1.0/modules/content/"
        })
        channel = ET.SubElement(root, "channel")

        # Metadados do canal (só na primeira vez)
        _sub(channel, "title",          "Boletim CampoFort")
        _sub(channel, "link",           "https://campofort.com.br")
        _sub(channel, "description",    "Boletim semanal de mercado agropecuário — Goiás e Mato Grosso. Apresentação: Daniel Rodrigues, CEO CampoFort.")
        _sub(channel, "language",       "pt-BR")
        ET.SubElement(channel, f"{{{itunes_ns}}}author").text  = "Daniel Rodrigues — CampoFort"
        ET.SubElement(channel, f"{{{itunes_ns}}}explicit").text = "false"
        cat = ET.SubElement(channel, f"{{{itunes_ns}}}category", text="Business")
        ET.SubElement(cat, f"{{{itunes_ns}}}category", text="Agriculture")

    # Novo item
    pub_date = formatdate(NOW.timestamp())
    guid     = f"campofort-{DATE_FILE}"

    item = ET.Element("item")
    _sub(item, "title",       titulo)
    _sub(item, "description", descricao)
    _sub(item, "pubDate",     pub_date)
    _sub(item, "guid",        guid, isPermaLink="false")
    ET.SubElement(item, "enclosure",
                  url=audio_url,
                  length=str(mp3_size),
                  type="audio/mpeg")
    ET.SubElement(item, f"{{{itunes_ns}}}duration").text = str(duracao_seg)
    ET.SubElement(item, f"{{{itunes_ns}}}summary").text  = descricao

    # Insere no topo (episódio mais recente primeiro)
    channel.insert(list(channel).index(channel.find("item")) if channel.find("item") is not None else len(list(channel)), item)

    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(RSS_PATH, encoding="utf-8", xml_declaration=True)


def _sub(parent, tag, text=None, **attrib):
    el = ET.SubElement(parent, tag, **attrib)
    if text:
        el.text = text
    return el


def update_episodios_json(audio_url: str, titulo: str, descricao: str,
                          duracao_seg: int) -> None:
    """Adiciona/atualiza episódio em episodios.json."""
    data = {}
    if EPISODIOS_PATH.exists():
        data = json.loads(EPISODIOS_PATH.read_text(encoding="utf-8"))

    episodios = data.get("episodios", [])

    # Remove entrada com a mesma data se já existir
    episodios = [e for e in episodios if e.get("data") != DATE_ISO]

    # Insere no topo
    episodios.insert(0, {
        "data":        DATE_ISO,
        "titulo":      titulo,
        "descricao":   descricao,
        "duracao_seg": duracao_seg,
        "audio_url":   audio_url,
        "mp3_local":   MP3_PATH.name,
    })

    data["episodios"] = episodios
    EPISODIOS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=4),
        encoding="utf-8"
    )


# ── 6. Telegram Bot API ──────────────────────────────────────────────────────

def send_telegram(message: str) -> bool:
    """Envia mensagem de texto via Telegram Bot API.

    Suporta Markdown: *negrito*, _itálico_, `código`, [texto](url).
    Limite: 4096 caracteres por mensagem.
    Mensagens > 4096 chars são divididas automaticamente por linha.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        print("  ✗ TELEGRAM_BOT_TOKEN ou TELEGRAM_CHAT_ID não configurados.")
        return False

    # Divide em partes de até 4096 chars, quebrando em linhas inteiras
    parts = []
    current = ""
    for line in message.splitlines(keepends=True):
        if len(current) + len(line) > 4096:
            if current:
                parts.append(current.rstrip())
            current = line
        else:
            current += line
    if current.strip():
        parts.append(current.rstrip())

    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    success = True
    for i, part in enumerate(parts, 1):
        payload = {
            "chat_id":                  TELEGRAM_CHAT,
            "text":                     part,
            "parse_mode":               "Markdown",
            "disable_web_page_preview": True,
        }
        try:
            r = requests.post(api_url, json=payload, timeout=30)
            if r.status_code == 200:
                print(f"  ✓ Telegram parte {i}/{len(parts)} enviada.")
            else:
                print(f"  ✗ Telegram parte {i} retornou {r.status_code}: {r.text[:300]}")
                success = False
        except Exception as e:
            print(f"  ✗ Erro ao enviar Telegram parte {i}: {e}")
            success = False
    return success


def send_telegram_audio(mp3_path: Path, caption: str = "") -> bool:
    """Envia o MP3 diretamente como mensagem de áudio no Telegram.

    O Telegram reproduz inline (player de voz), sem precisar de link externo.
    Limite de upload: 50 MB via Bot API.
    """
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT:
        return False

    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendAudio"
    try:
        with open(mp3_path, "rb") as f:
            r = requests.post(
                api_url,
                data={
                    "chat_id":    TELEGRAM_CHAT,
                    "caption":    caption[:1024],
                    "parse_mode": "Markdown",
                    "title":      f"Boletim CampoFort — {DATE_BR}",
                    "performer":  "Daniel Rodrigues — CampoFort",
                },
                files={"audio": (mp3_path.name, f, "audio/mpeg")},
                timeout=120,
            )
        if r.status_code == 200:
            print("  ✓ Áudio enviado diretamente ao Telegram.")
            return True
        else:
            print(f"  ✗ Telegram sendAudio retornou {r.status_code}: {r.text[:300]}")
            return False
    except Exception as e:
        print(f"  ✗ Erro ao enviar áudio ao Telegram: {e}")
        return False


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"\n{'='*55}")
    print(f"  PIPELINE CAMPOFORT — {DATE_BR}")
    print(f"{'='*55}\n")

    # ── Verificar duplicata ──────────────────────────────
    if BOLETIM_PATH.exists():
        print(f"Boletim {BOLETIM_PATH} já existe. Encerrando.\n")
        return

    # ── 1. Coletar dados ────────────────────────────────
    print("[1/6] Coletando dados de mercado...")
    data = gather_market_data()
    print(f"  ✓ Dólar: {data['dollar']}  |  Selic: {data['selic']}")

    # ── 2. Gerar conteúdo ───────────────────────────────
    print("\n[2/6] Gerando conteúdo via Claude Haiku...")
    content = generate_content(data)

    titulo   = f"Boletim CampoFort — {DATE_BR}"
    descricao = (content["boletim_md"][:300]
                 .split("\n")[3] if len(content["boletim_md"]) > 50
                 else titulo)

    # Salva arquivos de texto
    BOLETIM_PATH.write_text(content["boletim_md"],       encoding="utf-8")
    roteiro_full = (
        f"# Roteiro Podcast CampoFort — {DATE_BR}\n"
        f"**Voz:** masculina firme, ritmo cadenciado, autoridade técnica\n"
        f"**Duração-alvo:** 4 a 5 minutos\n"
        f"**Voz TTS recomendada:** pt-BR-AntonioNeural (Edge TTS)\n\n"
        f"---\n\n"
        f"## ROTEIRO PARA NARRAÇÃO (texto corrido — sem cifrão, percentual ou barra)\n\n"
        f"{content['roteiro_narracao']}\n\n"
        f"---\n\n"
        f"## BLOCOS CRONOMETRADOS (referência)\n"
        f"1. Abertura — 15s\n"
        f"2. Boi gordo GO/MT — 60s\n"
        f"3. Milho GO/MT — 50s\n"
        f"4. Soja GO/MT — 35s\n"
        f"5. Macro — 35s\n"
        f"6. Política Revista Oeste — 55s\n"
        f"7. Panorama regulatório — 40s\n"
        f"8. Projeções e encerramento — 50s\n"
    )
    ROTEIRO_PATH.write_text(roteiro_full, encoding="utf-8")
    print(f"  ✓ Boletim: {BOLETIM_PATH}")
    print(f"  ✓ Roteiro: {ROTEIRO_PATH}")

    # ── 3. Gerar áudio ──────────────────────────────────
    print("\n[3/6] Gerando áudio via Edge TTS...")
    generate_audio(content["roteiro_narracao"], MP3_PATH)
    mp3_size = MP3_PATH.stat().st_size
    print(f"  ✓ {MP3_PATH} ({mp3_size // 1024} KB)")

    # ── 4. Upload para GitHub Releases ──────────────────
    print("\n[4/6] Subindo MP3 para GitHub Releases...")
    if not GITHUB_TOKEN:
        print("  ✗ GITHUB_TOKEN não encontrado. Pulando upload.")
        audio_url = "[LINK_DO_PODCAST_PENDENTE]"
        wpp_ok = False
    else:
        audio_url = upload_mp3(MP3_PATH)
        print(f"  ✓ URL do áudio: {audio_url}")
        wpp_ok = True

    # ── 5. Atualizar RSS e episodios.json ───────────────
    print("\n[5/6] Atualizando RSS feed e episodios.json...")
    duracao_seg = max(240, int(mp3_size / 24000))  # estimativa por tamanho do MP3
    update_rss(audio_url, titulo, descricao, duracao_seg, mp3_size)
    update_episodios_json(audio_url, titulo, descricao, duracao_seg)
    print(f"  ✓ {RSS_PATH} e {EPISODIOS_PATH} atualizados")

    # ── 6. Enviar Telegram ──────────────────────────────
    print("\n[6/6] Enviando boletim e áudio via Telegram...")

    tg_message = content["mensagem_telegram"].replace("[LINK_AUDIO]", audio_url)

    # Salva sempre (auditoria / fallback)
    TG_PATH.write_text(tg_message, encoding="utf-8")

    tg_sent = False
    tg_audio_sent = False
    if TELEGRAM_TOKEN and TELEGRAM_CHAT:
        tg_sent = send_telegram(tg_message)
        if MP3_PATH.exists():
            audio_caption = f"🎙️ *Podcast CampoFort — {DATE_BR}*\n_Narrado por Daniel Rodrigues_"
            tg_audio_sent = send_telegram_audio(MP3_PATH, caption=audio_caption)
    else:
        print("  ✗ Secrets do Telegram não configurados. Mensagem salva em", TG_PATH)

    # ── Resumo final ─────────────────────────────────────
    print(f"\n{'='*55}")
    print("  PIPELINE CONCLUÍDO")
    print(f"  Boletim:  {BOLETIM_PATH}")
    print(f"  Roteiro:  {ROTEIRO_PATH}")
    print(f"  Áudio:    {MP3_PATH}")
    print(f"  RSS:      {RSS_PATH}")
    print(f"  Telegram texto: {'✓ Enviado' if tg_sent else '✗ Salvo em ' + str(TG_PATH)}")
    print(f"  Telegram áudio: {'✓ Enviado' if tg_audio_sent else '✗ Não enviado'}")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    main()
