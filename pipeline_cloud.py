#!/usr/bin/env python3
"""
Pipeline Cloud CampoFort - GitHub Actions
Toda quarta-feira 07h Brasilia, sem depender do PC.

Secrets GitHub:
  ANTHROPIC_API_KEY  TELEGRAM_BOT_TOKEN  TELEGRAM_CHAT_ID
  OPENAI_API_KEY     SPOTIFY_URL         GITHUB_TOKEN
"""
import asyncio, io, json, os, re, time, xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import formatdate
from pathlib import Path

import anthropic, edge_tts, requests
from bs4 import BeautifulSoup

GITHUB_REPO   = os.environ.get("GITHUB_REPO","danielsilvarodriguesdrs-ship-it/podcast-campofort")
RELEASE_TAG   = "audio"
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY","")
TELEGRAM_TOK  = os.environ.get("TELEGRAM_BOT_TOKEN","")
TELEGRAM_CHAT = os.environ.get("TELEGRAM_CHAT_ID","")
GITHUB_TOKEN  = os.environ.get("GITHUB_TOKEN","")
SPOTIFY_URL   = os.environ.get("SPOTIFY_URL","")
OPENAI_KEY    = os.environ.get("OPENAI_API_KEY","")
OPENAI_VOICE  = "echo"
EDGE_VOICE    = "pt-BR-AntonioNeural"

BRT        = timezone(timedelta(hours=-3))
NOW        = datetime.now(BRT)
DATE_BR    = NOW.strftime("%d/%m/%Y")
DATE_FILE  = NOW.strftime("%Y%m%d")
DATE_ISO   = NOW.strftime("%Y-%m-%d")
WEEKDAY_PT = ["Segunda-feira","Terca-feira","Quarta-feira",
              "Quinta-feira","Sexta-feira","Sabado","Domingo"][NOW.weekday()]

BOLETIM_PATH   = Path(f"boletim_semanal_campofort_{DATE_FILE}.md")
ROTEIRO_PATH   = Path(f"roteiro_podcast_campofort_{DATE_FILE}.md")
MP3_PATH       = Path(f"podcast_campofort_{DATE_FILE}.mp3")
TG_PATH        = Path(f"mensagem_telegram_{DATE_FILE}.txt")
RSS_PATH       = Path("docs/podcast_feed.xml")
EPISODIOS_PATH = Path("episodios.json")
HEADERS        = {"User-Agent":"Mozilla/5.0","Accept-Language":"pt-BR,pt;q=0.9"}

# == 1. Dados =================================================================

def get_dollar():
    try:
        d = requests.get("https://economia.awesomeapi.com.br/json/last/USD-BRL",timeout=10).json()["USDBRL"]
        return f"R$ {float(d['bid']):.2f} ({float(d['pctChange']):+.2f}% no dia)"
    except Exception as e: return f"indisponivel ({e})"

def get_dollar_history(days=7):
    try:
        rows = requests.get(f"https://economia.awesomeapi.com.br/json/daily/USD-BRL/{days}",timeout=10).json()
        out = []
        for row in reversed(rows):
            dt  = datetime.fromtimestamp(int(row["timestamp"]),tz=BRT).strftime("%d/%m")
            bid = float(row["bid"]); pct = float(row["pctChange"])
            out.append(f"{dt}|{bid:.4f}|{pct:+.2f}|{'up' if pct>0 else 'down' if pct<0 else 'flat'}")
        return "\n".join(out)
    except Exception as e: return f"indisponivel ({e})"

def fetch_text(url, max_chars=3000):
    try:
        r = requests.get(url,headers=HEADERS,timeout=15); r.raise_for_status()
        soup = BeautifulSoup(r.content,"html.parser")
        for t in soup(["script","style","nav","header","footer","aside","form"]): t.decompose()
        return re.sub(r"\n{3,}","\n\n",soup.get_text(separator="\n",strip=True))[:max_chars]
    except Exception as e: return f"[erro: {e}]"

def gather_market_data():
    print("  -> Dados de mercado...")
    hist = get_dollar_history(7)
    raw = {"dollar": get_dollar(), "dollar_history": hist}
    for key,urls in [
        ("boi",["https://www.noticiasagricolas.com.br/cotacoes/boi-gordo","https://www.canalrural.com.br/cotacoes/boi/"]),
        ("milho",["https://www.noticiasagricolas.com.br/cotacoes/milho"]),
        ("soja",["https://www.noticiasagricolas.com.br/cotacoes/soja"]),
        ("politica",["https://revistaoeste.com/agronegocio/","https://revistaoeste.com/politica/"]),
        ("regulatorio",["https://www.noticiasagricolas.com.br/noticias/boi","https://www.canalrural.com.br/pecuaria/"]),
    ]:
        texts=[]
        for u in urls:
            print(f"  -> {u}"); texts.append(fetch_text(u)); time.sleep(1)
        raw[key]="\n---\n".join(texts)
    return raw

# == 2. Grafico do Dolar =======================================================

def generate_dollar_chart(history_raw):
    """Gera grafico PNG da variacao do dolar (7 dias) via matplotlib."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        dates, vals, pcts = [], [], []
        for line in history_raw.strip().split("\n"):
            p = line.split("|")
            if len(p) >= 3:
                try:
                    dates.append(p[0])
                    vals.append(float(p[1]))
                    pcts.append(float(p[2]))
                except: pass

        if len(vals) < 2:
            return None

        fig, ax = plt.subplots(figsize=(9, 4))
        fig.patch.set_facecolor("#0d1117")
        ax.set_facecolor("#0d1117")

        colors = ["#22c55e" if p >= 0 else "#ef4444" for p in pcts]
        ax.plot(range(len(vals)), vals, color="#22c55e", linewidth=2.5, zorder=3)
        ax.fill_between(range(len(vals)), vals, min(vals)*0.9995,
                        alpha=0.18, color="#22c55e")

        for i, (v, c) in enumerate(zip(vals, colors)):
            ax.plot(i, v, "o", color=c, markersize=7, zorder=4)

        ax.set_xticks(range(len(dates)))
        ax.set_xticklabels(dates, color="#94a3b8", fontsize=10)
        ax.tick_params(colors="#94a3b8")
        ax.yaxis.set_major_formatter(plt.FormatStrFormatter("R$ %.3f"))
        ax.yaxis.label.set_color("#94a3b8")
        for spine in ax.spines.values(): spine.set_color("#1e293b")
        ax.grid(True, color="#1e293b", linewidth=0.8, linestyle="--")
        ax.set_title(f"USD/BRL - Ultimos 7 dias uteis  |  Hoje: {vals[-1]:.4f}",
                     color="#e2e8f0", fontsize=12, fontweight="bold", pad=12)

        last_val = vals[-1]
        direction = "alta" if pcts[-1] >= 0 else "queda"
        color_dir = "#22c55e" if pcts[-1] >= 0 else "#ef4444"
        ax.annotate(f"R$ {last_val:.4f}",
                    xy=(len(vals)-1, last_val),
                    xytext=(len(vals)-1.8, last_val + 0.002),
                    fontsize=11, fontweight="bold", color=color_dir,
                    arrowprops=dict(arrowstyle="->", color=color_dir, lw=1.5))

        plt.tight_layout(pad=1.5)
        buf = io.BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                    facecolor=fig.get_facecolor())
        buf.seek(0)
        plt.close(fig)
        print("  OK Grafico do dolar gerado")
        return buf.getvalue()
    except Exception as e:
        print(f"  ! Grafico falhou: {e}")
        return None

# == 3. Conteudo via Claude ====================================================

SYSTEM_PROMPT = (
    "Voce e o gerador do Boletim Semanal CampoFort, apresentado por Daniel Rodrigues.\n\n"
    "REGRAS - VALEM PARA OS TRES OUTPUTS:\n"
    "- Cotacoes: boi gordo, milho e soja SEMPRE Goias E Mato Grosso lado a lado\n"
    "- Politica: SOMENTE Revista Oeste (revistaoeste.com)\n"
    "- VALORES: SEMPRE digitos + unidade. Ex: R$ 321,50/@ | R$ 64,50/sc | R$ 5,02\n"
    "  PROIBIDO escrever valores por extenso em qualquer output\n"
    "- NAO mencionar Selic em nenhuma secao\n"
    "- Tom tecnico, firme, didatico e OTIMISTA: sempre inclua perspectiva positiva e criterio\n"
    "  de oportunidade ou acao concreta para o produtor"
)

def _hist_fmt(raw):
    out=[]
    for line in raw.strip().split("\n"):
        p=line.split("|")
        if len(p)>=4:
            dt,bid,pct,seta=p
            e={"up":"subiu","down":"recuou","flat":"estavel"}.get(seta.strip(),"")
            out.append(f"  {dt}: R$ {float(bid):.4f} ({pct}%) [{e}]")
    return "\n".join(out) if out else "  indisponivel"

def generate_content(data):
    hist = _hist_fmt(data.get("dollar_history",""))
    prompt = (
        f"Data: {WEEKDAY_PT}, {DATE_BR}\n\n"
        f"Dolar hoje: {data['dollar']}\n"
        f"Historico dolar 7 dias:\n{hist}\n\n"
        f"BOI GORDO:\n{data['boi'][:2000]}\n\n"
        f"MILHO:\n{data['milho'][:1200]}\n\n"
        f"SOJA:\n{data['soja'][:1200]}\n\n"
        f"POLITICA (Revista Oeste):\n{data['politica'][:1800]}\n\n"
        f"REGULATORIO:\n{data['regulatorio'][:1200]}\n\n"
        "---\nRetorne JSON exato (sem texto fora do JSON):\n"
        '{"boletim_md":"...","roteiro_narracao":"...","descricao_rss":"...","mensagem_telegram":"..."}\n\n'
        "=== boletim_md ===\n"
        "Valores SEMPRE em digitos. NAO mencionar Selic.\n"
        "Para cada secao de commodity (boi/milho/soja), termine com 1 linha otimista de acao.\n"
        "Secoes: Cabecalho | BOI GO/MT | MILHO GO/MT | SOJA GO/MT | DOLAR (contexto + impacto pratico) | POLITICA Revista Oeste | PANORAMA | PROJECOES | Assinatura [LINK DO PODCAST]\n\n"
        "=== roteiro_narracao ===\n"
        "ABERTURA EXATA: 'Bom dia, produtor(a). Este e o Boletim Informativo CampoFort, apresentado por Daniel Rodrigues. "
        "Hoje e " + WEEKDAY_PT + ", " + DATE_BR + ". Vamos aos mercados.'\n"
        "Valores em digitos. NAO mencionar Selic.\n"
        "Dolar: 'O dolar encerrou hoje a [valor]. Nos ultimos 7 dias oscilou entre [min] e [max]. Para o produtor que exporta, [impacto otimista e pratico].'\n"
        "Tom: firme, tecnico, com comentarios otimistas e proposta de acao.\n"
        "ENCERRAMENTO: 'Nutricao estrategica. Resultado no campo. Ate a proxima quarta-feira.'\n\n"
        "=== descricao_rss ===\n"
        "1 frase com as 3 cotacoes principais (boi GO e MT, milho GO, soja GO) em digitos + 1 manchete de politica. Max 200 chars.\n\n"
        "=== mensagem_telegram ===\n"
        "2500-3500 chars. *negrito* _italico_.\n"
        "NAO incluir secao de dolar - o grafico sera enviado separadamente.\n"
        "Para cada commodity, inclua emoji e 1 linha otimista de oportunidade.\n"
        "Politica: cada noticia Revista Oeste com ▶️.\n"
        "Final: '*Ouca o episodio completo no Spotify:*\\n[LINK_SPOTIFY]\\n\\n"
        "_Daniel Rodrigues | CampoFort_\\n_Nutricao estrategica. Resultado no campo._'"
    )
    client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    resp = client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=6000,
        system=SYSTEM_PROMPT,
        messages=[{"role":"user","content":prompt}]
    )
    raw = resp.content[0].text.strip()
    m = re.search(r"\{[\s\S]*\}", raw)
    if not m: raise ValueError(f"JSON invalido: {raw[:300]}")
    result = json.loads(m.group())
    if "mensagem_whatsapp" in result and "mensagem_telegram" not in result:
        result["mensagem_telegram"] = result.pop("mensagem_whatsapp")
    return result

# == 4. Audio =================================================================

def _clean(text):
    text = re.sub(r"#{1,6}\s+","",text)
    text = re.sub(r"\*{1,2}([^*]+)\*{1,2}",r"\1",text)
    text = re.sub(r"`[^`]+`","",text)
    text = re.sub(r"\[([^\]]+)\]\([^\)]+\)",r"\1",text)
    text = re.sub(r"_{1,2}([^_]+)_{1,2}",r"\1",text)
    return text.strip()

def generate_audio_openai(text, path):
    if not OPENAI_KEY: return False
    try:
        r = requests.post(
            "https://api.openai.com/v1/audio/speech",
            headers={"Authorization":f"Bearer {OPENAI_KEY}","Content-Type":"application/json"},
            json={"model":"tts-1-hd","voice":OPENAI_VOICE,"input":text,"speed":1.0},
            timeout=120
        )
        if r.status_code == 200:
            path.write_bytes(r.content)
            print(f"  OK OpenAI TTS ({OPENAI_VOICE}) - {len(r.content)//1024} KB")
            return True
        print(f"  ! OpenAI TTS {r.status_code}: {r.text[:150]}")
        return False
    except Exception as e:
        print(f"  ! OpenAI TTS erro: {e}"); return False

async def _edge_async(text, path):
    await edge_tts.Communicate(text,voice=EDGE_VOICE).save(str(path))

def generate_audio(roteiro_text, path):
    text = _clean(roteiro_text)
    if OPENAI_KEY:
        print(f"  Usando OpenAI TTS ({OPENAI_VOICE})...")
        if generate_audio_openai(text, path): return
        print("  Fallback para Edge TTS...")
    asyncio.run(_edge_async(text, path))
    print(f"  OK Edge TTS ({EDGE_VOICE})")

# == 5. GitHub Releases =======================================================

def get_or_create_release(gh):
    r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/tags/{RELEASE_TAG}",headers=gh)
    if r.status_code == 200: return r.json()
    r = requests.post(f"https://api.github.com/repos/{GITHUB_REPO}/releases",headers=gh,
        json={"tag_name":RELEASE_TAG,"name":"Episodios CampoFort","draft":False,"prerelease":False})
    r.raise_for_status(); return r.json()

def upload_mp3(mp3_path):
    gh = {"Authorization":f"Bearer {GITHUB_TOKEN}","Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
    rel = get_or_create_release(gh)
    for a in rel.get("assets",[]):
        if a["name"]==mp3_path.name:
            requests.delete(f"https://api.github.com/repos/{GITHUB_REPO}/releases/assets/{a['id']}",headers=gh)
            time.sleep(1)
    with open(mp3_path,"rb") as f:
        r = requests.post(f"{rel['upload_url'].split('{')[0]}?name={mp3_path.name}",
            headers={**gh,"Content-Type":"audio/mpeg"},data=f)
    r.raise_for_status(); return r.json()["browser_download_url"]

# == 6. RSS ===================================================================

def _sub(parent,tag,text=None,**a):
    el=ET.SubElement(parent,tag,**a)
    if text: el.text=text
    return el

def update_rss(audio_url,titulo,descricao,duracao_seg,mp3_size):
    ET.register_namespace("itunes","http://www.itunes.com/dtds/podcast-1.0.dtd")
    ET.register_namespace("content","http://purl.org/rss/1.0/modules/content/")
    ns="http://www.itunes.com/dtds/podcast-1.0.dtd"
    RSS_PATH.parent.mkdir(parents=True,exist_ok=True)
    if RSS_PATH.exists():
        tree=ET.parse(RSS_PATH); root=tree.getroot(); channel=root.find("channel")
    else:
        root=ET.Element("rss",version="2.0",attrib={"xmlns:itunes":ns,"xmlns:content":"http://purl.org/rss/1.0/modules/content/"})
        channel=ET.SubElement(root,"channel")
        _sub(channel,"title","Boletim CampoFort"); _sub(channel,"link","https://campofort.com.br")
        _sub(channel,"description","Boletim semanal - Goias e Mato Grosso."); _sub(channel,"language","pt-BR")
        ET.SubElement(channel,f"{{{ns}}}author").text="Daniel Rodrigues"
        ET.SubElement(channel,f"{{{ns}}}explicit").text="false"
        ET.SubElement(channel,f"{{{ns}}}image",href="https://danielsilvarodriguesdrs-ship-it.github.io/podcast-campofort/capa_campofort.jpg")
        cat=ET.SubElement(channel,f"{{{ns}}}category",text="Business")
        ET.SubElement(cat,f"{{{ns}}}category",text="Agriculture")

    # Atualiza lastBuildDate para forçar refresh do Spotify
    lbd = channel.find("lastBuildDate")
    if lbd is None:
        lbd = ET.SubElement(channel, "lastBuildDate")
    lbd.text = formatdate(NOW.timestamp())

    # Remove duplicata com mesmo guid
    for old in channel.findall("item"):
        g = old.find("guid")
        if g is not None and g.text == f"campofort-{DATE_FILE}":
            channel.remove(old)

    item=ET.Element("item")
    _sub(item,"title",titulo); _sub(item,"description",descricao)
    _sub(item,"pubDate",formatdate(NOW.timestamp()))
    _sub(item,"guid",f"campofort-{DATE_FILE}",isPermaLink="false")
    ET.SubElement(item,"enclosure",url=audio_url,length=str(mp3_size),type="audio/mpeg")
    ET.SubElement(item,f"{{{ns}}}duration").text=str(duracao_seg)
    ET.SubElement(item,f"{{{ns}}}author").text="Daniel Rodrigues"

    existing=channel.find("item")
    channel.insert(list(channel).index(existing) if existing is not None else len(list(channel)),item)
    tree2=ET.ElementTree(root); ET.indent(tree2,space="  ")
    tree2.write(RSS_PATH,encoding="utf-8",xml_declaration=True)

def update_episodios_json(audio_url,titulo,descricao,duracao_seg):
    data={}
    if EPISODIOS_PATH.exists(): data=json.loads(EPISODIOS_PATH.read_text(encoding="utf-8"))
    eps=[e for e in data.get("episodios",[]) if e.get("data")!=DATE_ISO]
    eps.insert(0,{"data":DATE_ISO,"titulo":titulo,"descricao":descricao,
                  "duracao_seg":duracao_seg,"audio_url":audio_url,"mp3_local":MP3_PATH.name})
    data["episodios"]=eps
    EPISODIOS_PATH.write_text(json.dumps(data,ensure_ascii=False,indent=4),encoding="utf-8")

# == 7. Telegram ==============================================================

def send_telegram(message):
    if not TELEGRAM_TOK or not TELEGRAM_CHAT:
        print("  ! Secrets Telegram ausentes."); return False
    api=f"https://api.telegram.org/bot{TELEGRAM_TOK}/sendMessage"
    parts=[message[i:i+4000] for i in range(0,len(message),4000)]
    ok=True
    for i,part in enumerate(parts,1):
        try:
            r=requests.post(api,json={"chat_id":TELEGRAM_CHAT,"text":part,
                "parse_mode":"Markdown","disable_web_page_preview":False},timeout=30)
            if r.status_code==200: print(f"  OK Telegram {i}/{len(parts)}")
            else: print(f"  ! Telegram {r.status_code}: {r.text[:150]}"); ok=False
        except Exception as e: print(f"  ! Telegram erro: {e}"); ok=False
        if len(parts)>1: time.sleep(1)
    return ok

def send_telegram_photo(image_bytes, caption=""):
    """Envia grafico como foto no Telegram."""
    if not TELEGRAM_TOK or not TELEGRAM_CHAT or image_bytes is None:
        return False
    api=f"https://api.telegram.org/bot{TELEGRAM_TOK}/sendPhoto"
    try:
        r=requests.post(api,
            data={"chat_id":TELEGRAM_CHAT,"caption":caption,"parse_mode":"Markdown"},
            files={"photo":("dolar_chart.png",image_bytes,"image/png")},
            timeout=30)
        if r.status_code==200: print("  OK Grafico do dolar enviado ao Telegram")
        else: print(f"  ! Telegram photo {r.status_code}: {r.text[:150]}")
        return r.status_code==200
    except Exception as e:
        print(f"  ! Telegram photo erro: {e}"); return False

# == Main =====================================================================

def main():
    print(f"\n{'='*55}\n  PIPELINE CAMPOFORT - {DATE_BR}\n{'='*55}\n")
    if MP3_PATH.exists(): print(f"Audio {MP3_PATH.name} ja existe. Encerrando."); return

    print("[1/7] Coletando dados...")
    data=gather_market_data()
    print(f"  OK Dolar: {data['dollar']}")

    print("\n[2/7] Gerando grafico do dolar...")
    chart_bytes = generate_dollar_chart(data.get("dollar_history",""))

    print("\n[3/7] Gerando conteudo via Claude...")
    content=generate_content(data)
    titulo=f"Boletim CampoFort - {DATE_BR}"
    descricao=content.get("descricao_rss") or titulo
    BOLETIM_PATH.write_text(content["boletim_md"],encoding="utf-8")
    ROTEIRO_PATH.write_text(
        f"# Roteiro Podcast CampoFort - {DATE_BR}\n"
        f"Voz: OpenAI '{OPENAI_VOICE}' | fallback: Edge TTS\n\n---\n\n"
        f"## ROTEIRO PARA NARRACAO\n\n{content['roteiro_narracao']}\n",
        encoding="utf-8")
    print(f"  OK {BOLETIM_PATH.name}")

    print("\n[4/7] Gerando audio...")
    generate_audio(content["roteiro_narracao"],MP3_PATH)
    mp3_size=MP3_PATH.stat().st_size
    print(f"  OK {MP3_PATH.name} ({mp3_size//1024} KB)")

    print("\n[5/7] Subindo para GitHub Releases...")
    if not GITHUB_TOKEN: print("  ! GITHUB_TOKEN ausente."); audio_url="[PENDENTE]"
    else: audio_url=upload_mp3(MP3_PATH); print(f"  OK {audio_url}")

    print("\n[6/7] Atualizando RSS e episodios.json...")
    duracao_seg=max(240,int(mp3_size/24000))
    update_rss(audio_url,titulo,descricao,duracao_seg,mp3_size)
    update_episodios_json(audio_url,titulo,descricao,duracao_seg)
    print(f"  OK RSS e episodios.json")

    print("\n[7/7] Enviando via Telegram...")
    spotify_link=SPOTIFY_URL if SPOTIFY_URL else audio_url+" _(Spotify em breve)_"
    tg_msg=(content["mensagem_telegram"]
            .replace("[LINK_AUDIO]",audio_url)
            .replace("[LINK_SPOTIFY]",spotify_link))
    TG_PATH.write_text(tg_msg,encoding="utf-8")

    if TELEGRAM_TOK and TELEGRAM_CHAT:
        # 1. Envia o grafico do dolar primeiro
        chart_caption = f"*USD/BRL - Variacao dos ultimos 7 dias*\n_{DATE_BR}_"
        send_telegram_photo(chart_bytes, caption=chart_caption)
        time.sleep(1)
        # 2. Envia o boletim completo
        send_telegram(tg_msg)
    else:
        print("  ! Secrets Telegram ausentes. Mensagem em", TG_PATH)

    print(f"\n{'='*55}")
    print(f"  Audio: {MP3_PATH.name} ({mp3_size//1024} KB)")
    print(f"  Spotify: {spotify_link[:70]}")
    print(f"{'='*55}\n")

if __name__ == "__main__":
    main()
