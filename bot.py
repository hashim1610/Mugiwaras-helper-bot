import os
from datetime import datetime, date, timedelta

import discord
from discord.ext import commands

# --------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------

TOKEN = os.getenv("TOKEN")  # set in Railway
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "0"))  # set in Railway

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


# --------------------------------------------------------------------
# SMALL HELPERS
# --------------------------------------------------------------------

def strip_code_block(text: str) -> str:
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        text = text[3:-3].strip()
    return text


def normalize_number(num_str: str) -> float:
    """Turn '3.5' or '3,5' into float(3.5)."""
    num_str = num_str.strip().replace(",", ".")
    return float(num_str)


def clean_discord_name(discord_part: str, lines, idx: int) -> str | None:
    """
    Clean up the "Discord: ..." content into a usable name/mention.

    Priority:
    1) If we can see an ID (like ... 1116155335854534766), use it to form <@ID>
    2) If there's a raw mention <@ID>, keep <@ID>
    3) Otherwise fall back to a text '@Name'
    4) If the 'name' is just a long row of dashes/underscores, ignore it
    """
    import re

    s = discord_part.strip()
    if not s:
        return None

    # Remove markdown clutter
    s = s.replace("**", "").replace("`", "").strip()

    # --- Case 1: raw mention <@...> or <@!...> in this line ---
    m = re.search(r"<@!?(\d+)>", s)
    if m:
        user_id = m.group(1)
        return f"<@{user_id}>"

    # --- Case 2: trailing numeric ID token in this line ---
    tokens = s.split()
    if tokens and tokens[-1].isdigit():
        user_id = tokens[-1]
        return f"<@{user_id}>"

    # --- Case 3: look at a couple of next lines for an ID or mention ---
    for k in range(idx + 1, min(idx + 4, len(lines))):
        candidate = lines[k].strip()
        if not candidate:
            continue
        candidate = candidate.replace("**", "").replace("`", "").strip()

        # raw mention in next line
        m2 = re.search(r"<@!?(\d+)>", candidate)
        if m2:
            return f"<@{m2.group(1)}>"

        parts = candidate.split()
        if parts and parts[-1].isdigit():
            return f"<@{parts[-1]}>"

        # fallback text name from next line
        if parts:
            name = parts[0]
            if not name.startswith("@"):
                name = "@" + name.lstrip("@")
            # avoid junk-only dashed names
            core = name.lstrip("@").strip()
            if core and all(ch in "-_" for ch in core) and len(core) > 5:
                continue
            return name

    # --- Case 4: fallback to text name from this line ---
    # Try to start at first '@' if present
    at_pos = s.find("@")
    candidate = s[at_pos:] if at_pos != -1 else s
    candidate = candidate.strip()
    parts = candidate.split()
    if not parts:
        return None

    if not parts[0].startswith("@"):
        parts[0] = "@" + parts[0].lstrip("@")
    name = " ".join(parts)

    # Remove trailing numeric ID if somehow still there
    parts2 = name.split()
    if len(parts2) > 1 and parts2[-1].isdigit():
        parts2 = parts2[:-1]
    name = " ".join(parts2).strip()

    core = name.lstrip("@").strip()
    if core and all(ch in "-_" for ch in core) and len(core) > 5:
        return None

    return name or None


def extract_number_after_marker(text: str, marker: str) -> float | None:
    """
    From a line, find first number after 'marker'.
    Example: text='Donated ... Materials added: 3.5 ID: 2159', marker='Materials added'
    """
    if marker not in text:
        return None
    tail = text.split(marker, 1)[1]
    # scan characters for first number
    num_chars = ""
    seen_digit = False
    for ch in tail:
        if ch.isdigit() or ch in ".,":  # allow comma / dot
            num_chars += ch
            seen_digit = True
        elif seen_digit:
            break
    if not seen_digit:
        return None
    try:
        return normalize_number(num_chars)
    except ValueError:
        return None


def extract_number_after_char(text: str, ch_marker: str) -> float | None:
    """
    Find first number after a specific char marker, e.g. '$'.
    """
    if ch_marker not in text:
        return None
    tail = text.split(ch_marker, 1)[1]
    num_chars = ""
    seen_digit = False
    for ch in tail:
        if ch.isdigit() or ch in ".,":  # allow comma / dot
            num_chars += ch
            seen_digit = True
        elif seen_digit:
            break
    if not seen_digit:
        return None
    try:
        return normalize_number(num_chars)
    except ValueError:
        return None


# --------------------------------------------------------------------
# PARSER (LINE-BY-LINE, SIMPLE)
# --------------------------------------------------------------------

def parse_log(raw_log: str):
    """
    Parse the raw clan log text and return three lists:
    donations, supplies, ledger.

    date filtering is done at message level when building raw_log.
    """
    lines = raw_log.splitlines()

    donations = []  # {name, materials}
    supplies = []   # {name, amount}
    ledger = []     # {name, transition, amount}

    n = len(lines)
    i = 0
    while i < n:
        line = lines[i].strip()

        # ---------- Donations ----------
        if "Donated" in line and "Materials" in line and "added" in line:
            materials = extract_number_after_marker(line, "Materials added")
            if materials is not None:
                # look ahead for Discord line
                name = None
                for j in range(i + 1, min(i + 6, n)):
                    if "Discord:" in lines[j]:
                        discord_part = lines[j].split("Discord:", 1)[1]
                        name = clean_discord_name(discord_part, lines, j)
                        break
                if name:
                    donations.append({"name": name, "materials": materials})

        # ---------- Supplies ----------
        if "Delivered" in line and "Supplies" in line:
            amount = extract_number_after_marker(line, "Delivered Supplies")
            if amount is not None:
                name = None
                for j in range(i + 1, min(i + 6, n)):
                    if "Discord:" in lines[j]:
                        discord_part = lines[j].split("Discord:", 1)[1]
                        name = clean_discord_name(discord_part, lines, j)
                        break
                if name:
                    supplies.append({"name": name, "amount": amount})

        # ---------- Ledger ----------
        if "Deposited to clan ledger" in line or "Withdrew from clan ledger" in line:
            if "Deposited" in line:
                transition = "Deposit"
            else:
                transition = "Withdrawal"

            amount = extract_number_after_char(line, "$")
            if amount is not None:
                name = None
                for j in range(i + 1, min(i + 6, n)):
                    if "Discord:" in lines[j]:
                        discord_part = lines[j].split("Discord:", 1)[1]
                        name = clean_discord_name(discord_part, lines, j)
                        break
                if name:
                    ledger.append({"name": name, "transition": transition, "amount": amount})

        i += 1

    return donations, supplies, ledger


# --------------------------------------------------------------------
# TABLE BUILDING
# --------------------------------------------------------------------

def build_markdown_output(donations, supplies, ledger):
    """
    Build the final markdown string with exactly 4 tables in order:
    Donations Breakdown Table Summary
    Overall Totals
    Supply Mission Summary
    Ledger Transactions
    """

    # ----- Donations summary -----
    donation_by_name = {}
    for d in donations:
        name = d["name"]
        mat = d["materials"]
        if name not in donation_by_name:
            donation_by_name[name] = {"count": 0, "total": 0.0}
        donation_by_name[name]["count"] += 1
        donation_by_name[name]["total"] += mat

    # Sort by Donations desc, then Total Materials Value desc
    sorted_donations = sorted(
        donation_by_name.items(),
        key=lambda kv: (-kv[1]["count"], -kv[1]["total"])
    )

    total_donation_count = sum(v["count"] for v in donation_by_name.values())
    total_materials_sum = sum(v["total"] for v in donation_by_name.values())

    lines = []

    # 1) Donations Breakdown Table Summary
    lines.append("**Donations Breakdown Table Summary**")
    lines.append("| Name | Donations | Total Materials Value |")
    lines.append("| --- | ---: | ---: |")
    for name, stats in sorted_donations:
        lines.append(
            f"| {name} | {stats['count']} | {stats['total']:.2f} |"
        )
    lines.append("")  # blank line after table

    # 2) Overall Totals
    lines.append("**Overall Totals**")
    lines.append("| Total Donations | Total Materials Value |")
    lines.append("| ---: | ---: |")
    lines.append(f"| {total_donation_count} | {total_materials_sum:.2f} |")
    lines.append("")

    # 3) Supply Mission Summary
    lines.append("**Supply Mission Summary**")
    lines.append("| Name | Supplies Delivered |")
    lines.append("| --- | ---: |")
    for s in supplies:
        lines.append(
            f"| {s['name']} | {s['amount']:.2f} |"
        )
    lines.append("")

    # 4) Ledger Transactions
    lines.append("**Ledger Transactions**")
    lines.append("| Name | Transition | Amount |")
    lines.append("| --- | --- | ---: |")
    for l in ledger:
        lines.append(
            f"| {l['name']} | {l['transition']} | {l['amount']:.2f} |"
        )

    # IMPORTANT: no extra commentary or text
    return "\n".join(lines)


def summarize_log(raw_log: str) -> str:
    raw_log = strip_code_block(raw_log)
    donations, supplies, ledger = parse_log(raw_log)
    return build_markdown_output(donations, supplies, ledger)


# --------------------------------------------------------------------
# DISCORD CHANNEL READING
# --------------------------------------------------------------------

async def get_log_channel():
    if LOG_CHANNEL_ID == 0:
        return None
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel is None:
        try:
            channel = await bot.fetch_channel(LOG_CHANNEL_ID)
        except Exception:
            return None
    return channel


async def build_raw_log_from_channel(start_date: date | None, end_date: date | None) -> str:
    """
    Fetch messages from the log channel, filter them by created_at date (message timestamp),
    and combine their content (including embeds & text attachments) into one big text blob.
    """
    channel = await get_log_channel()
    if channel is None:
        return ""

    messages = []
    async for msg in channel.history(limit=5000, oldest_first=True):
        msg_date = msg.created_at.date()
        if start_date and msg_date < start_date:
            continue
        if end_date and msg_date > end_date:
            continue

        parts = []

        # 1) Normal text content
        if msg.content:
            parts.append(msg.content)

        # 2) Embeds (common for log bots)
        for embed in msg.embeds:
            if embed.title:
                parts.append(str(embed.title))
            if embed.description:
                parts.append(str(embed.description))
            for field in embed.fields:
                parts.append(f"{field.name}: {field.value}")

        # 3) Text attachments (.txt, .log)
        for att in msg.attachments:
            if att.filename.lower().endswith((".txt", ".log")):
                try:
                    data = await att.read()
                    parts.append(data.decode("utf-8", errors="ignore"))
                except Exception:
                    pass

        if parts:
            messages.append("\n".join(parts))

    return "\n".join(messages)


# --------------------------------------------------------------------
# BOT EVENTS & COMMANDS
# --------------------------------------------------------------------

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


def chunk_text(text: str, limit: int = 1900):
    """Yield <=limit-char chunks split on line boundaries."""
    chunk = ""
    for line in text.splitlines():
        if len(chunk) + len(line) + 1 > limit:
            yield chunk
            chunk = ""
        chunk += line + "\n"
    if chunk:
        yield chunk


@bot.command(name="logsummary_all")
async def logsummary_all(ctx):
    """
    Usage: !logsummary_all
    Reads (up to limit) all messages from the log channel and summarizes them.
    """
    raw_log = await build_raw_log_from_channel(start_date=None, end_date=None)
    output = summarize_log(raw_log)

    for part in chunk_text(output):
        await ctx.send(part)


@bot.command(name="logsummary7")
async def logsummary_last7(ctx):
    """
    Usage: !logsummary7
    Reads from the log channel for the last 7 days and outputs the 4 tables.
    """
    today = date.today()
    start = today - timedelta(days=7)

    raw_log = await build_raw_log_from_channel(start_date=start, end_date=today)
    output = summarize_log(raw_log)

    for part in chunk_text(output):
        await ctx.send(part)


@bot.command(name="logsummary_range")
async def logsummary_range(ctx, start_str: str, end_str: str):
    """
    Usage: !logsummary_range 2025-11-25 2025-11-27
    Reads from the log channel for that date range.
    """
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
    except ValueError:
        await ctx.send("Invalid date format. Use YYYY-MM-DD YYYY-MM-DD.")
        return

    raw_log = await build_raw_log_from_channel(start_date=start, end_date=end)
    output = summarize_log(raw_log)

    for part in chunk_text(output):
        await ctx.send(part)


@bot.command(name="logdebug_range")
async def logdebug_range(ctx, start_str: str, end_str: str):
    """
    Debug command: shows how much raw log text we fetched,
    a small preview, and what the parser sees (donation counts + tables).
    Usage: !logdebug_range 2025-11-25 2025-11-27
    """
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
    except ValueError:
        await ctx.send("Invalid date format. Use YYYY-MM-DD YYYY-MM-DD.")
        return

    raw_log = await build_raw_log_from_channel(start_date=start, end_date=end)
    await ctx.send(f"Fetched {len(raw_log)} characters from log channel.")

    preview = raw_log[:800] or "(no text)"
    await ctx.send(f"Preview:\n```{preview}```")

    donations, supplies, ledger = parse_log(raw_log)
    await ctx.send(
        f"Parser results:\n"
        f"Donations: {len(donations)}\n"
        f"Supplies: {len(supplies)}\n"
        f"Ledger entries: {len(ledger)}"
    )

    tables = build_markdown_output(donations, supplies, ledger)
    for part in chunk_text(tables):
        await ctx.send(part)


bot.run(TOKEN)
