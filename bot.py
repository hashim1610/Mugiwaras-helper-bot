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
intents.members = True  # Needed for resolving <@ID> → DisplayName

bot = commands.Bot(command_prefix="!", intents=intents)


# --------------------------------------------------------------------
# BASIC HELPERS
# --------------------------------------------------------------------

def strip_code_block(text: str) -> str:
    text = text.strip()
    if text.startswith("```") and text.endswith("```"):
        return text[3:-3].strip()
    return text


def normalize_number(num_str: str) -> float:
    return float(num_str.replace(",", ".").strip())


# --------------------------------------------------------------------
# NAME CLEANING / MENTION RESOLVING
# --------------------------------------------------------------------

def clean_discord_name(discord_part: str, lines, idx: int) -> str | None:
    """
    Extract meaningful name from log line.
    Prefer <@ID> → resolved display name.
    """
    s = discord_part.replace("**", "").replace("`", "").strip()

    # Raw mention in this line
    m = re.search(r"<@!?(\d+)>", s)
    if m:
        return f"<@{m.group(1)}>"

    # Pattern like: @Name ... ID
    tokens = s.split()
    if tokens and tokens[-1].isdigit():
        return f"<@{tokens[-1]}>"

    # Look ahead for name or ID
    for k in range(idx + 1, min(idx + 4, len(lines))):
        nxt = lines[k].replace("**", "").replace("`", "").strip()
        if not nxt:
            continue

        m2 = re.search(r"<@!?(\d+)>", nxt)
        if m2:
            return f"<@{m2.group(1)}>"

        parts = nxt.split()
        if parts and parts[-1].isdigit():
            return f"<@{parts[-1]}>"

        # fallback textual name
        name = " ".join(parts)
        return name

    # Final fallback: use raw cleaned text
    return s or None


def display_name_from_mention(name: str, id_to_name: dict | None) -> str:
    """
    Convert <@ID> → DisplayName (no leading @).
    If not a mention or unknown, return name as-is.
    """
    if not id_to_name:
        return name

    m = re.fullmatch(r"<@!?(\d+)>", name.strip())
    if not m:
        return name  # already a normal name

    uid = m.group(1)
    disp = id_to_name.get(uid)
    if not disp:
        return name

    return disp  # NO '@' here


# --------------------------------------------------------------------
# NUMBER EXTRACTION HELPERS
# --------------------------------------------------------------------

def extract_number_after_marker(text: str, marker: str) -> float | None:
    if marker not in text:
        return None
    tail = text.split(marker, 1)[1]
    digits = ""
    started = False
    for ch in tail:
        if ch.isdigit() or ch in ".,": 
            digits += ch
            started = True
        elif started:
            break
    return normalize_number(digits) if digits else None


def extract_number_after_char(text: str, ch_marker: str) -> float | None:
    if ch_marker not in text:
        return None
    tail = text.split(ch_marker, 1)[1]
    digits = ""
    started = False
    for ch in tail:
        if ch.isdigit() or ch in ".,": 
            digits += ch
            started = True
        elif started:
            break
    return normalize_number(digits) if digits else None


# --------------------------------------------------------------------
# PARSER (Donations / Supplies / Ledger)
# --------------------------------------------------------------------

def parse_log(raw_log: str):
    lines = raw_log.splitlines()
    n = len(lines)

    donations = []
    supplies = []
    ledger = []

    i = 0
    while i < n:
        line = lines[i].strip()

        # Donations
        if "Donated" in line and "Materials added" in line:
            materials = extract_number_after_marker(line, "Materials added")
            if materials is not None:
                name = None
                for j in range(i + 1, min(i + 6, n)):
                    if "Discord:" in lines[j]:
                        dp = lines[j].split("Discord:", 1)[1]
                        name = clean_discord_name(dp, lines, j)
                        break
                if name:
                    donations.append({"name": name, "materials": materials})

        # Supplies
        if "Delivered" in line and "Supplies" in line:
            amt = extract_number_after_marker(line, "Delivered Supplies")
            if amt is not None:
                name = None
                for j in range(i + 1, min(i + 6, n)):
                    if "Discord:" in lines[j]:
                        dp = lines[j].split("Discord:", 1)[1]
                        name = clean_discord_name(dp, lines, j)
                        break
                if name:
                    supplies.append({"name": name, "amount": amt})

        # Ledger
        if ("Deposited to clan ledger" in line) or ("Withdrew from clan ledger" in line):
            trans = "Deposit" if "Deposited" in line else "Withdrawal"
            amt = extract_number_after_char(line, "$")

            if amt is not None:
                name = None
                for j in range(i + 1, min(i + 6, n)):
                    if "Discord:" in lines[j]:
                        dp = lines[j].split("Discord:", 1)[1]
                        name = clean_discord_name(dp, lines, j)
                        break

                if name:
                    ledger.append({"name": name, "transition": trans, "amount": amt})

        i += 1

    return donations, supplies, ledger


# --------------------------------------------------------------------
# TABLE GENERATOR
# --------------------------------------------------------------------

def make_table(headers, rows, align_right=None):
    if align_right is None:
        align_right = set()

    cols = len(headers)
    widths = [len(str(h)) for h in headers]

    for r in rows:
        for i in range(cols):
            widths[i] = max(widths[i], len(str(r[i])))

    def fmt_row(row):
        cells = []
        for i in range(cols):
            c = str(row[i])
            if i in align_right:
                cells.append(c.rjust(widths[i]))
            else:
                cells.append(c.ljust(widths[i]))
        return "| " + " | ".join(cells) + " |"

    header = fmt_row(headers)
    sep = "| " + " | ".join("-" * w for w in widths) + " |"

    result = [header, sep]
    for r in rows:
        result.append(fmt_row(r))

    return "\n".join(result)


# --------------------------------------------------------------------
# BUILD FINAL MARKDOWN OUTPUT (WITH COLORS & EMOJI)
# --------------------------------------------------------------------

def build_markdown_output(donations, supplies, ledger, id_to_name=None):
    sections = []

    # Donations summary
    donation_map = {}
    for d in donations:
        nm = d["name"]
        mt = d["materials"]
        donation_map.setdefault(nm, {"count": 0, "total": 0})
        donation_map[nm]["count"] += 1
        donation_map[nm]["total"] += mt

    sorted_don = sorted(
        donation_map.items(),
        key=lambda kv: (-kv[1]["count"], -kv[1]["total"])
    )

    total_count = sum(v["count"] for v in donation_map.values())
    total_mat = sum(v["total"] for v in donation_map.values())

    # 1) Donations table
    sections.append("**🟥 Donations Breakdown Table Summary**")

    donation_rows = []
    for idx, (name, stats) in enumerate(sorted_don):
        disp = display_name_from_mention(name, id_to_name)

        # ---- Medal assignment ----
        medal = ""
        if idx == 0:
            medal = "🥇 "
        elif idx == 1:
            medal = "🥈 "
        elif idx == 2:
            medal = "🥉 "

        donation_rows.append([
            f"{medal}{disp}",
            stats["count"],
            f"{stats['total']:.2f}",
    ])


    sections.append(
        make_table(
            ["Name", "Donations", "Total Materials Value"],
            donation_rows,
            align_right={1, 2}
        )
    )

    # 2) Overall Totals
    sections.append("**🟦 Overall Totals**")
    sections.append(
        make_table(
            ["Total Donations", "Total Materials Value"],
            [[total_count, f"{total_mat:.2f}"]],
            align_right={0, 1}
        )
    )

    # 3) Supplies
    sections.append("**🟩 Supply Mission Summary**")
    supply_rows = [
        [display_name_from_mention(s["name"], id_to_name), f"{s['amount']:.2f}"]
        for s in supplies
    ]
    sections.append(
        make_table(
            ["Name", "Supplies Delivered"],
            supply_rows,
            align_right={1}
        )
    )

    # 4) Ledger
    sections.append("**🟨 Ledger Transactions**")
    ledger_rows = []
    for l in ledger:
        base_name = display_name_from_mention(l["name"], id_to_name)
        transition = "⬆️ Deposit" if l["transition"] == "Deposit" else "⬇️ Withdrawal"
        ledger_rows.append(
            [base_name, transition, f"{l['amount']:.2f}"]
        )

    sections.append(
        make_table(
            ["Name", "Transition", "Amount"],
            ledger_rows,
            align_right={2}
        )
    )

    return "\n\n".join(sections)


def summarize_log(raw_log: str, id_to_name=None) -> str:
    raw_log = strip_code_block(raw_log)
    donations, supplies, ledger = parse_log(raw_log)
    return build_markdown_output(donations, supplies, ledger, id_to_name)


# --------------------------------------------------------------------
# DISCORD: READ CHANNEL
# --------------------------------------------------------------------

async def get_log_channel():
    if LOG_CHANNEL_ID == 0:
        return None
    ch = bot.get_channel(LOG_CHANNEL_ID)
    if ch is None:
        try:
            ch = await bot.fetch_channel(LOG_CHANNEL_ID)
        except:
            return None
    return ch


async def build_raw_log_from_channel(start_date, end_date):
    channel = await get_log_channel()
    if not channel:
        return ""

    msgs = []
    async for m in channel.history(limit=5000, oldest_first=True):
        md = m.created_at.date()
        if start_date and md < start_date:
            continue
        if end_date and md > end_date:
            continue

        parts = []

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
                except:
                    pass

        if parts:
            msgs.append("\n".join(parts))

    return "\n".join(msgs)


# --------------------------------------------------------------------
# DISCORD OUTPUT HELPERS
# --------------------------------------------------------------------

def chunk_text(text: str, limit=1800):
    out = ""
    for ln in text.splitlines():
        if len(out) + len(ln) + 1 > limit:
            yield out
            out = ""
        out += ln + "\n"
    if out:
        yield out


async def send_pretty(ctx, text: str):
    for part in chunk_text(text):
        await ctx.send(f"```md\n{part.strip()}\n```")


# --------------------------------------------------------------------
# COMMANDS
# --------------------------------------------------------------------

@bot.event
async def on_ready():
    print(f"✔ Logged in as {bot.user} (ID {bot.user.id})")


@bot.command()
async def logsummary_all(ctx):
    raw = await build_raw_log_from_channel(None, None)
    id_to_name = {str(m.id): m.display_name for m in ctx.guild.members}
    out = summarize_log(raw, id_to_name)
    await send_pretty(ctx, out)


@bot.command()
async def logsummary7(ctx):
    today = date.today()
    start = today - timedelta(days=7)
    raw = await build_raw_log_from_channel(start, today)
    id_to_name = {str(m.id): m.display_name for m in ctx.guild.members}
    out = summarize_log(raw, id_to_name)
    await send_pretty(ctx, out)


@bot.command()
async def logsummary_range(ctx, start_str: str, end_str: str):
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
    except:
        return await ctx.send("❌ Use format: `YYYY-MM-DD YYYY-MM-DD`")

    raw = await build_raw_log_from_channel(start, end)
    id_to_name = {str(m.id): m.display_name for m in ctx.guild.members}
    out = summarize_log(raw, id_to_name)
    await send_pretty(ctx, out)


@bot.command()
async def logdebug_range(ctx, start_str: str, end_str: str):
    try:
        start = datetime.strptime(start_str, "%Y-%m-%d").date()
        end = datetime.strptime(end_str, "%Y-%m-%d").date()
    except:
        return await ctx.send("❌ Use format: `YYYY-MM-DD YYYY-MM-DD`")

    raw = await build_raw_log_from_channel(start, end)
    await ctx.send(f"Fetched {len(raw)} chars")

    preview = raw[:800] or "(no text)"
    await ctx.send(f"```text\n{preview}\n```")

    donations, supplies, ledger = parse_log(raw)
    await ctx.send(
        f"Parsed:\nDonations: {len(donations)}\nSupplies: {len(supplies)}\nLedger: {len(ledger)}"
    )

    id_to_name = {str(m.id): m.display_name for m in ctx.guild.members}
    out = build_markdown_output(donations, supplies, ledger, id_to_name)
    await send_pretty(ctx, out)


# ---------------------------------------------------------------
# START BOT
# ---------------------------------------------------------------
bot.run(TOKEN)
