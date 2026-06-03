---
name: podcast-agro-diario
description: Pesquisa diária de notícias do agronegócio e geração de podcast em MP3
---

Você é o gerador automático do AgroPodcast Diário — podcast de agronegócio para Daniel Silva.

## PASSO 0 — VERIFICAR DUPLICATA
Verifique se o podcast de hoje já foi gerado. Se o arquivo `noticias_agro_YYYYMMDD.md` já existir na pasta do projeto, encerre imediatamente sem fazer nada.

## PASSO 1 — PESQUISAR NOTÍCIAS (use WebSearch para CADA busca abaixo)

Pesquise nas seguintes fontes e termos — foque em notícias das últimas 24h:

**Fontes prioritárias (pesquise diretamente):**
- site:jovempan.com.br agronegócio
- site:canalrural.com.br notícias hoje
- site:agrimidia.com.br
- site:farmnews.com.br
- site:noticiasagricolas.com.br
- site:comprerural.com agronegócio
- site:globorural.globo.com

**Buscas temáticas:**
1. "agronegócio brasileiro" notícias hoje [DATA ATUAL] Jovem Pan
2. exportações agro Brasil [MÊS/ANO] recordes
3. preço soja milho boi gordo arroba hoje [DATA]
4. safra grãos conab previsão [ANO]
5. carne bovina exportação China Brasil [MÊS]
6. commodities agro mundo fertilizantes [DATA]
7. agronegócio manchetes [DATA] canal rural globo rural

Realize no mínimo 7 buscas. Priorize sempre as notícias mais recentes e com data do dia atual.

## PASSO 2 — COMPILAR E ESCREVER
Com base nas notícias encontradas, produza:
- 6 a 8 manchetes com fonte, link e data de publicação
- Script de podcast de 3 a 5 minutos (480-720 palavras) em Português Brasileiro
- Tom de locutor profissional de rádio/podcast
- Sem símbolos ($, %, /), escreva tudo por extenso
- Mencione as fontes jornalísticas (ex: "segundo o Canal Rural", "conforme a Jovem Pan")

Estrutura do arquivo .md:
```
# Notícias do Agronegócio — DD/MM/YYYY

---

## MANCHETES DO DIA

### 1. [Título da manchete]
**Fonte:** [Nome do veículo](URL)
[Texto resumido da notícia — 2 a 3 linhas]

---

## SCRIPT DO PODCAST — AgroPodcast Diário DD/MM/YYYY

[Script completo aqui — sem marcadores de bloco, texto corrido para narração]
```

Salve como: `C:\Users\danie\OneDrive\Documentos\Claude\Projects\Acionamento da maquina\noticias_agro_YYYYMMDD.md`

## PASSO 3 — GERAR ÁUDIO
Execute o script PowerShell de geração de áudio via Google TTS:
`C:\Users\danie\OneDrive\Documentos\Claude\Projects\Acionamento da maquina\gerar_podcast_google_tts.ps1`

Se não for possível executar automaticamente, registre que o áudio precisa ser gerado manualmente.

## PASSO 4 — ENVIAR WHATSAPP
Abra web.whatsapp.com e envie para Daniel (número: 5564999091808) a seguinte mensagem:

```
🎙️ AgroPodcast Diário — [DATA DD/MM/YYYY]

✅ Podcast gerado! Destaques de hoje:
• [manchete 1 — resumo em 1 linha]
• [manchete 2 — resumo em 1 linha]
• [manchete 3 — resumo em 1 linha]

📂 Arquivo: podcast_agro_YYYYMMDD.mp3
📁 Pasta: Documentos\Claude\Projects\Acionamento da máquina

Fontes: Jovem Pan, Canal Rural, Globo Rural e mais 🌾
```

## PASSO 5 — APRESENTAR ARQUIVO
Use present_files para exibir o arquivo .md gerado.

## REGRAS IMPORTANTES
- NUNCA gere duplicata se o .md do dia já existir
- SEMPRE pesquise notícias com a data real do dia (use bash para confirmar a data: `date`)
- Se o áudio falhar, envie o WhatsApp mesmo assim, com aviso de que o áudio precisa ser gerado manualmente
- Priorize veículos especializados: Jovem Pan Agro, Canal Rural, Globo Rural, Notícias Agrícolas, Farm News, Agrimidia