import os
import re
from datetime import datetime, date, timedelta

import discord
from discord.ext import commands
from discord import app_commands  # for slash commands

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
# BUILD FINAL MARKDOWN OUTPUT / SECTIONS
# --------------------------------------------------------------------

def _build_markdown_sections(donations, supplies, ledger, id_to_name=None):
    """Internal helper: returns a list of 4 markdown sections as strings."""
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
    sec1_lines = []
    sec1_lines.append("**🟥 Donations Breakdown Table Summary**")

    donation_rows = [
        [
            display_name_from_mention(name, id_to_name),
            stats["count"],
            f"{stats['total']:.2f}",
        ]
        for name, stats in sorted_don
    ]

    sec1_lines.append(
        make_table(
            ["Name", "Donations", "Total Materials Value"],
            donation_rows,
            align_right={1, 2}
        )
    )
    sections.append("\n\n".join(sec1_lines))

    # 2) Overall Totals
    sec2_lines = []
    sec2_lines.append("**🟦 Overall Totals**")
    sec2_lines.append(
        make_table(
            ["Total Donations", "Total Materials Value"],
            [[total_count, f"{total_mat:.2f}"]],
            align_right={0, 1}
        )
    )
    sections.append("\n\n".join(sec2_lines))

    # 3) Supplies
    sec3_lines = []
    sec3_lines.append("**🟩 Supply Mission Summary**")
    supply_rows = [
        [display_name_from_mention(s["name"], id_to_name), f"{s['amount']:.2f}"]
        for s in supplies
    ]
    sec3_lines.append(
        make_table(
            ["Name", "Supplies Delivered"],
            supply_rows,
            align_right={1}
        )
    )
    sections.append("\n\n".join(sec3_lines))

    # 4) Ledger
    sec4_lines = []
    sec4_lines.append("**🟨 Ledger Transactions**")
    ledger_rows = []
    for l in ledger:
        base_name = display_name_from_mention(l["name"], id_to_name)
        transition = "⬆️ Deposit" if l["transition"] == "Deposit" else "⬇️ Withdrawal"
        # Dollar symbol added here
        ledger_rows.append(
            [base_name, transition, f"${l['amount']:.2f}"]
        )

    sec4_lines.append(
        make_table(
            ["Name", "Transition", "Amount"],
            ledger_rows,
            align_right={2}
        )
    )
    sections.append("\n\n".join(sec4_lines))

    return sections


def build_markdown_output(donations, supplies, ledger, id_to_name=None):
    """Old behavior: single big markdown string (used by ! commands)."""
    sections = _build_markdown_sections(donations, supplies, ledger, id_to_name)
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
    """Existing helper for prefix (!) commands."""
    for part in chunk_text(text):
        await ctx.send(f"```md\n{part.strip()}\n```")


async def send_sections_interaction(
    interaction: discord.Interaction,
    sections,
    already_responded: bool = False,
):
    """
    Send one or more logical sections for slash commands.
    Each section may still be chunked if it's huge.
    """
    first_send = not already_responded

    for sec in sections:
        if not sec.strip():
            continue
        for chunk in chunk_text(sec):
            msg = f"```md\n{chunk.strip()}\n```"
            if first_send:
                await interaction.response.send_message(msg)
                first_send = False
            else:
                await interaction.followup.send(msg)


# --------------------------------------------------------------------
# EVENTS
# --------------------------------------------------------------------

@bot.event
async def on_ready():
    print(f"✔ Logged in as {bot.user} (ID {bot.user.id})")

    # Per-guild sync so slash commands appear quickly in all servers
    try:
        for guild in bot.guilds:
            synced = await bot.tree.sync(guild=guild)
            print(f"✔ Synced {len(synced)} commands to guild {guild.name} ({guild.id})")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")


# ----------------------- PREFIX (!) COMMANDS ------------------------

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
        # DD-MM-YYYY format
        start = datetime.strptime(start_str, "%d-%m-%Y").date()
        end = datetime.strptime(end_str, "%d-%m-%Y").date()
    except:
        return await ctx.send("❌ Use format: `DD-MM-YYYY DD-MM-YYYY`")

    raw = await build_raw_log_from_channel(start, end)
    id_to_name = {str(m.id): m.display_name for m in ctx.guild.members}
    out = summarize_log(raw, id_to_name)
    await send_pretty(ctx, out)


@bot.command()
async def logdebug_range(ctx, start_str: str, end_str: str):
    try:
        # DD-MM-YYYY format
        start = datetime.strptime(start_str, "%d-%m-%Y").date()
        end = datetime.strptime(end_str, "%d-%m-%Y").date()
    except:
        return await ctx.send("❌ Use format: `DD-MM-YYYY DD-MM-YYYY`")

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


# ------- NEW PREFIX (!) COMMANDS: SECTION-SPECIFIC (RANGE) ----------

@bot.command()
async def logdonations_range(ctx, start_str: str, end_str: str):
    """Show only the Donations section for a date range."""
    try:
        start = datetime.strptime(start_str, "%d-%m-%Y").date()
        end = datetime.strptime(end_str, "%d-%m-%Y").date()
    except:
        return await ctx.send("❌ Use format: `DD-MM-YYYY DD-MM-YYYY`")

    raw = await build_raw_log_from_channel(start, end)
    id_to_name = {str(m.id): m.display_name for m in ctx.guild.members}
    donations, supplies, ledger = parse_log(raw)
    sections = _build_markdown_sections(donations, supplies, ledger, id_to_name)
    donations_sec = sections[0]
    await send_pretty(ctx, donations_sec)


@bot.command()
async def logtotals_range(ctx, start_str: str, end_str: str):
    """Show only the Overall Totals section for a date range."""
    try:
        start = datetime.strptime(start_str, "%d-%m-%Y").date()
        end = datetime.strptime(end_str, "%d-%m-%Y").date()
    except:
        return await ctx.send("❌ Use format: `DD-MM-YYYY DD-MM-YYYY`")

    raw = await build_raw_log_from_channel(start, end)
    id_to_name = {str(m.id): m.display_name for m in ctx.guild.members}
    donations, supplies, ledger = parse_log(raw)
    sections = _build_markdown_sections(donations, supplies, ledger, id_to_name)
    totals_sec = sections[1]
    await send_pretty(ctx, totals_sec)


@bot.command()
async def logsupply_range(ctx, start_str: str, end_str: str):
    """Show only the Supply Mission section for a date range."""
    try:
        start = datetime.strptime(start_str, "%d-%m-%Y").date()
        end = datetime.strptime(end_str, "%d-%m-%Y").date()
    except:
        return await ctx.send("❌ Use format: `DD-MM-YYYY DD-MM-YYYY`")

    raw = await build_raw_log_from_channel(start, end)
    id_to_name = {str(m.id): m.display_name for m in ctx.guild.members}
    donations, supplies, ledger = parse_log(raw)
    sections = _build_markdown_sections(donations, supplies, ledger, id_to_name)
    supply_sec = sections[2]
    await send_pretty(ctx, supply_sec)


@bot.command()
async def logledger_range(ctx, start_str: str, end_str: str):
    """Show only the Ledger Transactions section for a date range."""
    try:
        start = datetime.strptime(start_str, "%d-%m-%Y").date()
        end = datetime.strptime(end_str, "%d-%m-%Y").date()
    except:
        return await ctx.send("❌ Use format: `DD-MM-YYYY DD-MM-YYYY`")

    raw = await build_raw_log_from_channel(start, end)
    id_to_name = {str(m.id): m.display_name for m in ctx.guild.members}
    donations, supplies, ledger = parse_log(raw)
    sections = _build_markdown_sections(donations, supplies, ledger, id_to_name)
    ledger_sec = sections[3]
    await send_pretty(ctx, ledger_sec)


# ------------------------ SLASH (/) COMMANDS ------------------------

@bot.tree.command(name="logsummary_all", description="Summarize all logs in the log channel")
async def logsummary_all_slash(interaction: discord.Interaction):
    raw = await build_raw_log_from_channel(None, None)
    guild = interaction.guild
    id_to_name = {str(m.id): m.display_name for m in guild.members} if guild else {}
    donations, supplies, ledger = parse_log(raw)
    sections = _build_markdown_sections(donations, supplies, ledger, id_to_name)
    await send_sections_interaction(interaction, sections)


@bot.tree.command(name="logsummary7", description="Summarize the last 7 days of logs")
async def logsummary7_slash(interaction: discord.Interaction):
    today = date.today()
    start = today - timedelta(days=7)
    raw = await build_raw_log_from_channel(start, today)
    guild = interaction.guild
    id_to_name = {str(m.id): m.display_name for m in guild.members} if guild else {}
    donations, supplies, ledger = parse_log(raw)
    sections = _build_markdown_sections(donations, supplies, ledger, id_to_name)
    await send_sections_interaction(interaction, sections)


@bot.tree.command(name="logsummary_range", description="Summarize logs between two dates")
@app_commands.describe(
    start_str="Start date (DD-MM-YYYY)",
    end_str="End date (DD-MM-YYYY)"
)
async def logsummary_range_slash(
    interaction: discord.Interaction,
    start_str: str,
    end_str: str
):
    try:
        # DD-MM-YYYY
        start = datetime.strptime(start_str, "%d-%m-%Y").date()
        end = datetime.strptime(end_str, "%d-%m-%Y").date()
    except:
        await interaction.response.send_message(
            "❌ Use format: `DD-MM-YYYY` for both dates.",
            ephemeral=True
        )
        return

    raw = await build_raw_log_from_channel(start, end)
    guild = interaction.guild
    id_to_name = {str(m.id): m.display_name for m in guild.members} if guild else {}
    donations, supplies, ledger = parse_log(raw)
    sections = _build_markdown_sections(donations, supplies, ledger, id_to_name)
    await send_sections_interaction(interaction, sections)


@bot.tree.command(name="logdebug_range", description="Debug + summarize logs between two dates")
@app_commands.describe(
    start_str="Start date (DD-MM-YYYY)",
    end_str="End date (DD-MM-YYYY)"
)
async def logdebug_range_slash(
    interaction: discord.Interaction,
    start_str: str,
    end_str: str
):
    try:
        # DD-MM-YYYY
        start = datetime.strptime(start_str, "%d-%m-%Y").date()
        end = datetime.strptime(end_str, "%d-%m-%Y").date()
    except:
        await interaction.response.send_message(
            "❌ Use format: `DD-MM-YYYY` for both dates.",
            ephemeral=True
        )
        return

    raw = await build_raw_log_from_channel(start, end)

    # First message: basic stats + preview
    msg = f"Fetched {len(raw)} chars"
    preview = raw[:800] or "(no text)"
    msg_preview = f"{msg}\n```text\n{preview}\n```"
    await interaction.response.send_message(msg_preview)

    donations, supplies, ledger = parse_log(raw)
    await interaction.followup.send(
        f"Parsed:\nDonations: {len(donations)}\nSupplies: {len(supplies)}\nLedger: {len(ledger)}"
    )

    guild = interaction.guild
    id_to_name = {str(m.id): m.display_name for m in guild.members} if guild else {}
    sections = _build_markdown_sections(donations, supplies, ledger, id_to_name)

    # Send the 4 logical report parts as followups (interaction already responded)
    await send_sections_interaction(interaction, sections, already_responded=True)


# ---- NEW SLASH (/) COMMANDS: SECTION-SPECIFIC (RANGE) -----

@bot.tree.command(name="logdonations_range", description="Show only Donations section for a date range")
@app_commands.describe(
    start_str="Start date (DD-MM-YYYY)",
    end_str="End date (DD-MM-YYYY)"
)
async def logdonations_range_slash(
    interaction: discord.Interaction,
    start_str: str,
    end_str: str
):
    try:
        start = datetime.strptime(start_str, "%d-%m-%Y").date()
        end = datetime.strptime(end_str, "%d-%m-%Y").date()
    except:
        await interaction.response.send_message(
            "❌ Use format: `DD-MM-YYYY` for both dates.",
            ephemeral=True
        )
        return

    raw = await build_raw_log_from_channel(start, end)
    guild = interaction.guild
    id_to_name = {str(m.id): m.display_name for m in guild.members} if guild else {}
    donations, supplies, ledger = parse_log(raw)
    sections = _build_markdown_sections(donations, supplies, ledger, id_to_name)
    donations_sec = [sections[0]]
    await send_sections_interaction(interaction, donations_sec)


@bot.tree.command(name="logtotals_range", description="Show only Overall Totals for a date range")
@app_commands.describe(
    start_str="Start date (DD-MM-YYYY)",
    end_str="End date (DD-MM-YYYY)"
)
async def logtotals_range_slash(
    interaction: discord.Interaction,
    start_str: str,
    end_str: str
):
    try:
        start = datetime.strptime(start_str, "%d-%m-%Y").date()
        end = datetime.strptime(end_str, "%d-%m-%Y").date()
    except:
        await interaction.response.send_message(
            "❌ Use format: `DD-MM-YYYY` for both dates.",
            ephemeral=True
        )
        return

    raw = await build_raw_log_from_channel(start, end)
    guild = interaction.guild
    id_to_name = {str(m.id): m.display_name for m in guild.members} if guild else {}
    donations, supplies, ledger = parse_log(raw)
    sections = _build_markdown_sections(donations, supplies, ledger, id_to_name)
    totals_sec = [sections[1]]
    await send_sections_interaction(interaction, totals_sec)


@bot.tree.command(name="logsupply_range", description="Show only Supply section for a date range")
@app_commands.describe(
    start_str="Start date (DD-MM-YYYY)",
    end_str="End date (DD-MM-YYYY)"
)
async def logsupply_range_slash(
    interaction: discord.Interaction,
    start_str: str,
    end_str: str
):
    try:
        start = datetime.strptime(start_str, "%d-%m-%Y").date()
        end = datetime.strptime(end_str, "%d-%m-%Y").date()
    except:
        await interaction.response.send_message(
            "❌ Use format: `DD-MM-YYYY` for both dates.",
            ephemeral=True
        )
        return

    raw = await build_raw_log_from_channel(start, end)
    guild = interaction.guild
    id_to_name = {str(m.id): m.display_name for m in guild.members} if guild else {}
    donations, supplies, ledger = parse_log(raw)
    sections = _build_markdown_sections(donations, supplies, ledger, id_to_name)
    supply_sec = [sections[2]]
    await send_sections_interaction(interaction, supply_sec)


@bot.tree.command(name="logledger_range", description="Show only Ledger section for a date range")
@app_commands.describe(
    start_str="Start date (DD-MM-YYYY)",
    end_str="End date (DD-MM-YYYY)"
)
async def logledger_range_slash(
    interaction: discord.Interaction,
    start_str: str,
    end_str: str
):
    try:
        start = datetime.strptime(start_str, "%d-%m-%Y").date()
        end = datetime.strptime(end_str, "%d-%m-%Y").date()
    except:
        await interaction.response.send_message(
            "❌ Use format: `DD-MM-YYYY` for both dates.",
            ephemeral=True
        )
        return

    raw = await build_raw_log_from_channel(start, end)
    guild = interaction.guild
    id_to_name = {str(m.id): m.display_name for m in guild.members} if guild else {}
    donations, supplies, ledger = parse_log(raw)
    sections = _build_markdown_sections(donations, supplies, ledger, id_to_name)
    ledger_sec = [sections[3]]
    await send_sections_interaction(interaction, ledger_sec)


# ---------------------------------------------------------------
# START BOT
# ---------------------------------------------------------------
bot.run(TOKEN)
