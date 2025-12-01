# chat_read.py
import discord
from datetime import date
import yaml

# Load config
with open("config.yaml", "r") as f:
    CONFIG = yaml.safe_load(f)

LOG_CHANNEL_ID = int(CONFIG["discord"]["log_channel_id"])


async def get_log_channel(bot: discord.Client):
    """
    Get the log channel using the ID from config.yaml.
    """
    if LOG_CHANNEL_ID == 0:
        return None

    ch = bot.get_channel(LOG_CHANNEL_ID)
    if ch is None:
        try:
            ch = await bot.fetch_channel(LOG_CHANNEL_ID)
        except Exception:
            return None
    return ch


async def build_raw_log_from_channel(
    bot: discord.Client,
    start_date: date | None,
    end_date: date | None,
) -> str:
    """
    Read messages from the log channel and return a single big text blob.
    Includes:
      - message content
      - embed titles/descriptions/fields
      - text/log attachments
    """
    channel = await get_log_channel(bot)
    if not channel:
        return ""

    msgs: list[str] = []

    async for m in channel.history(limit=5000, oldest_first=True):
        md = m.created_at.date()
        if start_date and md < start_date:
            continue
        if end_date and md > end_date:
            continue

        parts: list[str] = []

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
            if att.filename.lower().endswith((".txt", ".log")):
                try:
                    data = await att.read()
                    parts.append(data.decode("utf-8"))
                except Exception:
                    pass

        if parts:
            msgs.append("\n".join(parts))

    return "\n".join(msgs)
