# utils/storage.py
import json
import os
from typing import Any, Dict, Optional

DATA_DIR = "data"
TASKS_FILE = os.path.join(DATA_DIR, "tasks.json")
CONFIG_FILE = os.path.join(DATA_DIR, "server_config.json")

os.makedirs(DATA_DIR, exist_ok=True)


def _load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def _save_json(path: str, data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---- Server config (per guild) ----

def get_server_config(guild_id: int) -> Dict[str, Any]:
    data = _load_json(CONFIG_FILE)
    return data.get(str(guild_id), {})


def set_server_config(guild_id: int, new_config: Dict[str, Any]) -> None:
    data = _load_json(CONFIG_FILE)
    data[str(guild_id)] = new_config
    _save_json(CONFIG_FILE, data)


def update_server_config(guild_id: int, **kwargs) -> Dict[str, Any]:
    cfg = get_server_config(guild_id)
    cfg.update(kwargs)
    set_server_config(guild_id, cfg)
    return cfg


# ---- Task storage ----
# tasks stored per guild, with incremental integer IDs

def get_all_tasks() -> Dict[str, Any]:
    return _load_json(TASKS_FILE)


def set_all_tasks(data: Dict[str, Any]) -> None:
    _save_json(TASKS_FILE, data)


def get_guild_tasks(guild_id: int) -> Dict[str, Any]:
    data = get_all_tasks()
    return data.get(str(guild_id), {"counter": 0, "tasks": {}})


def save_guild_tasks(guild_id: int, guild_data: Dict[str, Any]) -> None:
    data = get_all_tasks()
    data[str(guild_id)] = guild_data
    set_all_tasks(data)


def create_task(
    guild_id: int,
    creator_id: int,
    title: str,
    description: str,
    priority: str,
    message_id: Optional[int] = None,
    channel_id: Optional[int] = None,
    thread_id: Optional[int] = None,
) -> Dict[str, Any]:
    guild_data = get_guild_tasks(guild_id)
    counter = guild_data.get("counter", 0) + 1
    guild_data["counter"] = counter

    task_id = counter
    task = {
        "id": task_id,
        "title": title,
        "description": description,
        "priority": priority,
        "status": "Open",
        "creator_id": creator_id,
        "assignee_id": None,
        "message_id": message_id,
        "channel_id": channel_id,
        "thread_id": thread_id,
    }

    guild_data.setdefault("tasks", {})
    guild_data["tasks"][str(task_id)] = task
    save_guild_tasks(guild_id, guild_data)
    return task


def update_task(guild_id: int, task_id: int, **kwargs) -> Optional[Dict[str, Any]]:
    guild_data = get_guild_tasks(guild_id)
    tasks = guild_data.get("tasks", {})
    t = tasks.get(str(task_id))
    if not t:
        return None
    t.update(kwargs)
    tasks[str(task_id)] = t
    guild_data["tasks"] = tasks
    save_guild_tasks(guild_id, guild_data)
    return t


def get_task(guild_id: int, task_id: int) -> Optional[Dict[str, Any]]:
    guild_data = get_guild_tasks(guild_id)
    return guild_data.get("tasks", {}).get(str(task_id))


def list_tasks(guild_id: int) -> Dict[str, Any]:
    guild_data = get_guild_tasks(guild_id)
    return guild_data.get("tasks", {})
