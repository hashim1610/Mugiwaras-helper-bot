import os
import re
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
    """
    Turn '3.5' or '3,5' into float(3.5).
    """
    num_str = num_str.strip().replace(",", ".")
    return float(num_str)


def extract_name_from_discord_line(discord_line: str) -> str:
    """
    Turn a 'Discord:' content into a nice @tag-like name.
    Examples:
    - '@Gamer_anz 1119993751092334622' -> '@Gamer_anz'
    - '@Freddy Fenix [Manager] 123456' -> '@Freddy Fenix [Manager]'
    - '<@1119993751092334622>'         -> '<@1119993751092334622>'
    - 'Gamer_Anz'                      -> '@Gamer_Anz'
    """
    line = discord_line.strip()

    # If it starts with a raw mention (<@...>), just keep it
    if line.startswith("<@"):
        return line

    # If it starts with @, we probably have "@Name [roles] 1234567890"
    if line.startswith("@"):
        parts = line.split()
        if len(parts) > 1 and parts[-1].isdigit():
            # Drop the numeric ID at the end
            return " ".join(parts[:-1])
        return line

    # Otherwise, just take the first "word" as the name and ensure @
    parts = line.split()
    if not parts:
        return "@Unknown"
    base = parts[0]
    if not base.startswith("@"):
        base = "@" + base
    return base


# --------------------------------------------------------------------
# PARSER (REGEX-BASED, WHOLE-TEXT)
# --------------------------------------------------------------------

def parse_log(raw_log: str):
    """
    Parse the raw clan log text and return three lists:
    donations, supplies, ledger.

    This DOES NOT care about dates; date filtering is done at message level
    when we build raw_log from the channel.
    """
    text = raw_log

    donations = []  # {name, materials}
    supplies = []   # {name, amount}
    ledger = []     # {name, transition, amount}

    # ---------------- Donations ----------------
    # Pattern: "Donated ... Materials added: X ...\nDiscord: <something>"
    donation_pattern = re.compile(
        r"Donated.*?Materials\s*added[^\d]*([0-9]+(?:[.,][0-9]+)?)"
        r".*?\nDiscord:\s*(.+)",
        flags=re.IGNORECASE | re.DOTALL
    )

    for m in donation_pattern.finditer(text):
        amount_str = m.group(1)
        discord_part = m.group(2).splitlines()[0]  # only first line after Discord:
        materials = normalize_number(amount_str)
        name = extract_name_from_discord_line(discord_part)
        donations.append({"name": name, "materials": materials})

    # ---------------- Supply Missions ----------------
    # Pattern: "Delivered Supplies: X ...\nDiscord: <something>"
    supply_pattern = re.compile(
        r"Delivered\s*Supplies[^\d]*([0-9]+(?:[.,][0-9]+)?)"
        r".*?\nDiscord:\s*(.+)",
        flags=re.IGNORECASE | re.DOTALL
    )

    for m in supply_pattern.finditer(text):
        amount_str = m.group(1)
        discord_part = m.group(2).splitlines()[0]
        amount = normalize_number(amount_str)
        name = extract_name_from_discord_line(discord_part)
        supplies.append({"name": name, "amount": amount})

    # ---------------- Ledger ----------------
    # Pattern:
    #   "Deposited to clan ledger, $X ...\nDiscord: <something>"
    #   "Withdrew from clan ledger, $X ...\nDiscord: <something>"
    ledger_pattern = re.compile(
        r"(Deposited to clan ledger|Withdrew from clan ledger).*?\$([0-9]+(?:[.,][0-9]+)?)"
        r".*?\nDiscord:\s*(.+)",
        flags=re.IGNORECASE | re.DOTALL
    )

    for m in ledger_pattern.finditer(text):
        action = m.group(1).lower()
        if "deposited" in action:
            transition = "Deposit"
        else:
            transition = "Withdrawal"

        amount_str = m.group(2)
        discord_part = m.group(3).splitlines()[0]
        amount = normalize_number(amount_str)
        name = extract_name_from_discord_line(discord_part)
        ledger.append({"name": name, "transition": transition, "amount": amount})

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
    lines.append("Donations Breakdown Table Summary")
    lines.append("| Name | Donations | Total Materials Value |")
    lines.append("| --- | ---: | ---: |")
    for name, stats in sorted_donations:
        lines.append(
            f"| {name} | {stats['count']} | {stats['total']:.2f} |"
        )
    lines.append("")  # blank line after table

    # 2) Overall Totals
    lines.append("Overall Totals")
    lines.append("| Total Donations | Total Materials Value |")
    lines.append("| ---: | ---: |")
    lines.append(f"| {total_donation_count} | {total_materials_sum:.2f} |")
    lines.append("")

    # 3) Supply Mission Summary
    lines.append("Supply Mission Summary")
    lines.append("| Name | Supplies Delivered |")
    lines.append("| --- | ---: |")
    for s in supplies:
        lines.append(
            f"| {s['name']} | {s['amount']:.2f} |"
        )
    lines.append("")

    # 4) Ledger Transactions
    lines.append("Ledger Transactions")
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
