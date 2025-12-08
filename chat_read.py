# chat_read.py
import os
from datetime import date
from typing import Optional

import discord
import yaml

# Path to config file (override with CONFIG_PATH env if needed)
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yml")


def _load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"⚠ Failed to load config.yml from {CONFIG_PATH}: {e}")
        cfg = {}

    discord_cfg = cfg.get("discord", {}) or {}
    return {
        "camp_log_channel_id": int(discord_cfg.get("camp_log_channel_id", 0)),
        "ranch_log_channel_id": int(discord_cfg.get("ranch_log_channel_id", 0)),
        # legacy name, kept for backward-compat if someone still uses it
        "log_channel_id": int(discord_cfg.get("log_channel_id", 0)),
    }


_CFG = _load_config()

CAMP_LOG_CHANNEL_ID = _CFG["camp_log_channel_id"] or _CFG["log_channel_id"]
RANCH_LOG_CHANNEL_ID = _CFG["ranch_log_channel_id"]


async def _get_channel(bot: discord.Client, channel_id: int) -> Optional[discord.abc.Messageable]:
    """
    Generic helper: fetch any text-like channel by ID.
    """
    if not channel_id:
        print("⚠ Channel ID is 0 or not set.")
        return None

    ch = bot.get_channel(channel_id)
    if ch is None:
        try:
            ch = await bot.fetch_channel(channel_id)
        except Exception as e:
            print(f"❌ Failed to fetch channel {channel_id}: {e}")
            return None

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
    channel = await _get_channel(bot, channel_id)
    if not channel:
        print("⚠ No channel available (ID=%s)." % channel_id)
        return ""

    msgs = []

    # oldest_first=True to keep chronological order
    async for m in channel.history(limit=5000, oldest_first=True):
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
                    print("⚠ Failed to read attachment %s: %s" % (fn, e))

        if parts:
            msgs.append("\n".join(parts))

    return "\n".join(msgs)


# ---------------------------------------------------------------------------
# Convenience wrappers: camp + ranch
# ---------------------------------------------------------------------------

async def build_camp_raw_log(
    bot: discord.Client,
    start_date: Optional[date],
    end_date: Optional[date],
) -> str:
    """
    Wrapper for the old camp log, using CAMP_LOG_CHANNEL_ID.
    """
    return await build_raw_log_from_channel(bot, CAMP_LOG_CHANNEL_ID, start_date, end_date)


async def build_ranch_raw_log(
    bot: discord.Client,
    start_date: Optional[date],
    end_date: Optional[date],
) -> str:
    """
    Wrapper for the new ranch log, using RANCH_LOG_CHANNEL_ID.
    """
    return await build_raw_log_from_channel(bot, RANCH_LOG_CHANNEL_ID, start_date, end_date)
