# camp_commands.py
from datetime import datetime
import io

import discord
from discord import app_commands

from chat_read import COMMAND_CHANNEL_ID, build_camp_raw_log
from camp_out import (
    parse_log,
    build_markdown_sections,
    build_logsummary_csv_bytes,
)


# -------------------------------------------------------------
# Utility: Build mention → display name map
# -------------------------------------------------------------
def _build_id_to_name(guild: discord.Guild | None):
    if not guild:
        return {}
    return {str(m.id): m.display_name for m in guild.members}


# -------------------------------------------------------------
# Markdown chunking
# -------------------------------------------------------------
def _chunk_text(text: str, limit: int = 1800):
    out = ""
    for ln in text.splitlines():
        if len(out) + len(ln) + 1 > limit:
            yield out
            out = ""
        out += ln + "\n"
    if out:
        yield out


# -------------------------------------------------------------
# Interaction sender (supports multiple sections)
# -------------------------------------------------------------
async def _send_sections_interaction(
    interaction: discord.Interaction,
    sections,
    already_responded: bool = False,
):
    """
    If already_responded=False:
      - first chunk uses interaction.response.send_message()
      - remaining use interaction.followup.send()
    If already_responded=True:
      - all use interaction.followup.send()
    """
    first_send = not already_responded

    for sec in sections:
        if not sec.strip():
            continue

        for chunk in _chunk_text(sec):
            msg = f"```md\n{chunk.strip()}\n```"
            if first_send:
                await interaction.response.send_message(msg)
                first_send = False
            else:
                await interaction.followup.send(msg)


# -------------------------------------------------------------
# Channel restriction
# -------------------------------------------------------------
async def _ensure_command_channel(interaction: discord.Interaction) -> bool:
    """
    Ensure the command is used in the correct channel (COMMAND_CHANNEL_ID).
    If not, send an ephemeral error and return False.
    """
    if interaction.channel_id != COMMAND_CHANNEL_ID:
        await interaction.response.send_message(
            f"❌ This command can only be used in <#{COMMAND_CHANNEL_ID}>.",
            ephemeral=True,
        )
        return False
    return True


# -------------------------------------------------------------
# REGISTER ALL CAMP COMMANDS
# -------------------------------------------------------------
def register_camp_commands(bot: discord.Client):
    """
    Registers all /camp_* commands to the bot.
    """

    # ---------------------------------------------------------
    # /camp_report  (CSV output)
    # ---------------------------------------------------------
    @bot.tree.command(
        name="camp_report",
        description="Generate full camp log report as CSV for a date range.",
    )
    @app_commands.describe(
        start_str="Start date (DD-MM-YYYY)",
        end_str="End date (DD-MM-YYYY)",
    )
    async def camp_report_slash(
        interaction: discord.Interaction,
        start_str: str,
        end_str: str,
    ):
        if not await _ensure_command_channel(interaction):
            return

        # Parse date
        try:
            start = datetime.strptime(start_str, "%d-%m-%Y").date()
            end = datetime.strptime(end_str, "%d-%m-%Y").date()
        except Exception:
            await interaction.response.send_message(
                "❌ Use format: `DD-MM-YYYY` for both dates.",
                ephemeral=True,
            )
            return

        # Defer early because this can be heavy
        await interaction.response.defer(thinking=True)

        # Read logs
        raw = await build_camp_raw_log(interaction.client, start, end)
        guild = interaction.guild
        id_to_name = _build_id_to_name(guild)

        # Parse (NOTE: order matches camp_out.parse_log)
        donations, supplies, ledger, deliveries = parse_log(raw)

        # Build CSV (NOTE: argument order matches camp_out.build_logsummary_csv_bytes)
        csv_bytes = build_logsummary_csv_bytes(
            donations, supplies, ledger, deliveries, id_to_name
        )

        filename = f"camp_report_{start_str}_to_{end_str}.csv"
        file = discord.File(io.BytesIO(csv_bytes), filename=filename)

        await interaction.followup.send(
            "📄 Camp Report CSV is ready:",
            file=file,
        )

    # ---------------------------------------------------------
    # /camp_debug
    # ---------------------------------------------------------
    @bot.tree.command(
        name="camp_debug",
        description="Debug camp logs: show preview + parsed stats + full markdown.",
    )
    @app_commands.describe(
        start_str="Start date (DD-MM-YYYY)",
        end_str="End date (DD-MM-YYYY)",
    )
    async def camp_debug_slash(
        interaction: discord.Interaction,
        start_str: str,
        end_str: str,
    ):
        if not await _ensure_command_channel(interaction):
            return

        try:
            start = datetime.strptime(start_str, "%d-%m-%Y").date()
            end = datetime.strptime(end_str, "%d-%m-%Y").date()
        except Exception:
            await interaction.response.send_message(
                "❌ Use format `DD-MM-YYYY`",
                ephemeral=True,
            )
            return

        # Read text (should be fast enough to not defer, but it's okay)
        raw = await build_camp_raw_log(interaction.client, start, end)

        preview = raw[:800] or "(no text)"
        await interaction.response.send_message(
            f"Fetched {len(raw)} chars\n```text\n{preview}\n```"
        )

        # Parse
        donations, supplies, ledger, deliveries = parse_log(raw)

        await interaction.followup.send(
            "Parsed:\nDonations: {d}\nSupplies: {s}\nLedger: {l}\nDeliveries: {x}".format(
                d=len(donations),
                s=len(supplies),
                l=len(ledger),
                x=len(deliveries),
            )
        )

        guild = interaction.guild
        id_to_name = _build_id_to_name(guild)

        sections = build_markdown_sections(
            donations, supplies, ledger, deliveries, id_to_name
        )

        await _send_sections_interaction(
            interaction, sections, already_responded=True
        )

    # ---------------------------------------------------------
    # /camp_donations
    # ---------------------------------------------------------
    @bot.tree.command(
        name="camp_donations",
        description="Show only the Donations Breakdown (with totals).",
    )
    @app_commands.describe(
        start_str="Start date (DD-MM-YYYY)",
        end_str="End date (DD-MM-YYYY)",
    )
    async def camp_donations_slash(
        interaction: discord.Interaction,
        start_str: str,
        end_str: str,
    ):
        if not await _ensure_command_channel(interaction):
            return

        try:
            start = datetime.strptime(start_str, "%d-%m-%Y").date()
            end = datetime.strptime(end_str, "%d-%m-%Y").date()
        except Exception:
            await interaction.response.send_message(
                "❌ Format must be DD-MM-YYYY",
                ephemeral=True,
            )
            return

        # Defer before heavy log reading/parsing
        await interaction.response.defer(thinking=True)

        raw = await build_camp_raw_log(interaction.client, start, end)
        donations, supplies, ledger, deliveries = parse_log(raw)

        guild = interaction.guild
        id_to_name = _build_id_to_name(guild)

        sections = build_markdown_sections(
            donations, supplies, ledger, deliveries, id_to_name
        )

        # Donations is section index 0
        await _send_sections_interaction(
            interaction, [sections[0]], already_responded=True
        )

    # ---------------------------------------------------------
    # /camp_supplies
    # ---------------------------------------------------------
    @bot.tree.command(
        name="camp_supplies",
        description="Show only Supply Mission Summary.",
    )
    @app_commands.describe(
        start_str="Start date (DD-MM-YYYY)",
        end_str="End date (DD-MM-YYYY)",
    )
    async def camp_supplies_slash(
        interaction: discord.Interaction,
        start_str: str,
        end_str: str,
    ):
        if not await _ensure_command_channel(interaction):
            return

        try:
            start = datetime.strptime(start_str, "%d-%m-%Y").date()
            end = datetime.strptime(end_str, "%d-%m-%Y").date()
        except Exception:
            await interaction.response.send_message(
                "❌ Format: DD-MM-YYYY",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        raw = await build_camp_raw_log(interaction.client, start, end)
        donations, supplies, ledger, deliveries = parse_log(raw)

        guild = interaction.guild
        id_to_name = _build_id_to_name(guild)

        sections = build_markdown_sections(
            donations, supplies, ledger, deliveries, id_to_name
        )

        # Supplies is section index 1
        await _send_sections_interaction(
            interaction, [sections[1]], already_responded=True
        )

    # ---------------------------------------------------------
    # /camp_deliveries
    # ---------------------------------------------------------
    @bot.tree.command(
        name="camp_deliveries",
        description="Show only Delivery Mission Summary (stock sales).",
    )
    @app_commands.describe(
        start_str="Start date (DD-MM-YYYY)",
        end_str="End date (DD-MM-YYYY)",
    )
    async def camp_deliveries_slash(
        interaction: discord.Interaction,
        start_str: str,
        end_str: str,
    ):
        if not await _ensure_command_channel(interaction):
            return

        try:
            start = datetime.strptime(start_str, "%d-%m-%Y").date()
            end = datetime.strptime(end_str, "%d-%m-%Y").date()
        except Exception:
            await interaction.response.send_message(
                "❌ Format must be DD-MM-YYYY",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        raw = await build_camp_raw_log(interaction.client, start, end)
        donations, supplies, ledger, deliveries = parse_log(raw)

        guild = interaction.guild
        id_to_name = _build_id_to_name(guild)

        sections = build_markdown_sections(
            donations, supplies, ledger, deliveries, id_to_name
        )

        # Deliveries is section index 2
        await _send_sections_interaction(
            interaction, [sections[2]], already_responded=True
        )

    # ---------------------------------------------------------
    # /camp_ledger
    # ---------------------------------------------------------
    @bot.tree.command(
        name="camp_ledger",
        description="Show only Ledger Transactions.",
    )
    @app_commands.describe(
        start_str="Start date (DD-MM-YYYY)",
        end_str="End date (DD-MM-YYYY)",
    )
    async def camp_ledger_slash(
        interaction: discord.Interaction,
        start_str: str,
        end_str: str,
    ):
        if not await _ensure_command_channel(interaction):
            return

        try:
            start = datetime.strptime(start_str, "%d-%m-%Y").date()
            end = datetime.strptime(end_str, "%d-%m-%Y").date()
        except Exception:
            await interaction.response.send_message(
                "❌ Date must be DD-MM-YYYY",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        raw = await build_camp_raw_log(interaction.client, start, end)
        donations, supplies, ledger, deliveries = parse_log(raw)

        guild = interaction.guild
        id_to_name = _build_id_to_name(guild)

        sections = build_markdown_sections(
            donations, supplies, ledger, deliveries, id_to_name
        )

        # Ledger is section index 3
        await _send_sections_interaction(
            interaction, [sections[3]], already_responded=True
        )
