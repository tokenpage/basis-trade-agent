from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse

from basis_trade_agent.activity import get_shared_activity_json_path, get_shared_activity_log_path, read_activity

app = FastAPI(title="Basis Trade Agent API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:3000",
        "http://127.0.0.1:4173",
        "http://localhost:3000",
        "http://localhost:4173",
        "https://bta.yieldseeker.xyz",
    ],
    allow_origin_regex=r"https://.*\.?(yieldseeker.xyz)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
def healthz() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/activity.log")
def get_activity_log() -> PlainTextResponse:
    activityLogPath = get_shared_activity_log_path()
    if not activityLogPath.exists():
        raise HTTPException(status_code=404, detail=f"Activity log not found at {activityLogPath}")
    return PlainTextResponse(activityLogPath.read_text())


@app.get("/activity.json")
def get_activity_json() -> JSONResponse:
    activityJsonPath = get_shared_activity_json_path()
    if not activityJsonPath.exists():
        return JSONResponse({"events": []})
    return JSONResponse(read_activity(Path(activityJsonPath)))
