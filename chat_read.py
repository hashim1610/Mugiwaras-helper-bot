# chat_read.py
import os
from datetime import date
from typing import Optional

import discord
import yaml

# Path to config file (override with CONFIG_PATH env if needed)
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yml")


def _load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
            print(f"[chat_read] Loaded config from {CONFIG_PATH}")
    except Exception as e:
        print(f"⚠ [chat_read] Failed to load config.yml from {CONFIG_PATH}: {e}")
        cfg = {}

    discord_cfg = cfg.get("discord", {}) or {}
    return {
        "camp_log_channel_id": int(discord_cfg.get("camp_log_channel_id", 0)),
        "ranch_log_channel_id": int(discord_cfg.get("ranch_log_channel_id", 0)),
        "log_channel_id": int(discord_cfg.get("log_channel_id", 0)),
        "command_channel_id": int(discord_cfg.get("command_channel_id", 0)),
    }


_CFG = _load_config()

CAMP_LOG_CHANNEL_ID = _CFG["camp_log_channel_id"] or _CFG["log_channel_id"]
RANCH_LOG_CHANNEL_ID = _CFG["ranch_log_channel_id"]
COMMAND_CHANNEL_ID = _CFG["command_channel_id"]


async def _get_channel(bot: discord.Client, channel_id: int) -> Optional[discord.abc.Messageable]:
    """
    Generic helper: fetch any text-like channel by ID.
    """
    if not channel_id:
        print("⚠ [chat_read] Channel ID is 0 or not set.")
        return None

    ch = bot.get_channel(channel_id)
    if ch is None:
        try:
            ch = await bot.fetch_channel(channel_id)
        except Exception as e:
            print(f"❌ [chat_read] Failed to fetch channel {channel_id}: {e}")
            return None

    print(f"[chat_read] Using channel {channel_id} ({type(ch)})")
    return ch


async def build_raw_log_from_channel(
    bot: discord.Client,
    channel_id: int,
    start_date: Optional[date],
    end_date: Optional[date],
) -> str:
    """
    Read messages from the given channel and return a single big text blob.

    Includes for each message:
      - a date marker line: __DATE__ DD-MM-YYYY
      - message content
      - embed titles/descriptions/fields
      - text/log attachments (.txt, .log)
    """
    print(
        f"[chat_read] build_raw_log_from_channel(channel_id={channel_id}, "
        f"start_date={start_date}, end_date={end_date})"
    )

    channel = await _get_channel(bot, channel_id)
    if not channel:
        print(f"⚠ [chat_read] No channel available (ID={channel_id}). Returning empty log.")
        return ""

    msgs = []
    total_msgs = 0

    async for m in channel.history(limit=5000, oldest_first=True):
        total_msgs += 1
        md = m.created_at.date()

        if start_date and md < start_date:
            continue
        if end_date and md > end_date:
            continue

        parts = []

        # DATE MARKER — always DD-MM-YYYY
        parts.append("__DATE__ %s" % md.strftime("%d-%m-%Y"))

        if m.content:
            parts.append(m.content)

        for e in m.embeds:
            if e.title:
                parts.append(e.title)
            if e.description:
                parts.append(e.description)
            for f in e.fields:
                parts.append(f"{f.name}: {f.value}")

        for att in m.attachments:
            fn = att.filename.lower()
            if fn.endswith(".txt") or fn.endswith(".log"):
                try:
                    data = await att.read()
                    parts.append(data.decode("utf-8"))
                except Exception as e:
                    print("⚠ [chat_read] Failed to read attachment %s: %s" % (fn, e))

        if parts:
            msgs.append("\n".join(parts))

    raw_log = "\n".join(msgs)
    print(
        f"[chat_read] Done. Total messages scanned: {total_msgs}, "
        f"messages in range: {len(msgs)}, raw_log length: {len(raw_log)}"
    )

    # Optional: print first few lines for debug
    raw_lines = raw_log.splitlines()
    for idx, ln in enumerate(raw_lines[:20]):
        print(f"[chat_read] raw_log[{idx}]: {ln}")

    return raw_log


async def build_camp_raw_log(
    bot: discord.Client,
    start_date: Optional[date],
    end_date: Optional[date],
) -> str:
    print("[chat_read] build_camp_raw_log called")
    return await build_raw_log_from_channel(bot, CAMP_LOG_CHANNEL_ID, start_date, end_date)


async def build_ranch_raw_log(
    bot: discord.Client,
    start_date: Optional[date],
    end_date: Optional[date],
) -> str:
    print("[chat_read] build_ranch_raw_log called")
    return await build_raw_log_from_channel(bot, RANCH_LOG_CHANNEL_ID, start_date, end_date)
