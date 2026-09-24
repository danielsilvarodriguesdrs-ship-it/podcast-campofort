#!/usr/bin/env python3
"""
CampoFort Boletim Semanal — Runner para GitHub Actions
Gera boletim, roteiro, áudio e envia via Telegram toda quarta-feira às 05h30 BRT
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
OPENAI_API_KEY     = os.environ.get("OPENAI_API_KEY", "")
ELEVENLABS_API_KEY  = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_VOICE_ID = os.environ.get("ELEVENLABS_VOICE_ID") or "8xS29NBUUe3CYDmYeWfq"
GITHUB_TOKEN       = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPO        = os.environ.get("GITHUB_REPO", "danielsilvarodriguesdrs-ship-it/podcast-campofort")
SUPABASE_URL       = os.environ.get("SUPABASE_URL", "https://pcxbsbeywhytmjgouoej.supabase.co")
SUPABASE_ANON_KEY  = os.environ.get("SUPABASE_ANON_KEY", "")
# A tabela boletins só aceita escrita com a chave secreta (RLS bloqueia a anon/publishable)
SUPABASE_KEY       = os.environ.get("SUPABASE_SERVICE_KEY") or SUPABASE_ANON_KEY
# generate = terça (gera tudo, salva pending, não envia Telegram)
# publish  = quarta (lê pending, envia Telegram com link Spotify)
# full     = manual (gera + envia imediatamente)
MODE = os.environ.get("MODE", "full")

# Fuso horário BRT (UTC-3)
BRT = datetime.timezone(datetime.timedelta(hours=-3))
NOW = datetime.datetime.now(BRT)

# Data de PUBLICAÇÃO/ENVIO. No modo generate (roda na TERÇA), o conteúdo só é
# enviado na QUARTA-FEIRA seguinte — então todas as datas (mensagem, áudio,
# arquivos, RSS, episodes.json) usam o DIA SEGUINTE. Nos modos publish/full a
# data é a do próprio dia.
PUB = NOW + datetime.timedelta(days=1) if MODE == "generate" else NOW

DATE_SHORT = PUB.strftime("%d/%m/%Y")
DATE_FILE  = PUB.strftime("%Y%m%d")

MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"
]
DIAS_SEMANA = [
    "segunda-feira", "terça-feira", "quarta-feira",
    "quinta-feira", "sexta-feira", "sábado", "domingo"
]
DATE_LONG = f"{PUB.day} de {MESES[PUB.month - 1]} de {PUB.year}"
DIA_SEMANA = DIAS_SEMANA[PUB.weekday()]
MES_ANO = f"{MESES[PUB.month - 1]} de {PUB.year}"

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

ESTILO DO ROTEIRO (vai ser falado pela voz clonada do Daniel — tem que soar como ele
conversando com um produtor, não como locutor lendo matéria):
- Frases CURTAS e diretas, linguagem falada: "a gente", "tá", "olha", "presta atenção nisso".
- Varie o tamanho das frases; nada de todas com o mesmo ritmo ou o mesmo final.
- Use reticências (...) para pausas curtas entre ideias e quebra de parágrafo na troca de assunto.
- Coloque números, resultados e recomendações no fim da frase, onde a ênfase cai naturalmente.
- Tom técnico, seguro e próximo, de quem tem experiência de campo. Sem cara de publicidade,
  telemarketing ou rádio; sem drama; sem formalismo ("vale ressaltar", "cumpre destacar").
- NÃO escreva sotaque, gírias regionais forçadas nem palavras "caipirizadas".
  Exemplo BOM: "Produtor... presta atenção nisso. Porque quando a gente fala em ganho de peso... não é só colocar suplemento no cocho."
  Exemplo RUIM: "Produtor, preste atenção nesta informação, pois quando falamos em ganho de peso dos animais, não devemos considerar apenas o fornecimento de suplemento no cocho."

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


# ─── Preparação do texto para a voz ──────────────────────────────────────────
# Siglas que a voz soletra ou pronuncia errado → forma falada
SIGLAS_FALADAS = {
    "B3": "bê três", "IMEA": "Imea", "CEPEA": "Cepea", "ESALQ": "Esalq", "Esalq": "Esalq",
    "CONAB": "Conab", "USDA": "Departamento de Agricultura americano", "EUA": "Estados Unidos",
    "GO": "Goiás", "MT": "Mato Grosso", "MS": "Mato Grosso do Sul", "MG": "Minas Gerais",
    "SP": "São Paulo", "PIB": "pib", "IPCA": "inflação", "CBOT": "Chicago", "FOB": "fob",
}


def _num_extenso(n: str) -> str:
    from num2words import num2words
    return num2words(int(n), lang="pt_BR")


def preparar_texto_fala(texto: str) -> str:
    """Deixa o roteiro 'falável': sem títulos/markdown, siglas por extenso e números
    escritos, para a voz não travar nem soletrar."""
    import re
    linhas = []
    for linha in texto.splitlines():
        l = linha.strip()
        # Títulos (**TÍTULO**, # Título, linha toda em maiúsculas) viram só uma pausa
        if re.fullmatch(r"(\*\*|#+\s*).*", l) or (len(l) > 3 and l.upper() == l and re.search(r"[A-ZÇÃÉ]", l)):
            linhas.append("")
            continue
        linhas.append(l.strip('"“”'))
    t = "\n".join(linhas)
    t = re.sub(r"[*_#`]", "", t)
    for sigla, fala in SIGLAS_FALADAS.items():
        t = re.sub(rf"\b{re.escape(sigla)}\b", fala, t)
    # Safra 2026/27 → "vinte e seis, vinte e sete"
    t = re.sub(r"\b(\d{2})(\d{2})/(\d{2})\b", lambda m: f"{_num_extenso(m[2])}, {_num_extenso(m[3])}", t)
    # Decimais 13,3 → "treze vírgula três"; percentuais
    t = re.sub(r"\b(\d+),(\d+)\b", lambda m: f"{_num_extenso(m[1])} vírgula {_num_extenso(m[2])}", t)
    t = t.replace("%", " por cento")
    t = re.sub(r"\b\d+\b", lambda m: _num_extenso(m[0]), t)
    # Palavras soltas em MAIÚSCULAS → normal (senão a voz grita ou soletra)
    t = re.sub(r"\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{3,}\b", lambda m: m[0].capitalize(), t)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def generate_audio(roteiro: str) -> bytes:
    """Gera MP3 com a voz clonada do Daniel (ElevenLabs). Fallback: OpenAI onyx."""
    roteiro = preparar_texto_fala(roteiro)
    if ELEVENLABS_API_KEY:
        try:
            return generate_audio_elevenlabs(roteiro)
        except Exception as e:
            print(f"  ⚠️  ElevenLabs falhou ({e}) — usando fallback OpenAI onyx")
    else:
        print("  ⚠️  ELEVENLABS_API_KEY ausente — usando fallback OpenAI onyx")
    return generate_audio_openai(roteiro)


# Configuração da voz clonada (escolhida por amostras — ver modo "amostras")
VOZ_CONFIG = {
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {"stability": 0.6, "similarity_boost": 0.9, "style": 0.0,
                       "use_speaker_boost": True, "speed": 1.0},
}


def _elevenlabs_tts(text: str, config: dict, previous_text: str = "", next_text: str = "") -> bytes:
    payload = {"text": text, **config}
    # eleven_v3 não aceita encadeamento de contexto entre blocos
    if config["model_id"] != "eleven_v3":
        if previous_text:
            payload["previous_text"] = previous_text
        if next_text:
            payload["next_text"] = next_text
    resp = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}?output_format=mp3_44100_128",
        headers={"xi-api-key": ELEVENLABS_API_KEY, "Content-Type": "application/json"},
        json=payload, timeout=180,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
    return resp.content


def generate_audio_elevenlabs(roteiro: str, config: dict | None = None) -> bytes:
    """Gera MP3 via ElevenLabs (voz clonada). Blocos ≤ 2500 chars com contexto
    anterior/seguinte para manter a entonação contínua entre os blocos."""
    config = config or VOZ_CONFIG
    print(f"🎙️ Gerando áudio com ElevenLabs (voz clonada, {config['model_id']})...")

    chunks = _split_text(roteiro, max_chars=2500)
    print(f"  📄 Roteiro dividido em {len(chunks)} bloco(s) de áudio")

    audio_parts: list[bytes] = []
    for i, chunk in enumerate(chunks):
        print(f"  🔊 Gerando bloco {i + 1}/{len(chunks)} ({len(chunk)} chars)...")
        audio_parts.append(_elevenlabs_tts(
            chunk, config,
            previous_text=chunks[i - 1][-500:] if i > 0 else "",
            next_text=chunks[i + 1][:500] if i < len(chunks) - 1 else "",
        ))

    return b"".join(audio_parts)


def generate_audio_openai(roteiro: str) -> bytes:
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
    """Envia mensagem de texto. Na última parte, adiciona botão inline do Spotify.
    Se o Markdown vier malformado (entidade cortada por LLM ou pelo corte em pedaços),
    o Telegram responde 400 — nesse caso reenvia a mesma parte sem parse_mode, como texto puro,
    pra garantir que a mensagem chegue de qualquer forma."""
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
        if resp.status_code == 400:
            print(f"  ⚠️ Falha no parse Markdown (parte {i + 1}): {resp.text} — reenviando como texto puro")
            payload.pop("parse_mode", None)
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
        "data": PUB.strftime("%Y-%m-%d"),
        "pubDate": PUB.strftime("%a, %d %b %Y 05:30:00 -0300"),
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
    <itunes:owner>
      <itunes:name>Daniel Rodrigues</itunes:name>
      <itunes:email>danielsilva.rodrigues.drs@gmail.com</itunes:email>
    </itunes:owner>
    <itunes:summary>Boletim semanal com cotações e análises de boi gordo, milho e soja para GO e MT.</itunes:summary>
    <itunes:category text="Business">
      <itunes:category text="Investing"/>
    </itunes:category>
    <itunes:explicit>false</itunes:explicit>
    <itunes:image href="{pages_base}/capa_campofort.jpg"/>
    <image>
      <url>{pages_base}/capa_campofort.jpg</url>
      <title>CampoFort — Boletim Agropecuário</title>
      <link>{pages_base}</link>
    </image>
    {items_xml}
  </channel>
</rss>"""

    # Escreve na raiz E em docs/ (GitHub Pages serve de docs/)
    Path("podcast_feed.xml").write_text(rss_xml, encoding="utf-8")
    Path("docs/podcast_feed.xml").write_text(rss_xml, encoding="utf-8")
    print(f"  ✅ RSS feed atualizado: {len(episodes)} episódio(s) → podcast_feed.xml + docs/podcast_feed.xml")
    print(f"  🎵 URL do feed: {pages_base}/podcast_feed.xml")


# ─── Supabase ─────────────────────────────────────────────────────────────────
def _supabase_headers() -> dict:
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates",
    }


def _supabase_payload(title: str, telegram_msg: str, published_at: str,
                      audio_url: str | None, episode_number: int | None) -> dict:
    # Resumo curto: primeiras 3 linhas não-vazias
    desc_lines = [l.strip() for l in telegram_msg.split("\n") if l.strip() and not l.startswith("===")]
    return {
        "title": title,
        "summary": " ".join(desc_lines[:3])[:300],
        "content": telegram_msg,
        "published_at": published_at,
        "audio_url": audio_url,
        "spotify_url": SPOTIFY_SHOW_URL,
        "episode_number": episode_number,
    }


def supabase_sync_missing() -> None:
    """Insere no app os episódios do episodes.json que ainda não estão no Supabase
    (ex.: semanas em que o salvamento falhou). Nº do episódio = ordem cronológica."""
    import json as _json
    if not SUPABASE_KEY:
        return
    ep_path = Path("episodes.json")
    if not ep_path.exists():
        return
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/boletins?select=episode_number",
            headers=_supabase_headers(), timeout=15,
        )
        resp.raise_for_status()
        existing = {r["episode_number"] for r in resp.json()}
        eps = list(reversed(_json.loads(ep_path.read_text(encoding="utf-8"))))
        for n, ep in enumerate(eps, 1):
            if n in existing:
                continue
            txt = Path(f"output/boletim_{ep['data'].replace('-', '')}.txt")
            if not txt.exists():
                print(f"  ⚠️  Ep. {n} sem arquivo {txt} — pulado")
                continue
            payload = _supabase_payload(ep["titulo"], txt.read_text(encoding="utf-8"),
                                        f"{ep['data']}T05:30:00-03:00", ep["audio_url"], n)
            r = requests.post(f"{SUPABASE_URL}/rest/v1/boletins",
                              json=payload, headers=_supabase_headers(), timeout=15)
            r.raise_for_status()
            print(f"  ✅ Ep. {n} ({ep['titulo']}) sincronizado no app")
    except Exception as e:
        print(f"  ⚠️  Sincronização Supabase falhou (não crítico): {e}")


def supabase_save_boletim(telegram_msg: str, audio_url: str | None, episode_number: int | None) -> None:
    """Insere ou atualiza o boletim do dia na tabela boletins do Supabase."""
    if not SUPABASE_KEY:
        print("  ⚠️  SUPABASE_SERVICE_KEY ausente — boletim não salvo no app")
        return

    payload = _supabase_payload(f"Boletim CampoFort — {DATE_SHORT}", telegram_msg,
                                PUB.strftime("%Y-%m-%dT05:30:00-03:00"), audio_url, episode_number)
    headers = _supabase_headers()

    try:
        resp = requests.post(
            f"{SUPABASE_URL}/rest/v1/boletins",
            json=payload,
            headers=headers,
            timeout=15,
        )
        resp.raise_for_status()
        print(f"  ✅ Boletim salvo no Supabase (ep. {episode_number})")
    except Exception as e:
        print(f"  ⚠️  Supabase falhou (não crítico): {e}")


# ─── Salvar arquivos locais ────────────────────────────────────────────────────
def save_files(telegram_msg: str, roteiro: str, audio_bytes: bytes) -> None:
    out = Path("output")
    out.mkdir(exist_ok=True)
    (out / f"boletim_{DATE_FILE}.txt").write_text(telegram_msg, encoding="utf-8")
    (out / f"roteiro_{DATE_FILE}.md").write_text(roteiro, encoding="utf-8")
    (out / f"podcast_campofort_{DATE_FILE}.mp3").write_bytes(audio_bytes)
    print(f"💾 Arquivos salvos em output/")


# ─── Main ──────────────────────────────────────────────────────────────────────
SPOTIFY_SHOW_URL  = "https://open.spotify.com/show/033s9dJplOa8SpCMY7EXnd"
PENDING_FILE      = Path("output/boletim_pending.txt")


def main() -> None:
    print(f"\n🌾 CampoFort Boletim Runner — {DATE_SHORT} ({DIA_SEMANA}) — modo: {MODE}\n{'─' * 50}")

    # ── MODO AMOSTRAS: mesmo trecho curto em várias configurações de voz, para
    # escolher de ouvido a mais fiel ao Daniel. Salva em output/amostras/ (artefato).
    if MODE == "amostras":
        texto = preparar_texto_fala(
            "Bom dia, produtor. Olha... a arroba do boi segue firme. "
            "Em Goiás a gente tá vendo trezentos e quarenta e cinco reais por arroba, "
            "e no Mato Grosso, trezentos e vinte e nove.\n\n"
            "Agora presta atenção nisso. Na B3, o contrato de outubro já passa de trezentos e setenta reais. "
            "Então quem tem boi pronto... tem espaço pra negociar melhor. "
            "Mas não é só olhar preço, tá? É fazer a conta do custo da diária no cocho."
        )
        base = {"use_speaker_boost": True, "speed": 1.0}
        amostras = {
            "A_multilingual_estavel": {"model_id": "eleven_multilingual_v2",
                "voice_settings": {**base, "stability": 0.6, "similarity_boost": 0.9, "style": 0.0}},
            "B_multilingual_bem_fiel": {"model_id": "eleven_multilingual_v2",
                "voice_settings": {**base, "stability": 0.75, "similarity_boost": 0.95, "style": 0.0}},
            "C_turbo_portugues": {"model_id": "eleven_turbo_v2_5", "language_code": "pt",
                "voice_settings": {**base, "stability": 0.55, "similarity_boost": 0.9}},
            "D_v3_portugues": {"model_id": "eleven_v3", "language_code": "pt",
                "voice_settings": {"stability": 0.5, "similarity_boost": 0.9}},
        }
        out = Path("output/amostras"); out.mkdir(parents=True, exist_ok=True)
        for nome, cfg in amostras.items():
            try:
                (out / f"{nome}.mp3").write_bytes(_elevenlabs_tts(texto, cfg))
                print(f"  ✅ Amostra {nome}")
            except Exception as e:
                print(f"  ⚠️  Amostra {nome} falhou: {e}")
        return

    # ── MODO AUDIO: refaz só o áudio do dia (voz clonada) a partir do roteiro já
    # gerado, publica com nome novo (o Spotify não rebaixa uma URL já conhecida)
    # e substitui o episódio no feed. Não chama o Claude nem envia Telegram.
    if MODE == "audio":
        roteiro_path  = Path(f"output/roteiro_{DATE_FILE}.md")
        boletim_path  = Path(f"output/boletim_{DATE_FILE}.txt")
        if not roteiro_path.exists() or not boletim_path.exists():
            raise SystemExit(f"❌ Roteiro/boletim de {DATE_SHORT} não encontrado em output/")
        if not ELEVENLABS_API_KEY:
            raise SystemExit("❌ ELEVENLABS_API_KEY ausente")
        audio_bytes = generate_audio_elevenlabs(preparar_texto_fala(roteiro_path.read_text(encoding="utf-8")))
        filename = f"podcast_campofort_{DATE_FILE}_v{NOW.strftime('%H%M')}.mp3"
        Path("output", filename).write_bytes(audio_bytes)
        audio_url = github_upload_release(audio_bytes, filename)
        update_rss_feed(audio_url, boletim_path.read_text(encoding="utf-8"))
        if SUPABASE_KEY:
            try:
                requests.patch(
                    f"{SUPABASE_URL}/rest/v1/boletins?title=eq.Boletim CampoFort — {DATE_SHORT}",
                    json={"audio_url": audio_url}, headers=_supabase_headers(), timeout=15,
                ).raise_for_status()
            except Exception as e:
                print(f"  ⚠️  Supabase audio_url não atualizado (não crítico): {e}")
            supabase_sync_missing()
        print(f"\n🏁 Áudio substituído — {audio_url}")
        return

    # ── MODO SYNC: só completa no app os boletins que faltam no Supabase ──────
    if MODE == "sync":
        print("\n📲 Sincronizando boletins faltantes no Supabase...")
        supabase_sync_missing()
        return

    # ── MODO PUBLISH: apenas envia Telegram com o boletim salvo na terça ──────
    if MODE == "publish":
        if not PENDING_FILE.exists():
            print("⚠️  Nenhum boletim pendente encontrado em output/boletim_pending.txt")
            return
        telegram_msg = PENDING_FILE.read_text(encoding="utf-8")
        print("\n📱 Enviando boletim salvo via Telegram...")
        telegram_send_text(telegram_msg, spotify_url=SPOTIFY_SHOW_URL)
        PENDING_FILE.unlink(missing_ok=True)
        print(f"\n🏁 Boletim publicado com sucesso — {DATE_SHORT}")
        return

    # ── MODO GENERATE ou FULL: gera conteúdo, áudio e RSS ────────────────────
    telegram_msg, roteiro = generate_content()
    audio_bytes = generate_audio(roteiro)
    filename = f"podcast_campofort_{DATE_FILE}.mp3"
    save_files(telegram_msg, roteiro, audio_bytes)

    # Salvar pending para o modo publish (quarta-feira). No modo full o envio é
    # imediato — não deixar pending, senão a quarta reenviaria este boletim.
    if MODE == "generate":
        PENDING_FILE.write_text(telegram_msg, encoding="utf-8")
        print(f"  💾 Boletim salvo em {PENDING_FILE}")

    # Spotify RSS — hospedar MP3 no GitHub Releases e atualizar feed
    audio_url = None
    episode_number = None
    if GITHUB_TOKEN:
        print("\n🎵 Publicando no Spotify RSS via GitHub Releases...")
        try:
            audio_url = github_upload_release(audio_bytes, filename)
            update_rss_feed(audio_url, telegram_msg)
            # Estimar número do episódio pelo episodes.json
            import json as _json
            ep_path = Path("episodes.json")
            if ep_path.exists():
                eps = _json.loads(ep_path.read_text(encoding="utf-8"))
                episode_number = len(eps)
        except Exception as e:
            print(f"  ⚠️  RSS/Release falhou (não crítico): {e}")
    else:
        print("  ⚠️  GITHUB_TOKEN ausente — Spotify RSS ignorado")

    # Salvar no Supabase (app CampoFort)
    print("\n📲 Salvando no Supabase...")
    supabase_save_boletim(telegram_msg, audio_url, episode_number)
    supabase_sync_missing()

    if MODE == "full":
        # Modo manual: envia Telegram imediatamente
        print("\n📱 Enviando via Telegram (modo full)...")
        telegram_send_text(telegram_msg, spotify_url=SPOTIFY_SHOW_URL)
        print(f"\n🏁 Boletim entregue com sucesso — {DATE_SHORT}")
    else:
        # Modo generate: aguarda quarta para enviar
        print(f"\n✅ Geração concluída — Telegram será enviado na quarta-feira às 05h30 BRT")
        print(f"🎵 Feed RSS atualizado — Spotify processará o episódio durante a noite")

    if audio_url:
        print(f"🎵 MP3 público: {audio_url}")


if __name__ == "__main__":
    main()
