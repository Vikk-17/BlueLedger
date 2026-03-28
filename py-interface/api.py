"""
FastAPI entry point for the BlueLedger Carbon Credit Pipeline.

Endpoints:
    GET  /health  — liveness check
    POST /run     — submit a GeoJSON geometry, run the pipeline, return results
"""

import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from carbon_credit_pipeline import CarbonCreditPipeline
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"

app = FastAPI(title="BlueLedger Carbon Credit API")
logger = logging.getLogger(__name__)


class RunRequest(BaseModel):
    UUID: str
    name: str
    geometry: Dict[
        str, Any
    ]  # GeoJSON geometry object: {"type": "Polygon", "coordinates": [...]}


# Endpoints


@app.get("/health")
async def health():
    """Liveness check."""
    return {"status": "ok"}


@app.post("/run")
async def run(request: RunRequest):
    """
    Accept a GeoJSON geometry, run the carbon credit pipeline, return results.
    The geometry is passed directly to the pipeline in memory —
    no intermediate file is written to disk.
    """
    logger.info(f"Received /run request — UUID: {request.UUID}, name: {request.name}")

    try:
        pipeline = CarbonCreditPipeline(config_path=str(BASE_DIR / "config.yaml"))
        results = await asyncio.to_thread(pipeline.run, request.geometry, request.UUID)

    except Exception as e:
        logger.error(f"Pipeline failed for UUID {request.UUID}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    # Persist an API-level log entry (default=str handles numpy types)
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = LOGS_DIR / f"api_run_{timestamp}.log"
    log_file.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")

    status_str = results["eligibility"]["status"]
    status_code = "True" if status_str.startswith("ELIGIBLE") else "False"

    return {
        "UUID": request.UUID,
        "name": request.name,
        "STATUS_CODE": status_code,
        "STATUS": status_str,
        "summary": {
            "NDVI_MEAN": results.get("ndvi_stats", {}).get("mean"),
            "NDWI_MEAN": results.get("ndwi_stats", {}).get("mean"),
            "TOTAL_AREA": results.get("carbon", {}).get("total_area_ha"),
            "TOTAL_CREDITS": results.get("carbon", {}).get("credits_issued"),
        },
    }


if __name__ == "__main__":
    import uvicorn

    print("Starting BlueLedger API on http://0.0.0.0:8000")
    print("Interactive docs: http://0.0.0.0:8000/docs")
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=False)
