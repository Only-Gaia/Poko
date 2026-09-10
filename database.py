"""
database.py
Very small JSON-file "database" used to persist everything the bot needs:
per-guild config, per-user economy/level/warns data, custom messages, etc.

This keeps the project dependency-free (no external database needed) while
still surviving bot restarts. Good enough for small/medium servers - swap
this module out for SQLite/PostgreSQL later if you outgrow it.
"""

import json
import os
import threading
import time
from typing import Any, Dict

import config

_lock = threading.Lock()

_DEFAULT_GUILD = {
    "config": {
        "welcome_channel": None,
        "welcome_message": "Welcome {mention} to **{guild}**! 🎉",
        "goodbye_channel": None,
        "goodbye_message": "**{user}** left the server. 👋",
        "verified_role": None,
        "unverified_role": None,
        "log_channel": None,
        "locked_channels": [],
    },
    "staff": [],              # list of user IDs granted "pex" (bot staff perms)
    "users": {},              # user_id (str) -> user data dict
    "custom_messages": {},    # name -> content (managed by SPECIAL_USER_ID)
}

_DEFAULT_USER = {
    "pokash": 0,
    "luck": 0,
    "xp": 0,
    "level": 0,
    "last_xp": 0,
    "warns": [],             # list of {"reason": str, "moderator": id, "time": ts}
    "inventory": {},         # item_name -> quantity
    "married_to": None,      # user_id (str) or None
    "married_since": None,   # timestamp
}


def _ensure_dir():
    os.makedirs(config.DATA_DIR, exist_ok=True)


def _load() -> Dict[str, Any]:
    _ensure_dir()
    if not os.path.exists(config.DB_PATH):
        return {"guilds": {}}
    try:
        with open(config.DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {"guilds": {}}


def _save(data: Dict[str, Any]):
    _ensure_dir()
    tmp_path = config.DB_PATH + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp_path, config.DB_PATH)


def _guild(data: Dict[str, Any], guild_id: int) -> Dict[str, Any]:
    gid = str(guild_id)
    if gid not in data["guilds"]:
        data["guilds"][gid] = json.loads(json.dumps(_DEFAULT_GUILD))
    # backfill any keys added after a guild was first created
    for key, value in _DEFAULT_GUILD.items():
        data["guilds"][gid].setdefault(key, json.loads(json.dumps(value)))
    return data["guilds"][gid]


def _user(guild_data: Dict[str, Any], user_id: int) -> Dict[str, Any]:
    uid = str(user_id)
    if uid not in guild_data["users"]:
        guild_data["users"][uid] = json.loads(json.dumps(_DEFAULT_USER))
    for key, value in _DEFAULT_USER.items():
        guild_data["users"][uid].setdefault(key, json.loads(json.dumps(value)))
    return guild_data["users"][uid]


class DB:
    """Thin convenience wrapper around the JSON file, guarded by a lock."""

    # ---------- generic ----------
    @staticmethod
    def guild_config(guild_id: int) -> Dict[str, Any]:
        with _lock:
            data = _load()
            return dict(_guild(data, guild_id)["config"])

    @staticmethod
    def set_guild_config(guild_id: int, **kwargs):
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            g["config"].update(kwargs)
            _save(data)

    @staticmethod
    def user(guild_id: int, user_id: int) -> Dict[str, Any]:
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            return dict(_user(g, user_id))

    @staticmethod
    def update_user(guild_id: int, user_id: int, **kwargs):
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            u = _user(g, user_id)
            u.update(kwargs)
            _save(data)
            return dict(u)

    # ---------- economy ----------
    @staticmethod
    def add_pokash(guild_id: int, user_id: int, amount: int) -> int:
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            u = _user(g, user_id)
            u["pokash"] = max(0, u["pokash"] + amount)
            _save(data)
            return u["pokash"]

    @staticmethod
    def set_pokash(guild_id: int, user_id: int, amount: int) -> int:
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            u = _user(g, user_id)
            u["pokash"] = max(0, amount)
            _save(data)
            return u["pokash"]

    @staticmethod
    def add_luck(guild_id: int, user_id: int, amount: int) -> int:
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            u = _user(g, user_id)
            u["luck"] = max(0, min(config.MAX_LUCK, u["luck"] + amount))
            _save(data)
            return u["luck"]

    @staticmethod
    def add_inventory_item(guild_id: int, user_id: int, item: str, qty: int = 1):
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            u = _user(g, user_id)
            u["inventory"][item] = u["inventory"].get(item, 0) + qty
            if u["inventory"][item] <= 0:
                del u["inventory"][item]
            _save(data)
            return dict(u["inventory"])

    # ---------- warns ----------
    @staticmethod
    def add_warn(guild_id: int, user_id: int, reason: str, moderator_id: int):
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            u = _user(g, user_id)
            u["warns"].append({
                "reason": reason,
                "moderator": moderator_id,
                "time": int(time.time()),
            })
            _save(data)
            return len(u["warns"])

    @staticmethod
    def remove_warn(guild_id: int, user_id: int, index: int) -> bool:
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            u = _user(g, user_id)
            if 0 <= index < len(u["warns"]):
                u["warns"].pop(index)
                _save(data)
                return True
            return False

    @staticmethod
    def get_warns(guild_id: int, user_id: int):
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            return list(_user(g, user_id)["warns"])

    # ---------- staff / pex ----------
    @staticmethod
    def add_staff(guild_id: int, user_id: int):
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            if user_id not in g["staff"]:
                g["staff"].append(user_id)
                _save(data)

    @staticmethod
    def remove_staff(guild_id: int, user_id: int):
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            if user_id in g["staff"]:
                g["staff"].remove(user_id)
                _save(data)

    @staticmethod
    def is_staff(guild_id: int, user_id: int) -> bool:
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            return user_id in g["staff"]

    # ---------- custom messages ----------
    @staticmethod
    def set_custom_message(guild_id: int, name: str, content: str):
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            g["custom_messages"][name.lower()] = content
            _save(data)

    @staticmethod
    def remove_custom_message(guild_id: int, name: str) -> bool:
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            if name.lower() in g["custom_messages"]:
                del g["custom_messages"][name.lower()]
                _save(data)
                return True
            return False

    @staticmethod
    def get_custom_message(guild_id: int, name: str):
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            return g["custom_messages"].get(name.lower())

    @staticmethod
    def list_custom_messages(guild_id: int):
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            return list(g["custom_messages"].keys())

    # ---------- locked channels ----------
    @staticmethod
    def set_locked(guild_id: int, channel_id: int, locked: bool):
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            locked_channels = set(g["config"].get("locked_channels", []))
            if locked:
                locked_channels.add(channel_id)
            else:
                locked_channels.discard(channel_id)
            g["config"]["locked_channels"] = list(locked_channels)
            _save(data)

    # ---------- leaderboard (world-wide, across every guild) ----------
    @staticmethod
    def global_level_leaderboard(limit: int = 10):
        with _lock:
            data = _load()
            rows = []
            for gid, gdata in data["guilds"].items():
                for uid, udata in gdata["users"].items():
                    rows.append((int(uid), int(gid), udata.get("level", 0), udata.get("xp", 0)))
            rows.sort(key=lambda r: (r[2], r[3]), reverse=True)
            # keep only the best entry per user across guilds
            seen = set()
            result = []
            for user_id, guild_id, level, xp in rows:
                if user_id in seen:
                    continue
                seen.add(user_id)
                result.append((user_id, guild_id, level, xp))
                if len(result) >= limit:
                    break
            return result

    # ---------- xp / level ----------
    @staticmethod
    def add_xp(guild_id: int, user_id: int, amount: int):
        with _lock:
            data = _load()
            g = _guild(data, guild_id)
            u = _user(g, user_id)
            u["xp"] += amount
            leveled_up = False
            while u["xp"] >= config.xp_needed_for_level(u["level"]):
                u["xp"] -= config.xp_needed_for_level(u["level"])
                u["level"] += 1
                u["pokash"] += config.POKASH_PER_LEVEL
                leveled_up = True
            u["last_xp"] = int(time.time())
            _save(data)
            return leveled_up, u["level"], u["pokash"]
