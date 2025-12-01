# chat_read.py
import os
from datetime import date

import discord

LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))


async def get_log_channel(bot):
    """
    Get the log channel using LOG_CHANNEL_ID from env.
    """
    if LOG_CHANNEL_ID == 0:
        print("⚠ LOG_CHANNEL_ID is 0 or not set.")
        return None

    ch = bot.get_channel(LOG_CHANNEL_ID)
    if ch is None:
        try:
            ch = await bot.fetch_channel(LOG_CHANNEL_ID)
        except Exception as e:
            print(f"❌ Failed to fetch log channel {LOG_CHANNEL_ID}: {e}")
            return None
    return ch


async def build_raw_log_from_channel(bot, start_date, end_date):
    """
    Read messages from the log channel and return a single big text blob.
    Includes:
      - a date marker line: __DATE__ YYYY-MM-DD
      - message content
      - embed titles/descriptions/fields
      - text/log attachments
    """
    channel = await get_log_channel(bot)
    if not channel:
        print("⚠ No log channel available.")
        return ""

    msgs = []

    async for m in channel.history(limit=5000, oldest_first=True):
        md = m.created_at.date()
        if start_date and md < start_date:
            continue
        if end_date and md > end_date:
            continue

        parts = []

        # Date marker for all content from this message
        parts.append("__DATE__ %s" % md.strftime("%d-%m-%Y"))

        if m.content:
            parts.append(m.content)

        for e in m.embeds:
            if e.title:
                parts.append(e.title)
            if e.description:
                parts.append(e.description)
            for f in e.fields:
                parts.append("%s: %s" % (f.name, f.value))

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
