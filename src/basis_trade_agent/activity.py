import json
import os
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_SHARED_RUNTIME_DIR = Path("landing-page")


def get_shared_runtime_dir() -> Path:
    return Path(os.environ.get("BASIS_TRADE_SHARED_DIR", str(DEFAULT_SHARED_RUNTIME_DIR)))


def get_shared_activity_log_path() -> Path:
    return get_shared_runtime_dir() / "activity.log"


def get_shared_activity_json_path() -> Path:
    return get_shared_runtime_dir() / ".agent_activity.json"


def get_activity_path(configPath: Path) -> Path:
    return configPath.parent / ".agent_activity.json"


def get_tx_explorer_url(chainId: int, txHash: str) -> str:
    if chainId == 42161:
        return f"https://arbiscan.io/tx/{txHash}"
    return txHash


def read_activity(activityPath: Path) -> dict:
    if not activityPath.exists():
        return {"events": []}
    return json.loads(activityPath.read_text())


def write_activity(activityPath: Path, activity: dict) -> None:
    activityPath.parent.mkdir(parents=True, exist_ok=True)
    activityPath.write_text(json.dumps(activity, indent=2) + "\n")


def append_activity_event(activityPath: Path, event: dict) -> None:
    activity = read_activity(activityPath)
    events = activity.get("events", [])
    events.append({"timestamp": datetime.now(timezone.utc).isoformat(), **event})
    activity["events"] = events[-20:]
    write_activity(activityPath, activity)
    write_activity(get_shared_activity_json_path(), activity)
