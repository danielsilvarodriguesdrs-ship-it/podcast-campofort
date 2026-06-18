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
PROMPT = f"""
Você é o assistente de Daniel Rodrigues, representante técnico-comercial da CampoFort Nutrição Estratégica
e da Cria Bem Nutrição Animal. Gere o BOLETIM SEMANAL CAMPOFORT para {DATE_SHORT} ({DIA_SEMANA}).

══════════════════════════════════════
REGRAS ABSOLUTAS (sem exceção):
══════════════════════════════════════
1. Todo texto em Português Brasileiro correto — sem anglicismos, sem palavras em inglês ou espanhol
2. NÃO mencionar SELIC em nenhum trecho
3. Foco geográfico: boi gordo, milho e soja para GOIÁS e MATO GROSSO lado a lado
4. Fonte política obrigatória: Revista Oeste (revistaoeste.com) — 1 fato político da semana
5. Use os dados mais recentes encontrados nas pesquisas — se não houver dados de hoje, use os de ontem ou dos últimos 3 dias, indicando a data de referência. NUNCA pergunte ao usuário nem peça confirmação. SEMPRE gere o boletim completo com os melhores dados disponíveis.
6. Linguagem profissional, direta, dinâmica — voltada ao produtor rural de GO e MT
7. Separadores ━━━━━━━━━━━━━━━━━━━━, marcadores ▸, emojis nos cabeçalhos
8. Roteiro: todos os números por extenso em português (sem R$, %, /, @, sc, bu — escreva "reais", "por cento", etc.)
9. O roteiro do podcast DEVE ter entre 600 e 900 palavras — equivalente a 4 a 5 minutos de narração. Desenvolva cada bloco com análise, contexto e orientação prática para o produtor.

══════════════════════════════════════
PESQUISAS OBRIGATÓRIAS — faça ANTES de escrever:
══════════════════════════════════════
1. boi gordo Goiás cotação arroba {MES_ANO}
2. boi gordo Mato Grosso IMEA preço semana atual
3. B3 boi gordo contrato futuro hoje {DATE_SHORT}
4. milho Rio Verde Goiás saca preço hoje
5. milho Mato Grosso IMEA disponível semana
6. B3 milho contratos futuros hoje
7. soja Sul Goiano cotação saca semana
8. soja Mato Grosso IMEA preço semana
9. Chicago soja milho fechamento hoje
10. dólar real cotação hoje
11. site:revistaoeste.com agronegócio política semana
12. exportação carne bovina Brasil China veto UE {MES_ANO}
13. Plano Safra crédito rural agronegócio novidade {MES_ANO}

══════════════════════════════════════
SAÍDA ESPERADA — dois blocos separados:
══════════════════════════════════════

BLOCO 1 — MENSAGEM TELEGRAM (entre ===TELEGRAM_INICIO=== e ===TELEGRAM_FIM===):

===TELEGRAM_INICIO===
📊 *BOLETIM CAMPOFORT* — {DATE_SHORT}
_{DIA_SEMANA.capitalize()} | Mercado Agropecuário_

Bom dia, produtor.

━━━━━━━━━━━━━━━━━━━━
🐂 *BOI GORDO*

▸ GO R$ XXX,XX/@ (à vista) | R$ XXX,XX/@ (prazo 30 dias)
▸ MT R$ XXX,XX/@ (Cuiabá) | R$ XXX,XX/@ (Sudeste)
▸ B3 [mês próx] R$ XXX,XX/@ (+X,XX%) | [mês seguinte] R$ XXX,XX/@ (+X,XX%)

[2 linhas de análise — situação de oferta, demanda, perspectiva]

━━━━━━━━━━━━━━━━━━━━
🌽 *MILHO*

▸ CEPEA/Esalq R$ XX,XX/sc (+X,XX%)
▸ GO Rio Verde ~R$ XX,XX/sc | MT (IMEA) R$ XX,XX/sc (-X,XX%)
▸ B3 [mês] R$ XX,XX/sc | Chicago US$ X,XX/bu (-X,XX%)

[2 linhas de análise — contexto de oferta safrinha, oportunidade ou risco]

━━━━━━━━━━━━━━━━━━━━
🌱 *SOJA*

▸ Paranaguá R$ XXX,XX/sc (+X,XX%) | Paraná R$ XXX,XX/sc
▸ MT (IMEA) R$ XXX,XX/sc (+X,XX%) | Chicago US$ XX,XX/bu (+X,XX%)

[2 linhas de análise — câmbio, exportação, perspectiva]

━━━━━━━━━━━━━━━━━━━━
💵 *CÂMBIO*

▸ Dólar R$ X,XX
▸ [1 linha de impacto direto no agronegócio]

━━━━━━━━━━━━━━━━━━━━
🏛️ *POLÍTICA* _(Revista Oeste)_

[2 a 3 linhas do fato político mais relevante da semana com leitura direta para o produtor rural]

━━━━━━━━━━━━━━━━━━━━
🔎 *PANORAMA*

▸ [destaque regulatório ou comercial 1 — frase objetiva]
▸ [destaque regulatório ou comercial 2]
▸ [destaque regulatório ou comercial 3 se relevante]

━━━━━━━━━━━━━━━━━━━━
_Daniel Rodrigues_
_CampoFort Nutrição Estratégica_
_Representante técnico-comercial — Cria Bem Nutrição Animal_
_Nutrição estratégica. Resultado no campo._
===TELEGRAM_FIM===

──────────────────────────────────────

BLOCO 2 — ROTEIRO DO PODCAST (entre ===ROTEIRO_INICIO=== e ===ROTEIRO_FIM===):

===ROTEIRO_INICIO===
[Roteiro narrável de 4 a 5 minutos. Todos os números, unidades e símbolos escritos POR EXTENSO:
R$ 330,00 → "trezentos e trinta reais por arroba"
+0,61% → "alta de zero vírgula sessenta e um por cento"
US$ 4,14/bu → "quatro dólares e quatorze centavos por bushel"
Nomes de meses e datas também por extenso.

ABERTURA OBRIGATÓRIA:
"Bom dia, produtor. Este é o Boletim Informativo CampoFort. Hoje é {DIA_SEMANA}, {DATE_LONG}. Vamos aos mercados."

Blocos: BOI GORDO → MILHO → SOJA → CÂMBIO → POLÍTICA DA SEMANA → PANORAMA

ENCERRAMENTO OBRIGATÓRIO:
"Este boletim foi elaborado por Daniel da CampoFort Nutrição Estratégica, representante técnico-comercial da Cria Bem Nutrição Animal. Nutrição estratégica. Resultado no campo. Até a próxima quarta-feira."
]
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
def telegram_send_text(text: str) -> None:
    """Envia mensagem de texto (divide em partes se necessário)."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    # Telegram: limite de 4096 caracteres por mensagem
    for i, chunk in enumerate([text[j:j + 4000] for j in range(0, len(text), 4000)]):
        resp = requests.post(url, json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": chunk,
            "parse_mode": "Markdown"
        }, timeout=30)
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
    save_files(telegram_msg, roteiro, audio_bytes)

    print("\n📱 Enviando via Telegram...")
    telegram_send_text(telegram_msg)
    telegram_send_audio(audio_bytes, f"podcast_campofort_{DATE_FILE}.mp3")

    print(f"\n🏁 Boletim entregue com sucesso — {DATE_SHORT}")


if __name__ == "__main__":
    main()
