from fastapi import FastAPI
from pydantic import BaseModel
from engine import SentinelRAGEngine
from privacy import anonymize_text
import datetime
import json

app = FastAPI(title="SentinelRAG Compliance API")

engine = SentinelRAGEngine()


class QueryRequest(BaseModel):
    query: str


def log_decision(query, result):
    redacted_query = anonymize_text(query)
    log_entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "query": redacted_query,
        "result": result
    }

    with open("audit_log.jsonl", "a") as f:
        f.write(json.dumps(log_entry) + "\n")


@app.post("/screen")
def screen_entity(request: QueryRequest):
    result = engine.screen(request.query)
    log_decision(request.query, result)
    return result

class BatchRequest(BaseModel):
    queries: list[str]


@app.post("/batch_screen")
def batch_screen(request: BatchRequest):
    results = []

    for q in request.queries:
        result = engine.screen(q)
        log_decision(q, result)
        results.append(result)

    return {"results": results}