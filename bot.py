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
# PARSING HELPERS
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


def find_discord_name(lines, start_index):
    """
    Extracts user name with @tag retained.
    Handles:
    - Discord: @Name 1234          -> @Name
    - Discord: @Name               -> @Name
    - Discord: <@1234>             -> @VisibleName (next line)
    - Discord: <@!1234>            -> @VisibleName (next line)
    - Fallback:                    -> @ID-1234
    """
    for i in range(start_index, len(lines)):
        line = lines[i].strip()
        if not line.startswith("Discord:"):
            continue

        # Case 1: Discord: @Name 123456
        m = re.search(r"Discord:\s*@(.+?)\s+\d+\s*$", line)
        if m:
            name = m.group(1).strip()
            return f"@{name}"

        # Case 2: Discord: @Name
        m2 = re.search(r"Discord:\s*@(.+)", line)
        if m2:
            name = m2.group(1).strip()
            return f"@{name}"

        # Case 3: Mention only: <@1234> or <@!1234>
        m3 = re.search(r"Discord:\s*<@!?(\d+)>", line)
        if m3:
            # Try next non-empty line as visible name
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines):
                visible = lines[j].strip()
                return f"@{visible}"
            # Fallback: use ID-based label
            return f"@ID-{m3.group(1)}"

        return None

    return None


def parse_log(raw_log: str):
    """
    Parse the raw clan log text and return three lists:
    donations, supplies, ledger.
    (We do NOT track dates here; date filtering is done at message level.)
    """
    lines = raw_log.splitlines()

    donations = []  # {name, materials (float)}
    supplies = []   # {name, amount (float)}
    ledger = []     # {name, transition, amount (float)}

    for i, line in enumerate(lines):
        stripped = line.strip()

        # ----- Donations -----
        if "Donated" in stripped and "Materials" in stripped and "added" in stripped:
            # Very tolerant: "Materials added: 3.5", "Materials  added : 3,5", etc.
            m = re.search(
                r"Materials\s*added[^\d]*([0-9]+(?:[.,][0-9]+)?)",
                stripped,
                flags=re.IGNORECASE,
            )
            if not m:
                continue
            materials = normalize_number(m.group(1))
            name = find_discord_name(lines, i + 1)
            if not name:
                continue
            donations.append({
                "name": name,
                "materials": materials,
            })
            continue

        # ----- Supply Missions -----
        if "Delivered" in stripped and "Supplies" in stripped:
            m = re.search(
                r"Delivered\s*Supplies[^\d]*([0-9]+(?:[.,][0-9]+)?)",
                stripped,
                flags=re.IGNORECASE,
            )
            if not m:
                continue
            amount = normalize_number(m.group(1))
            name = find_discord_name(lines, i + 1)
            if not name:
                continue
            supplies.append({
                "name": name,
                "amount": amount,
            })
            continue

        # ----- Ledger -----
        if "Deposited to clan ledger" in stripped or "Withdrew from clan ledger" in stripped:
            transition = "Deposit" if "Deposited" in stripped else "Withdrawal"
            m = re.search(r"\$([0-9]+(?:[.,][0-9]+)?)", stripped)
            if not m:
                continue
            amount = normalize_number(m.group(1))
            name = find_discord_name(lines, i + 1)
            if not name:
                continue
            ledger.append({
                "name": name,
                "transition": transition,
                "amount": amount,
            })
            continue

    return donations, supplies, ledger


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

    cleaned = strip_code_block(raw_log)
    donations, supplies, ledger = parse_log(cleaned)

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
