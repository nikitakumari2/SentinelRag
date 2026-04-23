# SentinelRAG

**Hybrid Symbolic-Neural Compliance Screening Engine**

SentinelRAG screens business entities, people, aliases, and identifiers against the OFAC Specially Designated Nationals (SDN) list. It combines graph lookup, lexical retrieval, semantic retrieval, and deterministic decision logic with local-first execution.

---

## Table of Contents

- [Overview](#overview)
- [How It Works](#how-it-works)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Run the System](#run-the-system)
- [Keep SDN Data Updated](#keep-sdn-data-updated)
- [Evaluation and Benchmarking](#evaluation-and-benchmarking)
- [PII Handling Mode (Presidio)](#pii-handling-mode-presidio)
- [API Response Shape](#api-response-shape)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Disclaimer](#disclaimer)

---

## Overview

SentinelRAG builds and uses three complementary indexes:

- **Knowledge Graph (`networkx`)** for exact alias and identifier jumps.
- **BM25 (`rank-bm25`)** for lexical/token overlap matching.
- **Vector search (`Chroma` + MiniLM embeddings)** for semantic name similarity.

When model downloads are blocked by network/proxy policy, the engine degrades gracefully:

- Vector retrieval can fall back to BM25-only mode.
- Cross-encoder reranking can be skipped.
- Screening still returns deterministic `MATCH` / `NO_MATCH` responses.

---

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

### Typical latency per stage

| Stage | Approximate time | Notes |
|---|---|---|
| Knowledge graph lookup | ~0.04ms | O(1) dict lookup — always runs first |
| Hybrid retrieval | ~30ms | Vector + BM25 combined |
| Quick fuzzy pre-check | ~1ms | Skips cross-encoder if score ≥ 92 |
| Cross-encoder rerank | ~60ms | Only runs for ambiguous queries |
| Deterministic decision | ~1ms | Rule-based, no model inference |
| **Total (graph hit)** | **~0.1ms** | Fast path |
| **Total (full pipeline)** | **~90ms** | Worst case |

The pipeline short-circuits at the earliest confident stage — most real-world queries resolve via graph lookup or the fuzzy pre-check and never reach the cross-encoder.

---

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
├── privacy.py
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
## Pipeline
<img width="1322" height="1438" alt="image" src="https://github.com/user-attachments/assets/4dc6ea9c-02de-4b1d-b51d-441e03314ecf" />

---

## Prerequisites

- Python 3.10+ (3.11 recommended)
- `pip` and virtual environment support
- Internet access for first-time model downloads (optional but recommended)

If model downloads are blocked, SentinelRAG still runs in deterministic fallback mode using graph + BM25 logic.

## Quick Start

### 1) Clone and install

```bash
git clone https://github.com/nikitakumari2/SentinelRag.git
cd SentinelRag
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Optional (for cleaner dependency isolation):

```bash
pip install --upgrade pip
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

---

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

Example response:

```json
{
  "decision": "MATCH",
  "entity_number": "306",
  "confidence": 1.0,
  "reason": "Graph alias/entity lookup match.",
  "latency": {
    "graph_lookup_ms": 0.04,
    "total_ms": 0.12
  }
}
```

### CLI Retriever

```bash
python retriever.py
```

---

## Keep SDN Data Updated

Run:

```bash
python update_sdn.py
```

`update_sdn.py` behavior:

- Downloads latest SDN CSV from OFAC.
- Compares MD5 hash with existing `data/sdn.csv`.
- Backs up previous file into `data/backups/` with a timestamp.
- Rebuilds all indexes only when content has changed.
- If download fails but local `data/sdn.csv` exists, skips rebuild safely.

Optional proxy bypass for restricted environments:

```bash
SDN_BYPASS_PROXY=1 python update_sdn.py
```

Example cron (daily 2am):

```bash
0 2 * * * cd /path/to/SentinelRag && /path/to/SentinelRag/.venv/bin/python update_sdn.py >> logs/sdn_update.log 2>&1
```

### GitHub Actions — automated daily update

Create `.github/workflows/update_sdn.yml`:

```yaml
name: Update SDN List

on:
  schedule:
    - cron: '0 2 * * *'
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: python update_sdn.py
      - name: Commit if changed
        run: |
          git config user.name "github-actions"
          git config user.email "actions@github.com"
          git add bm25_corpus.json knowledge_graph.pkl
          git diff --staged --quiet || git commit -m "Auto-update SDN $(date +%Y-%m-%d)" && git push
```

---

## Evaluation and Benchmarking

```bash
# Run accuracy evaluation against the auto-generated test suite
python evaluate.py

# Measure average latency across repeated queries
python benchmark.py

# Regenerate the auto test dataset from current SDN data
python generate_auto_tests.py
```

### Sample evaluation output

```
MISSED CASE: MIKHAILIUK, Leoni  Expected: MATCH  Predicted: NO_MATCH

=== Evaluation Report ===
Total Samples:    80
Accuracy:         0.96
Precision:        0.97
Recall:           0.95
False Positives:  1
False Negatives:  2
```

### Sample benchmark output

```
Total queries: 100
Total time:    8.43s
Average latency: 0.0843s
```

The auto test suite (`evaluation_data_auto.json`) is generated by `generate_auto_tests.py`. It samples 20 random entities from the SDN list and creates three query variants per entity (exact, lowercase, one character truncated) plus 20 random noise strings for negative examples — 80 test cases total.

> **Note:** `evaluate.py` currently uses `retriever.py` directly rather than `engine.py`, so results do not reflect the adaptive short-circuit logic. Scores are therefore slightly conservative relative to real-world performance.

---

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

If `ENABLE_PII_REDACTION` is false/unset, text is passed through unchanged. The default lightweight mode avoids downloading large NLP models; for this reason, default entities focus on regex-based types such as phone and email.

## API Response Shape

Typical `POST /screen` response:

```json
{
  "query": "Banco Nacional de Cuba",
  "decision": "MATCH",
  "entity_number": "12345",
  "confidence": 0.98,
  "reason": "High fuzzy similarity with strong retrieval agreement",
  "latency": {
    "total_ms": 52.1
  }
}
```

Notes:

- `decision` is always deterministic (`MATCH` or `NO_MATCH`).
- `entity_number` may be `null` when no high-confidence match is found.
- `latency` contains per-step timing details when available.

## Configuration

Key constants you can tune — all currently defined in `engine.py` and `retriever.py`:

| Constant | Default | File | Effect |
|---|---|---|---|
| `FUZZY_MATCH_THRESHOLD` | `85` | `engine.py`, `retriever.py` | Minimum fuzzy score (0–100) to count as a match. Lower = more matches, higher false-positive risk. |
| Quick pre-check threshold | `92` | `engine.py` line 187 | Score above which cross-encoder is skipped entirely. Raise to force more reranking; lower for speed. |
| `k` in `hybrid_retrieve()` | `5` | `engine.py` line 65 | Candidates fetched from each retrieval method. Higher = better recall, slower retrieval. |

---

## Troubleshooting

- **`data/sdn.csv` missing**: run `python update_sdn.py` or download manually, then run `python ingesting.py`.
- **`vector_db`/index artifacts missing**: run `python ingesting.py` to regenerate all retrieval assets.
- **Model download failures**: verify network/proxy settings; fallback mode still allows deterministic screening.
- **Slow startup on first run**: expected while embedding/rerank models cache locally.
- **Streamlit watcher warnings**: run with `--server.fileWatcherType none`.

## Roadmap

- Align `evaluate.py` with full `engine.py` adaptive flow.
- Add Docker packaging.
- Add async batch screening path for API.
- Tune fuzzy threshold separately for person names vs company names.
- Include aliases in cross-encoder scoring pairs (not just primary name).
- Extend support to additional sanctions datasets (EU, UN, HMT).

---

## Disclaimer

SentinelRAG is a research/development tool and not legal advice or a certified compliance platform. Always involve qualified legal and compliance teams for production regulatory decisions.
