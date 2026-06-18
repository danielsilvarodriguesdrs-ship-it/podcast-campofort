#!/usr/bin/env python3
"""
CampoFort Boletim Semanal — Runner para GitHub Actions
Gera boletim, roteiro, áudio e envia via Telegram toda quarta-feira às 06h BRT
"""

import os
import datetime
import requests
import anthropic
from openai import OpenAI
from pathlib import Path

# ─── Configuração ──────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
ANTHROPIC_API_KEY  = os.environ["ANTHROPIC_API_KEY"]
OPENAI_API_KEY     = os.environ["OPENAI_API_KEY"]
GITHUB_TOKEN       = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO        = os.environ.get("GITHUB_REPO", "danielsilvarodriguesdrs-ship-it/podcast-campofort")

# Fuso horário BRT (UTC-3)
BRT = datetime.timezone(datetime.timedelta(hours=-3))
NOW = datetime.datetime.now(BRT)

DATE_SHORT = NOW.strftime("%d/%m/%Y")
DATE_FILE  = NOW.strftime("%Y%m%d")

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
]
DIAS_SEMANA = [
    "segunda-feira", "terça-feira", "quarta-feira",
    "quinta-feira", "sexta-feira", "sábado", "domingo"
]
DATE_LONG = f"{NOW.day} de {MESES[NOW.month - 1]} de {NOW.year}"
DIA_SEMANA = DIAS_SEMANA[NOW.weekday()]
MES_ANO = f"{MESES[NOW.month - 1]} de {NOW.year}"

# ─── Prompt de geração ─────────────────────────────────────────────────────────
PROMPT = f"""Gere o BOLETIM SEMANAL CAMPOFORT — {DATE_SHORT} ({DIA_SEMANA}).
Você representa Daniel Rodrigues, CampoFort Nutrição Estratégica / Cria Bem Nutrição Animal.

REGRAS:
- Português brasileiro. Sem SELIC. GO e MT lado a lado em cada commodity.
- TELEGRAM: valores em notação numérica — R$ 327,00/@, +1,2%, US$ 4,27/bu. NUNCA por extenso.
- ROTEIRO: valores POR EXTENSO — "trezentos e vinte e sete reais por arroba", "alta de um vírgula dois por cento".
- Dados mais recentes disponíveis (até 3 dias). NUNCA pergunte. SEMPRE gere o boletim completo.

PESQUISAS — faça as 5 antes de escrever:
1. boi gordo Goiás Mato Grosso cotação arroba semana atual {MES_ANO}
2. milho soja Goiás Mato Grosso IMEA CEPEA preço hoje {DATE_SHORT}
3. B3 boi gordo milho soja futuros fechamento {DATE_SHORT}
4. dólar cotação hoje exportação carne bovina Brasil China {MES_ANO}
5. site:revistaoeste.com política agronegócio {MES_ANO}

===TELEGRAM_INICIO===
📊 *BOLETIM CAMPOFORT* — {DATE_SHORT}
_{DIA_SEMANA.capitalize()} | Mercado Agropecuário_

Bom dia, produtor!

━━━━━━━━━━━━━━━━━━━━
🐂 *BOI GORDO*
▸ *GO* R$ X,XX/@ (à vista) · R$ X,XX/@ (prazo 30d)
▸ *MT* R$ X,XX/@ (Cuiabá)
▸ *B3* [mês] R$ X,XX/@ (X,X%)
💬 _[análise: oferta, demanda ou tendência — 1 linha]_

━━━━━━━━━━━━━━━━━━━━
🌽 *MILHO*
▸ *GO* R$ X,XX/sc · *MT* R$ X,XX/sc (X,X%)
▸ *B3* R$ X,XX/sc · *Chicago* US$ X,XX/bu (X,X%)
💬 _[análise: safrinha, demanda, risco — 1 linha]_

━━━━━━━━━━━━━━━━━━━━
🌱 *SOJA*
▸ *GO* R$ X,XX/sc · *MT* R$ X,XX/sc (X,X%)
▸ *Chicago* US$ X,XX/bu (X,X%) · *Paranaguá* R$ X,XX/sc
💬 _[análise: câmbio, exportação, perspectiva — 1 linha]_

━━━━━━━━━━━━━━━━━━━━
💵 *CÂMBIO*
▸ Dólar R$ X,XX · _[impacto no agro — 1 linha]_

━━━━━━━━━━━━━━━━━━━━
🏛️ *POLÍTICA* _(Revista Oeste)_
▸ _[fato político relevante da semana — 2 linhas]_

━━━━━━━━━━━━━━━━━━━━
🔎 *PANORAMA*
▸ [destaque 1 com número]
▸ [destaque 2 com número]
▸ [destaque 3 se relevante]

━━━━━━━━━━━━━━━━━━━━
_Daniel Rodrigues_
_CampoFort Nutrição Estratégica · Cria Bem Nutrição Animal_
_Nutrição estratégica. Resultado no campo._
===TELEGRAM_FIM===

===ROTEIRO_INICIO===
"Bom dia, produtor. Este é o Boletim Informativo CampoFort. Hoje é {DIA_SEMANA}, {DATE_LONG}. Vamos aos mercados."

[600 a 900 palavras. Ordem: BOI GORDO → MILHO → SOJA → CÂMBIO → POLÍTICA → PANORAMA.
Análise, contexto e orientação prática para o produtor. Todos os valores POR EXTENSO.]

"Este boletim foi elaborado por Daniel da CampoFort Nutrição Estratégica, representante técnico-comercial da Cria Bem Nutrição Animal. Nutrição estratégica. Resultado no campo. Até a próxima quarta-feira."
===ROTEIRO_FIM===
"""


# ─── Geração de conteúdo (Claude + web search) ─────────────────────────────────
def generate_content() -> tuple[str, str]:
    """Chama Claude API com web search. Retorna (telegram_msg, roteiro)."""
    print("🔍 Pesquisando cotações e gerando conteúdo via Claude API...")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    response = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=6000,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 15
        }],
        messages=[{"role": "user", "content": PROMPT}]
    )

    full_text = "".join(
        block.text for block in response.content
        if hasattr(block, "text")
    )

    # Extrair blocos
    def extract_block(text: str, start_tag: str, end_tag: str) -> str:
        if start_tag in text and end_tag in text:
            return text.split(start_tag)[1].split(end_tag)[0].strip()
        return text.strip()

    telegram_msg = extract_block(full_text, "===TELEGRAM_INICIO===", "===TELEGRAM_FIM===")
    roteiro      = extract_block(full_text, "===ROTEIRO_INICIO===",  "===ROTEIRO_FIM===")

    return telegram_msg, roteiro


# ─── Geração de áudio (OpenAI TTS) ───────────────────────────────────────────
def _split_text(text: str, max_chars: int = 3800) -> list[str]:
    """Divide o texto em blocos ≤ max_chars, quebrando em fim de frase.
    Garante que nenhum bloco exceda max_chars, mesmo sentenças muito longas."""
    chunks, current = [], ""
    for sentence in text.replace("\n", " \n ").split(". "):
        piece = sentence + ". "
        # Sentença individualmente maior que max_chars: divide por força bruta
        if len(piece) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            for i in range(0, len(piece), max_chars):
                sub = piece[i:i + max_chars].strip()
                if sub:
                    chunks.append(sub)
            continue
        candidate = current + piece
        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                chunks.append(current.strip())
            current = piece
    if current.strip():
        chunks.append(current.strip())
    return chunks or [text[:max_chars]]


def generate_audio(roteiro: str) -> bytes:
    """Gera MP3 via OpenAI TTS tts-1-hd, voz 'onyx'. Divide automaticamente se > 4000 chars."""
    print("🎙️ Gerando áudio com OpenAI TTS (voz onyx)...")

    client = OpenAI(api_key=OPENAI_API_KEY)
    chunks = _split_text(roteiro)
    print(f"  📄 Roteiro dividido em {len(chunks)} bloco(s) de áudio")

    audio_parts: list[bytes] = []
    for i, chunk in enumerate(chunks):
        print(f"  🔊 Gerando bloco {i + 1}/{len(chunks)} ({len(chunk)} chars)...")
        response = client.audio.speech.create(
            model="tts-1-hd",
            voice="onyx",
            input=chunk,
            response_format="mp3",
            speed=0.95
        )
        audio_parts.append(response.content)

    return b"".join(audio_parts)


# ─── Telegram ─────────────────────────────────────────────────────────────────
def telegram_send_text(text: str, spotify_url: str = None) -> None:
    """Envia mensagem de texto. Na última parte, adiciona botão inline do Spotify."""
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [text[j:j + 4000] for j in range(0, len(text), 4000)]

    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown"
        }
        # Botão inline apenas na última parte
        if spotify_url and i == len(chunks) - 1:
            payload["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": "🎙️ Ouça o Podcast no Spotify", "url": spotify_url}
                ]]
            }
        resp = requests.post(api_url, json=payload, timeout=30)
        resp.raise_for_status()
        print(f"  ✅ Texto enviado (parte {i + 1})")


def telegram_send_audio(audio_bytes: bytes, filename: str) -> None:
    """Envia arquivo de áudio via Telegram."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio"
    resp = requests.post(
        url,
        files={"audio": (filename, audio_bytes, "audio/mpeg")},
        data={
            "chat_id": TELEGRAM_CHAT_ID,
            "caption": f"🎙️ Podcast CampoFort — {DATE_SHORT}",
            "title": f"Boletim CampoFort {DATE_SHORT}",
            "performer": "Daniel Rodrigues — CampoFort Nutrição Estratégica"
        },
        timeout=180
    )
    resp.raise_for_status()
    print("  ✅ Áudio enviado")


# ─── Spotify RSS via GitHub Releases ─────────────────────────────────────────
def github_upload_release(audio_bytes: bytes, filename: str) -> str:
    """Cria GitHub Release e faz upload do MP3. Retorna URL pública de download."""
    import json as _json
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    tag = f"ep-{DATE_FILE}"

    # Verificar se release já existe (re-run protection)
    check = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{tag}",
        headers=headers, timeout=15
    )
    if check.status_code == 200:
        release_id = check.json()["id"]
        print(f"  ♻️  Release {tag} já existe — reutilizando")
    else:
        resp = requests.post(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases",
            headers=headers,
            json={
                "tag_name": tag,
                "name": f"🎙️ Boletim CampoFort — {DATE_SHORT}",
                "body": f"Episódio semanal do podcast CampoFort — {DATE_LONG}.",
                "draft": False,
                "prerelease": False
            },
            timeout=30
        )
        resp.raise_for_status()
        release_id = resp.json()["id"]
        print(f"  🏷️  Release {tag} criada (id {release_id})")

    # Upload do MP3
    upload_resp = requests.post(
        f"https://uploads.github.com/repos/{GITHUB_REPO}/releases/{release_id}/assets?name={filename}",
        headers={**headers, "Content-Type": "audio/mpeg"},
        data=audio_bytes,
        timeout=300
    )
    if upload_resp.status_code == 422:
        # Asset já existe — buscar URL existente
        assets = requests.get(
            f"https://api.github.com/repos/{GITHUB_REPO}/releases/{release_id}/assets",
            headers=headers, timeout=15
        ).json()
        for a in assets:
            if a["name"] == filename:
                url = a["browser_download_url"]
                print(f"  ♻️  Asset já existia: {url}")
                return url
    upload_resp.raise_for_status()
    url = upload_resp.json()["browser_download_url"]
    print(f"  ✅ MP3 publicado: {url}")
    return url


def update_rss_feed(audio_url: str, telegram_msg: str) -> None:
    """Atualiza episodes.json e regenera podcast_feed.xml para o Spotify."""
    import json as _json

    episodes_path = Path("episodes.json")
    episodes = _json.loads(episodes_path.read_text(encoding="utf-8")) if episodes_path.exists() else []

    # Descrição: primeira linha não-vazia do boletim
    desc_lines = [l.strip() for l in telegram_msg.split("\n") if l.strip() and not l.startswith("===")]
    descricao = " ".join(desc_lines[:3])[:300]

    episode = {
        "titulo": f"Boletim CampoFort — {DATE_SHORT}",
        "data": NOW.strftime("%Y-%m-%d"),
        "pubDate": NOW.strftime("%a, %d %b %Y 06:00:00 -0300"),
        "descricao": descricao,
        "audio_url": audio_url,
        "guid": audio_url
    }

    # Evitar duplicatas por data
    episodes = [e for e in episodes if e.get("data") != episode["data"]]
    episodes.insert(0, episode)
    episodes = episodes[:52]  # Manter 1 ano de episódios

    episodes_path.write_text(_json.dumps(episodes, ensure_ascii=False, indent=2), encoding="utf-8")

    # Gerar itens RSS
    items_xml = ""
    for ep in episodes:
        items_xml += f"""
    <item>
      <title><![CDATA[{ep['titulo']}]]></title>
      <description><![CDATA[{ep['descricao']}]]></description>
      <pubDate>{ep['pubDate']}</pubDate>
      <enclosure url="{ep['audio_url']}" type="audio/mpeg"/>
      <guid isPermaLink="false">{ep['guid']}</guid>
      <itunes:duration>300</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>"""

    pages_base = f"https://danielsilvarodriguesdrs-ship-it.github.io/podcast-campofort"
    rss_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"
  xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd"
  xmlns:content="http://purl.org/rss/1.0/modules/content/">
  <channel>
    <title>CampoFort — Boletim Agropecuário</title>
    <link>{pages_base}</link>
    <description>Boletim semanal com cotações de boi gordo, milho e soja para produtores de Goiás e Mato Grosso. Por Daniel Rodrigues — CampoFort Nutrição Estratégica.</description>
    <language>pt-BR</language>
    <copyright>CampoFort Nutrição Estratégica</copyright>
    <managingEditor>danielsilva.rodrigues.drs@gmail.com (Daniel Rodrigues)</managingEditor>
    <itunes:author>Daniel Rodrigues — CampoFort Nutrição Estratégica</itunes:author>
    <itunes:summary>Boletim semanal com cotações e análises de boi gordo, milho e soja para GO e MT.</itunes:summary>
    <itunes:category text="Business">
      <itunes:category text="Investing"/>
    </itunes:category>
    <itunes:explicit>false</itunes:explicit>
    <itunes:image href="{pages_base}/cover.jpg"/>
    <image>
      <url>{pages_base}/cover.jpg</url>
      <title>CampoFort — Boletim Agropecuário</title>
      <link>{pages_base}</link>
    </image>
    {items_xml}
  </channel>
</rss>"""

    Path("podcast_feed.xml").write_text(rss_xml, encoding="utf-8")
    print(f"  ✅ RSS feed atualizado: {len(episodes)} episódio(s) → podcast_feed.xml")
    print(f"  🎵 URL do feed: {pages_base}/podcast_feed.xml")


# ─── Salvar arquivos locais ────────────────────────────────────────────────────
def save_files(telegram_msg: str, roteiro: str, audio_bytes: bytes) -> None:
    out = Path("output")
    out.mkdir(exist_ok=True)
    (out / f"boletim_{DATE_FILE}.txt").write_text(telegram_msg, encoding="utf-8")
    (out / f"roteiro_{DATE_FILE}.md").write_text(roteiro, encoding="utf-8")
    (out / f"podcast_campofort_{DATE_FILE}.mp3").write_bytes(audio_bytes)
    print(f"💾 Arquivos salvos em output/")


# ─── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    print(f"\n🌾 CampoFort Boletim Runner — {DATE_SHORT} ({DIA_SEMANA})\n{'─' * 50}")

    telegram_msg, roteiro = generate_content()
    audio_bytes = generate_audio(roteiro)
    filename = f"podcast_campofort_{DATE_FILE}.mp3"
    save_files(telegram_msg, roteiro, audio_bytes)

    # Spotify RSS — hospedar MP3 no GitHub Releases e atualizar feed
    audio_url = None
    if GITHUB_TOKEN:
        print("\n🎵 Publicando no Spotify RSS via GitHub Releases...")
        try:
            audio_url = github_upload_release(audio_bytes, filename)
            update_rss_feed(audio_url, telegram_msg)
        except Exception as e:
            print(f"  ⚠️  RSS/Release falhou (não crítico): {e}")
    else:
        print("  ⚠️  GITHUB_TOKEN ausente — Spotify RSS ignorado")

    SPOTIFY_SHOW_URL = "https://open.spotify.com/show/033s9dJplOa8SpCMY7EXnd"

    print("\n📱 Enviando via Telegram...")
    telegram_send_text(telegram_msg, spotify_url=SPOTIFY_SHOW_URL)
    telegram_send_audio(audio_bytes, filename)

    print(f"\n🏁 Boletim entregue com sucesso — {DATE_SHORT}")
    if audio_url:
        print(f"🎵 MP3 público: {audio_url}")


if __name__ == "__main__":
    main()
