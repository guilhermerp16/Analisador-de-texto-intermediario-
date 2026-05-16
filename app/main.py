import string
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional

app = FastAPI(title="Analisador de Texto")

app.mount("/static", StaticFiles(directory="static"), name="static")


# ── Funções de análise ────────────────────────────────────────────────────────

def limpar_texto(texto: str) -> str:
    import re
    texto = texto.lower()
    for pontuacao in string.punctuation:
        if pontuacao == "-":
            continue  # trata o hífen separadamente abaixo
        texto = texto.replace(pontuacao, "")
    # Remove hífens isolados (diálogos, travessões soltos) mas preserva palavras compostas
    texto = re.sub(r'(?<![a-záàãâéêíóôõúüç])-|-(?![a-záàãâéêíóôõúüç])', '', texto)
    return texto


def contar_caracteres(texto: str) -> dict:
    contador: dict = {}
    for char in texto:
        contador[char] = contador.get(char, 0) + 1
    return contador


def contar_palavras(texto: str) -> dict:
    palavras = texto.split()
    contador: dict = {}
    for palavra in palavras:
        contador[palavra] = contador.get(palavra, 0) + 1
    return contador


def mostrar_top_palavras(contador: dict, limite: int = 5) -> list:
    ordenado = sorted(contador.items(), key=lambda x: x[1], reverse=True)
    return ordenado[:limite]


def maior_palavra(texto: str) -> Optional[str]:
    palavras = texto.split()
    if palavras:
        return max(palavras, key=len)
    return None


# ── Integração com API pública ────────────────────────────────────────────────

# API REST do Wiktionary (estrutura por seções de idioma)
WIKTIONARY_REST = "https://pt.wiktionary.org/api/rest_v1/page/definition"
# MediaWiki API do Wiktionary pt — mais confiável, retorna wikitext extraído
WIKTIONARY_MW = "https://pt.wiktionary.org/w/api.php"
# Fallback em inglês
FALLBACK_API = "https://api.dictionaryapi.dev/api/v2/entries/en"

POS_MAP = {
    "Substantivo": "substantivo", "Verbo": "verbo", "Adjetivo": "adjetivo",
    "Advérbio": "advérbio", "Pronome": "pronome", "Preposição": "preposição",
    "Conjunção": "conjunção", "Artigo": "artigo", "Interjeição": "interjeição",
    "noun": "substantivo", "verb": "verbo", "adjective": "adjetivo",
    "adverb": "advérbio", "pronoun": "pronome", "preposition": "preposição",
    "conjunction": "conjunção", "exclamation": "interjeição",
}


def _limpar_html(texto: str) -> str:
    import re
    return re.sub(r"<[^>]+>", "", texto).strip()


def _extrair_definicao_wikitext(wikitext: str, preferir_pt: bool = True) -> Optional[tuple[str, str]]:
    """
    Extrai a primeira definição e classe gramatical de um wikitext do Wiktionary pt.
    Suporta marcadores ={{-pt-}}= e ={{-en-}}= usados pelo Wiktionary em português.
    Retorna (pos, definicao) ou None.
    """
    import re

    # Divide o wikitext em blocos por idioma (={{-pt-}}=, ={{-en-}}=, etc.)
    blocos = []  # lista de (codigo_idioma, conteudo)
    idioma_atual = ""
    linhas_bloco = []

    for linha in wikitext.split("\n"):
        m = re.match(r"^=\{\{-(\w+)-\}\}=$", linha.strip())
        if m:
            if idioma_atual:
                blocos.append((idioma_atual, "\n".join(linhas_bloco)))
            idioma_atual = m.group(1)
            linhas_bloco = []
        else:
            linhas_bloco.append(linha)

    if idioma_atual:
        blocos.append((idioma_atual, "\n".join(linhas_bloco)))

    # Se não encontrou blocos, trata o arquivo inteiro como um bloco
    if not blocos:
        blocos = [("pt", wikitext)]

    # Ordena: pt primeiro se preferir_pt
    if preferir_pt:
        blocos.sort(key=lambda b: (0 if b[0] == "pt" else 1))

    for _idioma, conteudo in blocos:
        pos = ""
        for linha in conteudo.split("\n"):
            linha = linha.strip()

            # Classe gramatical: ==Substantivo==, ==Verbo==, etc.
            pos_match = re.match(r"^==([^=]+)==$", linha)
            if pos_match:
                pos_raw = pos_match.group(1).strip()
                pos = POS_MAP.get(pos_raw, pos_raw.lower())
                continue

            # Definição: linha começando com # mas não ## ou #: ou #*
            if re.match(r"^#[^#:*]", linha):
                def_text = linha[1:]
                # Remove [[link|texto]] → texto
                def_text = re.sub(r"\[\[(?:[^\]|]*\|)?([^\]]+)\]\]", r"\1", def_text)
                # Remove templates de escopo
                def_text = re.sub(r"\{\{escopo2?\|[^}]*\}\}\s*", "", def_text)
                def_text = re.sub(r"\{\{[^}]+\}\}", "", def_text)
                # Remove formatação wiki
                def_text = re.sub(r"'{2,}", "", def_text)
                def_text = re.sub(r"<[^>]+>", "", def_text)
                def_text = def_text.strip(" .,;")
                if len(def_text) >= 2:
                    return (pos, def_text)

    return None


HEADERS = {
    "User-Agent": "AnalisadorDeTexto/2.0 (https://github.com/guilhermerp16/Bootcamp-II; educational project)"
}


async def buscar_definicao(palavra: str) -> Optional[dict]:
    """
    Busca definição de uma palavra:
    1. Wiktionary REST API (pt-BR)
    2. Wiktionary MediaWiki API — parse do wikitext (mais robusto)
    3. Free Dictionary API (inglês) — fallback
    """
    async with httpx.AsyncClient(timeout=7.0, headers=HEADERS) as client:

        # ── 1ª tentativa: Wiktionary REST ────────────────────────────────────
        try:
            r = await client.get(f"{WIKTIONARY_REST}/{palavra}")
            if r.status_code == 200:
                data = r.json()
                secoes = data.get("pt") or data.get("en") or (
                    next(iter(data.values()), None)
                )
                if secoes and isinstance(secoes, list):
                    for secao in secoes:
                        for defn in secao.get("definitions", []):
                            def_text = _limpar_html(defn.get("definition", ""))
                            if def_text:
                                pos_raw = secao.get("partOfSpeech", "")
                                return {
                                    "palavra": palavra,
                                    "partOfSpeech": POS_MAP.get(pos_raw, pos_raw),
                                    "definicao": def_text,
                                    "fonte": "Wiktionary (pt)",
                                }
        except (httpx.RequestError, ValueError, StopIteration):
            pass

        # ── 2ª tentativa: Wiktionary MediaWiki API (wikitext) ─────────────────
        try:
            params = {
                "action": "query",
                "titles": palavra,
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
                "format": "json",
                "formatversion": "2",
            }
            r = await client.get(WIKTIONARY_MW, params=params)
            if r.status_code == 200:
                data = r.json()
                pages = data.get("query", {}).get("pages", [])
                if pages and "missing" not in pages[0]:
                    wikitext = (
                        pages[0]
                        .get("revisions", [{}])[0]
                        .get("slots", {})
                        .get("main", {})
                        .get("content", "")
                    )
                    import re as _re
                    tem_pt = bool(_re.search(r"=\{\{-pt-\}\}=", wikitext))
                    resultado = _extrair_definicao_wikitext(wikitext) if tem_pt else None
                    if resultado:
                        pos, def_text = resultado
                        return {
                            "palavra": palavra,
                            "partOfSpeech": pos,
                            "definicao": def_text,
                            "fonte": "Wiktionary (pt)",
                        }
        except (httpx.RequestError, ValueError, KeyError, IndexError):
            pass

        # ── 3ª tentativa: Free Dictionary (inglês) ───────────────────────────
        try:
            r = await client.get(f"{FALLBACK_API}/{palavra}")
            if r.status_code == 200:
                data = r.json()
                meanings = data[0].get("meanings", [])
                if meanings:
                    pos_raw = meanings[0].get("partOfSpeech", "")
                    defs = meanings[0].get("definitions", [])
                    def_text = defs[0].get("definition", "") if defs else ""
                    if def_text:
                        return {
                            "palavra": palavra,
                            "partOfSpeech": POS_MAP.get(pos_raw, pos_raw),
                            "definicao": def_text,
                            "fonte": "Free Dictionary (en)",
                        }
        except (httpx.RequestError, KeyError, IndexError):
            pass

    return None


# ── Schemas ───────────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    texto: str
    opcoes: list[str]


# ── Rotas ─────────────────────────────────────────────────────────────────────

@app.get("/")
async def index():
    return FileResponse("static/index.html")


@app.post("/analisar")
async def analisar(req: AnalyzeRequest):
    texto = req.texto
    opcoes = req.opcoes

    if not texto.strip():
        raise HTTPException(status_code=400, detail="Texto não pode estar vazio.")

    texto_limpo = limpar_texto(texto)
    resultado: dict = {}

    if "caracteres" in opcoes:
        resultado["caracteres"] = contar_caracteres(texto)

    if "palavras" in opcoes or "top_palavras" in opcoes or "estatisticas" in opcoes:
        palavras_contadas = contar_palavras(texto_limpo)

        if "palavras" in opcoes:
            resultado["palavras"] = dict(palavras_contadas)

        if "top_palavras" in opcoes:
            resultado["top_palavras"] = mostrar_top_palavras(palavras_contadas)

        if "estatisticas" in opcoes:
            resultado["estatisticas"] = {
                "total_palavras": len(texto_limpo.split()),
                "total_caracteres": len(texto_limpo),
            }

    if "maior_palavra" in opcoes:
        resultado["maior_palavra"] = maior_palavra(texto_limpo)

    return resultado


@app.get("/debug/{palavra}")
async def debug(palavra: str):
    """Endpoint temporário para inspecionar respostas brutas das APIs."""
    async with httpx.AsyncClient(timeout=7.0, headers=HEADERS) as client:
        rest_raw = None
        mw_raw = None

        try:
            r = await client.get(f"{WIKTIONARY_REST}/{palavra}")
            rest_raw = {"status": r.status_code, "body": r.json() if r.status_code == 200 else r.text}
        except Exception as e:
            rest_raw = {"erro": str(e)}

        try:
            params = {
                "action": "query", "titles": palavra,
                "prop": "revisions", "rvprop": "content",
                "rvslots": "main", "format": "json", "formatversion": "2",
            }
            r = await client.get(WIKTIONARY_MW, params=params)
            data = r.json()
            pages = data.get("query", {}).get("pages", [])
            wikitext = ""
            if pages and "missing" not in pages[0]:
                wikitext = pages[0].get("revisions", [{}])[0].get("slots", {}).get("main", {}).get("content", "")
            mw_raw = {"status": r.status_code, "primeiras_500_chars": wikitext[:500]}
        except Exception as e:
            mw_raw = {"erro": str(e)}

        return {"wiktionary_rest": rest_raw, "mediawiki": mw_raw}


@app.get("/definicao/{palavra:path}")
async def definicao(palavra: str):
    """Busca definição em pt-BR via Wiktionary; fallback para Free Dictionary API (en)."""
    palavra = palavra.lower().strip()
    # Tenta a palavra como está
    data = await buscar_definicao(palavra)
    if data:
        return data
    # Se tem hífen, tenta sem hífen (ex: "guarda-chuva" → "guarda chuva")
    if "-" in palavra:
        data = await buscar_definicao(palavra.replace("-", " "))
        if data:
            return data
    # Se tem espaço, tenta com hífen (ex: "guarda chuva" → "guarda-chuva")
    if " " in palavra:
        data = await buscar_definicao(palavra.replace(" ", "-"))
        if data:
            return data
    raise HTTPException(status_code=404, detail="Definição não encontrada.")
