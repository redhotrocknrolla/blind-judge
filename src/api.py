#!/usr/bin/env python3
"""
Blind Judge — FastAPI Server
POST /audit  — принимает input.json, возвращает final_verdict.json
GET  /health — проверка живости
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any

from config import load_config
from judge import audit

app = FastAPI(
    title="Blind Judge",
    description="Гибридный аудитор для мультиагентных систем.",
    version="1.0.0"
)

config = load_config()


class AuditRequest(BaseModel):
    schema_version: str
    request_id: str
    task: str
    inputs: list
    conclusion: str
    actions: list
    domain_hint: Any = None


@app.get("/health")
def health():
    return {"status": "ok", "version": "1.0.0"}


@app.post("/audit")
def audit_endpoint(request: AuditRequest):
    try:
        input_data = request.model_dump()
        result = audit(input_data, config)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
