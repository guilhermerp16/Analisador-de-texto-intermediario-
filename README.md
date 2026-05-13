# 🧾 Analisador de Texto

> 🔗 **Acesse a aplicação:** [[https://analisador-de-texto.onrender.com](https://analisador-de-texto-intermediario.onrender.com)]

---

## 📌 Descrição do problema

Muitas pessoas, como estudantes, escritores iniciantes e profissionais, têm dificuldade em analisar rapidamente a qualidade de um texto — quantidade de palavras, frequência de termos e estrutura básica. Isso pode prejudicar estudos, produção de conteúdo e organização de informações. 

## 💡 Proposta da solução

O Analisador de Texto é uma aplicação **web (GUI)** que permite analisar textos de forma rápida e prática, fornecendo métricas detalhadas e integração com o **Wiktionary pt-BR** para buscar definições das palavras analisadas em português e inglês.

## 👥 Público-alvo

* Estudantes
* Escritores
* Qualquer pessoa que trabalhe com texto

## ⚙️ Funcionalidades

* Contagem de caracteres
* Contagem de palavras
* Top 5 palavras mais usadas (com gráfico de barras)
* Estatísticas gerais (total de palavras e caracteres)
* Maior palavra do texto
* **🌐 Integração com API:** clique em qualquer palavra para ver sua definição — funciona com palavras em **português** e em **inglês**

## 🌐 Integração com API Pública

A aplicação consome duas APIs gratuitas e abertas, sem necessidade de chave:

**1. Wiktionary MediaWiki API (pt-BR) — fonte principal**
```
GET https://pt.wiktionary.org/w/api.php?action=query&titles={palavra}&prop=revisions...
```

**2. Free Dictionary API (inglês) — fallback**
```
GET https://api.dictionaryapi.dev/api/v2/entries/en/{palavra}
```

Ao clicar em qualquer palavra nos resultados, a aplicação tenta primeiro buscar a definição em português no Wiktionary. Se a palavra não tiver entrada em português (ex: palavras em inglês), cai automaticamente para a Free Dictionary API. O resultado é exibido com a fonte utilizada (🇧🇷 ou 🇺🇸).

## 🛠️ Tecnologias utilizadas

* Python 3.13
* **FastAPI** (backend / API REST)
* **Uvicorn** (servidor ASGI)
* **httpx** (requisições HTTP assíncronas)
* HTML/CSS/JS vanilla (frontend)
* GitHub Actions (CI)
* pytest + anyio (testes unitários e de integração)
* flake8 (linting)
* **Render** (deploy)

## 📦 Instalação local

```bash
git clone https://github.com/guilhermerp16/Bootcamp-II.git
cd Bootcamp-II/"Analisador de texto"
pip install -r requirements.txt
```

## ▶️ Execução local

```bash
uvicorn app.main:app --reload
```

Acesse [http://localhost:8000](http://localhost:8000) no navegador.

## 🧪 Executar testes

```bash
pytest --tb=short -v
```

## 📁 Estrutura do projeto

```
.
├── app/
│   ├── __init__.py
│   └── main.py          # Backend FastAPI + funções de análise + integração com APIs
├── static/
│   └── index.html       # Frontend (HTML/CSS/JS)
├── tests/
│   └── test_app.py      # Testes unitários e de integração
├── .github/
│   └── workflows/
│       └── ci.yml       # Pipeline CI
├── requirements.txt
├── pyproject.toml
└── render.yaml          # Configuração de deploy
```

## 🔢 Versão atual

v2.0.0

## 🧠 Como usar

1. Acesse o link da aplicação (ou rode localmente)
2. Selecione as análises desejadas clicando nos botões
3. Cole ou escreva seu texto
4. Clique em **Analisar →**
5. Clique em qualquer palavra nos resultados para ver sua definição

## 🧪 Testes automatizados

O projeto inclui:

- **Testes unitários** — validam funções isoladas (`limpar_texto`, `contar_palavras`, `maior_palavra`, etc.)
- **Testes de integração internos** — validam os endpoints da API FastAPI usando `httpx.AsyncClient`
- **Testes de integração externos (mockados)** — simulam respostas do Wiktionary e da Free Dictionary API com `unittest.mock`, cobrindo os cenários: definição encontrada em pt-BR, fallback para inglês, e palavra não encontrada em nenhuma fonte

## 👤 Autor

Guilherme Ribeiro
