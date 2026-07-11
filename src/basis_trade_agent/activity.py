import json
from datetime import datetime, timezone
from pathlib import Path


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


def append_activity_event(activityPath: Path, event: dict) -> None:
    activity = read_activity(activityPath)
    events = activity.get("events", [])
    events.append({"timestamp": datetime.now(timezone.utc).isoformat(), **event})
    activity["events"] = events[-20:]
    activityPath.write_text(json.dumps(activity, indent=2) + "\n")
