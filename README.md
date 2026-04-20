# SentinelRAG

**Hybrid Symbolic-Neural Compliance Screening Engine**

SentinelRAG screens business entities, people, aliases, and identifiers against the OFAC Specially Designated Nationals (SDN) list. It combines graph lookup, lexical retrieval, semantic retrieval, and deterministic decision logic with local-first execution.

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Run the System](#run-the-system)
- [Keep SDN Data Updated](#keep-sdn-data-updated)
- [Evaluation and Benchmarking](#evaluation-and-benchmarking)
- [PII Handling Mode (Presidio)](#pii-handling-mode-presidio)
- [Configuration Notes](#configuration-notes)
- [Roadmap](#roadmap)
- [Disclaimer](#disclaimer)

## Overview

SentinelRAG builds and uses three complementary indexes:

- **Knowledge Graph (`networkx`)** for exact alias and identifier jumps.
- **BM25 (`rank-bm25`)** for lexical/token overlap matching.
- **Vector search (`Chroma` + MiniLM embeddings)** for semantic name similarity.

When model downloads are blocked by network/proxy policy, the engine degrades gracefully:

- vector retrieval can fall back to BM25-only mode
- cross-encoder reranking can be skipped
- screening still returns deterministic `MATCH` / `NO_MATCH` responses

## How It Works

1. **Graph lookup** tries exact node hits first (entity, alias, ID).
2. **Hybrid retrieval** combines vector and BM25 candidates (deduplicated).
3. **Quick fuzzy pre-check** can skip reranking for high-confidence matches.
4. **Cross-encoder rerank** (`cross-encoder/ms-marco-MiniLM-L6-v2`) reorders ambiguous candidates.
5. **Deterministic decision** applies exact/fuzzy rules and returns confidence, reason, and latency breakdown.

Output includes:

- `decision` (`MATCH` or `NO_MATCH`)
- `entity_number`
- `confidence`
- `reason`
- `latency` metrics

## Project Structure

```text
SentinelRag/
├── api.py
├── app_ui.py
├── benchmark.py
├── bm25_corpus.json
├── check_data.py
├── data/
│   ├── sdn.csv
│   └── backups/
├── engine.py
├── evaluate.py
├── evaluation_data.json
├── evaluation_data_auto.json
├── generate_auto_tests.py
├── generator.py
├── ingesting.py
├── knowledge_graph.pkl
├── requirements.txt
├── retriever.py
├── test_engine.py
├── update_sdn.py
└── vector_db/
```

## Quick Start

### 1) Clone and install

```bash
git clone https://github.com/nikitakumari2/SentinelRag.git
cd SentinelRag
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Prepare SDN data

If `data/sdn.csv` is missing, download it:

```bash
mkdir -p data
curl -L "https://www.treasury.gov/ofac/downloads/sdn.csv" -o data/sdn.csv
```

### 3) Build indexes (one-time or after SDN refresh)

```bash
python ingesting.py
```

This builds:

- `vector_db/`
- `bm25_corpus.json`
- `knowledge_graph.pkl`

### 4) Smoke test

```bash
python test_engine.py
```

## Run the System

### Streamlit UI (recommended)

```bash
streamlit run app_ui.py
```

Open `http://localhost:8501`.

If file-watcher noise appears on some environments:

```bash
streamlit run app_ui.py --server.fileWatcherType none
```

### FastAPI

```bash
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Single request:

```bash
curl -X POST "http://localhost:8000/screen" \
  -H "Content-Type: application/json" \
  -d '{"query":"Banco Nacional de Cuba"}'
```

Batch request:

```bash
curl -X POST "http://localhost:8000/batch_screen" \
  -H "Content-Type: application/json" \
  -d '{"queries":["BNC","Random Company"]}'
```

### CLI Retriever

```bash
python retriever.py
```

## Keep SDN Data Updated

Run:

```bash
python update_sdn.py
```

`update_sdn.py` behavior:

- downloads latest SDN CSV
- compares MD5 hash with existing `data/sdn.csv`
- backs up previous file into `data/backups/`
- rebuilds indexes only when content changed
- if download fails but local `data/sdn.csv` exists, skips rebuild safely

Optional proxy bypass for restricted environments:

```bash
SDN_BYPASS_PROXY=1 python update_sdn.py
```

Example cron (daily 2am):

```bash
0 2 * * * cd /path/to/SentinelRag && /path/to/SentinelRag/.venv/bin/python update_sdn.py >> logs/sdn_update.log 2>&1
```

## Evaluation and Benchmarking

```bash
python evaluate.py
python benchmark.py
python generate_auto_tests.py
```

## PII Handling Mode (Presidio)

SentinelRAG includes optional PII redaction utilities via Microsoft Presidio.

Current integration points:

- API audit logging redacts the stored query before writing `audit_log.jsonl`.
- Streamlit bulk section includes an optional checkbox to redact query text in displayed/exported CSV output.

By default, redaction is disabled. Enable with environment variables:

```bash
export ENABLE_PII_REDACTION=true
export PII_ENTITIES=PHONE_NUMBER,EMAIL_ADDRESS,PERSON
```

If `ENABLE_PII_REDACTION` is false/unset, text is passed through unchanged.
The default lightweight mode avoids downloading large NLP models; for this reason, default entities focus on regex-based types such as phone and email.

## Configuration Notes

Useful tuning points:

- `FUZZY_MATCH_THRESHOLD` in `engine.py`
- quick-similarity shortcut threshold in `engine.py`
- `k` candidate count in `hybrid_retrieve()`

## Roadmap

- Align `evaluate.py` with full `engine.py` adaptive flow.
- Add Docker packaging.
- Add async batch screening path for API.
- Extend support to additional sanctions datasets.

## Disclaimer

SentinelRAG is a research/development tool and not legal advice or a certified compliance platform. Always involve qualified legal and compliance teams for production regulatory decisions.
