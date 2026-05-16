"""
Testes unitários e de integração do Analisador de Texto.
Os testes de integração com a API externa usam mock (unittest.mock)
para não depender de conexão real durante o CI.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport

from app.main import (
    app,
    contar_caracteres,
    contar_palavras,
    limpar_texto,
    mostrar_top_palavras,
    maior_palavra,
    buscar_definicao,
)


# ── Testes unitários ──────────────────────────────────────────────────────────

def test_contar_caracteres():
    resultado = contar_caracteres("aaa")
    assert resultado["a"] == 3


def test_contar_palavras():
    resultado = contar_palavras("ola ola mundo")
    assert resultado["ola"] == 2
    assert resultado["mundo"] == 1


def test_limpar_texto():
    assert limpar_texto("Olá, mundo!!!") == "olá mundo"


def test_limpar_texto_preserva_hifen_composto():
    assert limpar_texto("guarda-chuva") == "guarda-chuva"


def test_limpar_texto_remove_hifen_isolado():
    resultado = limpar_texto("- Olá mundo")
    assert "-" not in resultado


def test_top_palavras():
    contador = {"a": 5, "b": 2, "c": 1}
    top = mostrar_top_palavras(contador, limite=2)
    assert top[0][0] == "a"
    assert len(top) == 2


def test_maior_palavra():
    assert maior_palavra("o gato correu rapidamente") == "rapidamente"


def test_maior_palavra_vazia():
    assert maior_palavra("") is None


# ── Testes de integração (API interna) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_endpoint_analisar_palavras():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/analisar",
            json={"texto": "hello world hello", "opcoes": ["palavras", "top_palavras"]},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["palavras"]["hello"] == 2
    assert data["top_palavras"][0][0] == "hello"


@pytest.mark.asyncio
async def test_endpoint_analisar_estatisticas():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/analisar",
            json={"texto": "um dois três", "opcoes": ["estatisticas"]},
        )
    assert response.status_code == 200
    data = response.json()
    assert data["estatisticas"]["total_palavras"] == 3


@pytest.mark.asyncio
async def test_endpoint_texto_vazio():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/analisar",
            json={"texto": "   ", "opcoes": ["palavras"]},
        )
    assert response.status_code == 400


# ── Testes de integração com API externa (mockada) ────────────────────────────

def _make_mock_client(responses: list):
    """Cria um AsyncClient mockado que retorna respostas em sequência."""
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=responses)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


@pytest.mark.asyncio
async def test_buscar_definicao_sucesso_pt():
    """Testa integração com Wiktionary simulando resposta bem-sucedida em pt-BR."""
    # REST retorna 501, MediaWiki retorna wikitext com seção pt
    rest_404 = MagicMock()
    rest_404.status_code = 501

    mw_ok = MagicMock()
    mw_ok.status_code = 200
    mw_ok.json.return_value = {
        "query": {
            "pages": [{
                "revisions": [{
                    "slots": {
                        "main": {
                            "content": "={{-pt-}}=\n==Substantivo==\n# o fruto do abacateiro\n"
                        }
                    }
                }]
            }]
        }
    }

    mock_client = _make_mock_client([rest_404, mw_ok])
    with patch("app.main.httpx.AsyncClient", return_value=mock_client):
        resultado = await buscar_definicao("abacate")

    assert resultado is not None
    assert resultado["partOfSpeech"] == "substantivo"
    assert "abacateiro" in resultado["definicao"]
    assert resultado["fonte"] == "Wiktionary (pt)"


@pytest.mark.asyncio
async def test_buscar_definicao_fallback_ingles():
    """Testa fallback para Free Dictionary quando Wiktionary não tem seção pt."""
    rest_501 = MagicMock()
    rest_501.status_code = 501

    # MediaWiki retorna wikitext sem seção pt (ex: só azerbaijano)
    mw_sem_pt = MagicMock()
    mw_sem_pt.status_code = 200
    mw_sem_pt.json.return_value = {
        "query": {
            "pages": [{
                "revisions": [{
                    "slots": {"main": {"content": "={{-az-}}=\n==Substantivo==\n# número\n"}}
                }]
            }]
        }
    }

    # Free Dictionary retorna definição em inglês
    en_ok = MagicMock()
    en_ok.status_code = 200
    en_ok.json.return_value = [{
        "meanings": [{
            "partOfSpeech": "verb",
            "definitions": [{"definition": "To speak or utter words."}]
        }]
    }]

    mock_client = _make_mock_client([rest_501, mw_sem_pt, en_ok])
    with patch("app.main.httpx.AsyncClient", return_value=mock_client):
        resultado = await buscar_definicao("say")

    assert resultado is not None
    assert resultado["fonte"] == "Free Dictionary (en)"
    assert "speak" in resultado["definicao"]


@pytest.mark.asyncio
async def test_buscar_definicao_nao_encontrada():
    """Testa quando nenhuma API encontra a palavra."""
    resp_404 = MagicMock()
    resp_404.status_code = 404

    resp_501 = MagicMock()
    resp_501.status_code = 501

    mw_missing = MagicMock()
    mw_missing.status_code = 200
    mw_missing.json.return_value = {"query": {"pages": [{"missing": True}]}}

    mock_client = _make_mock_client([resp_501, mw_missing, resp_404])
    with patch("app.main.httpx.AsyncClient", return_value=mock_client):
        resultado = await buscar_definicao("xyzxyzxyz")

    assert resultado is None


@pytest.mark.asyncio
async def test_endpoint_definicao_via_api(monkeypatch):
    """Testa o endpoint /definicao/{palavra} com mock da chamada externa."""
    async def mock_buscar(palavra):
        return {
            "palavra": palavra,
            "partOfSpeech": "substantivo",
            "definicao": "Fruto tropical.",
            "fonte": "Wiktionary (pt)",
        }

    monkeypatch.setattr("app.main.buscar_definicao", mock_buscar)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/definicao/abacate")

    assert response.status_code == 200
    data = response.json()
    assert data["definicao"] == "Fruto tropical."
    assert data["fonte"] == "Wiktionary (pt)"
