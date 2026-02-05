# BlueLedger API Documentation

Flask-based REST API for the Carbon Credit Pipeline.

**Base URL:** `http://localhost:8000`

---

## Endpoints

### 1. Health Check

**`GET /health`**

Returns the API status.

**Response:**
```json
{"status": "ok"}
```

---

### 2. Run Pipeline

**`POST /run`**

Submit a GeoJSON area of interest and execute the carbon credit analysis pipeline.

#### Request

**Headers:**
```
Content-Type: application/json
```

**Body:** Valid GeoJSON object with a `type` field.

**Example:**
```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Polygon",
        "coordinates": [[[88.3, 22.5], [88.4, 22.5], [88.4, 22.6], [88.3, 22.6], [88.3, 22.5]]]
      },
      "properties": {}
    }
  ]
}
```

#### Response

| Field | Type | Description |
|-------|------|-------------|
| `success` | boolean | Whether the pipeline completed without errors |
| `exit_code` | integer | Process exit code (0 = success) |
| `files.log_file` | string | Path to execution log |
| `files.carbon_credit_report` | string | Path to generated report |
| `files.summary_json` | string | Path to summary JSON |
| `summary` | object | Extracted metrics (see below) |

**Summary Object:**

| Field | Type | Description |
|-------|------|-------------|
| `NDVI_MEAN` | float | Normalized Difference Vegetation Index mean |
| `NDWI_MEAN` | float | Normalized Difference Water Index mean |
| `TOTAL_AREA` | float | Area in hectares |
| `TOTAL_CREDITS` | integer | Carbon credits issued |
| `STATUS` | string | Eligibility status |
| `TIME_PERIOD` | array | Analysis time period |

**Example Response:**
```json
{
  "success": true,
  "exit_code": 0,
  "files": {
    "log_file": "/path/to/logs/api_run_20260205_120000.log",
    "carbon_credit_report": "/path/to/outputs/carbon_credit_report.txt",
    "summary_json": "/path/to/outputs/summary.json"
  },
  "summary": {
    "NDVI_MEAN": 0.306,
    "NDWI_MEAN": -0.345,
    "TOTAL_AREA": 3003.95,
    "TOTAL_CREDITS": 4576,
    "STATUS": "ELIGIBLE",
    "TIME_PERIOD": [["2026-01-01", "2026-01-15"], ["2026-01-16", "2026-01-31"]]
  }
}
```

#### Error Responses

**400 Bad Request** - Invalid GeoJSON:
```json
{"error": "Invalid GeoJSON: must have 'type' field"}
```

**400 Bad Request** - Invalid JSON:
```json
{"error": "Invalid JSON: <error details>"}
```

---

## Quick Start

**Start the server:**
```bash
python3 api.py
```

**Test health:**
```bash
curl http://localhost:8000/health
```

**Run pipeline:**
```bash
curl -X POST http://localhost:8000/run \
  -H "Content-Type: application/json" \
  -d @aoi.geojson
```

---

## Output Files

| File | Location | Description |
|------|----------|-------------|
| `api_run_*.log` | `logs/` | Execution logs with timestamps |
| `carbon_credit_report.txt` | `outputs/` | Full analysis report |
| `summary.json` | `outputs/` | Summary metrics in JSON |
