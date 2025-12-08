# camp_commands.py
from datetime import datetime
import io

import discord
from discord import app_commands

from chat_read import build_camp_raw_log
from camp_out import (
    parse_log,
    build_markdown_sections,
    build_delivery_table,
    build_logsummary_csv_bytes,
)

# Commands only allowed here:
COMMAND_CHANNEL_ID = 1442401333692072027


def _build_id_to_name(guild: discord.Guild | None):
    if not guild:
        return {}
    return {str(m.id): m.display_name for m in guild.members}


def _chunk_text(text, limit=1800):
    out = ""
    for ln in text.splitlines():
        if len(out) + len(ln) + 1 > limit:
            yield out
            out = ""
        out += ln + "\n"
    if out:
        yield out


async def _send_sections_interaction(
    interaction: discord.Interaction,
    sections,
    already_responded: bool = False,
):
    """
    Send one or more markdown sections.
    - If already_responded is False: first chunk uses interaction.response.send_message()
    - If already_responded is True: all chunks use interaction.followup.send()
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


def register_camp_commands(bot: discord.Client):
    """
    Attach all / commands to the given bot.
    """

    @bot.tree.command(
        name="logsummary_range",
        description="Summarize logs between two dates (CSV file output)",
    )
    @app_commands.describe(
        start_str="Start date (DD-MM-YYYY)",
        end_str="End date (DD-MM-YYYY)",
    )
    async def logsummary_range_slash(
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
                "❌ Use format: `DD-MM-YYYY` for both dates.",
                ephemeral=True,
            )
            return

        # Defer so we don't hit the 3s timeout
        await interaction.response.defer(thinking=True)

        raw = await build_camp_raw_log(interaction.client, start, end)
        guild = interaction.guild
        id_to_name = _build_id_to_name(guild)

        donations, supplies, ledger, deliveries = parse_log(raw)
        csv_bytes = build_logsummary_csv_bytes(donations, supplies, ledger, id_to_name)
        filename = f"logsummary_{start_str}_to_{end_str}.csv"
        file = discord.File(io.BytesIO(csv_bytes), filename=filename)

        await interaction.followup.send(
            "📄 Here is your CSV log summary:",
            file=file,
        )

    @bot.tree.command(
        name="logdebug_range",
        description="Debug + summarize logs between two dates",
    )
    @app_commands.describe(
        start_str="Start date (DD-MM-YYYY)",
        end_str="End date (DD-MM-YYYY)",
    )
    async def logdebug_range_slash(
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
                "❌ Use format: `DD-MM-YYYY` for both dates.",
                ephemeral=True,
            )
            return

        raw = await build_camp_raw_log(interaction.client, start, end)

        msg = f"Fetched {len(raw)} chars"
        preview = raw[:800] or "(no text)"
        msg_preview = f"{msg}\n```text\n{preview}\n```"
        await interaction.response.send_message(msg_preview)

        donations, supplies, ledger, deliveries = parse_log(raw)
        await interaction.followup.send(
            "Parsed:\nDonations: %d\nSupplies: %d\nLedger: %d\nDeliveries: %d"
            % (len(donations), len(supplies), len(ledger), len(deliveries))
        )

        guild = interaction.guild
        id_to_name = _build_id_to_name(guild)
        sections = build_markdown_sections(donations, supplies, ledger, id_to_name)

        # Already responded once, so only use followups now
        await _send_sections_interaction(
            interaction, sections, already_responded=True
        )

    @bot.tree.command(
        name="logdonations_range",
        description="Show only Donations section for a date range",
    )
    @app_commands.describe(
        start_str="Start date (DD-MM-YYYY)",
        end_str="End date (DD-MM-YYYY)",
    )
    async def logdonations_range_slash(
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
                "❌ Use format: `DD-MM-YYYY` for both dates.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        raw = await build_camp_raw_log(interaction.client, start, end)
        guild = interaction.guild
        id_to_name = _build_id_to_name(guild)
        donations, supplies, ledger, deliveries = parse_log(raw)
        sections = build_markdown_sections(donations, supplies, ledger, id_to_name)
        donations_sec = [sections[0]]

        await _send_sections_interaction(interaction, donations_sec, already_responded=True)

    @bot.tree.command(
        name="logtotals_range",
        description="Show only Overall Totals for a date range",
    )
    @app_commands.describe(
        start_str="Start date (DD-MM-YYYY)",
        end_str="End date (DD-MM-YYYY)",
    )
    async def logtotals_range_slash(
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
                "❌ Use format: `DD-MM-YYYY` for both dates.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        raw = await build_camp_raw_log(interaction.client, start, end)
        guild = interaction.guild
        id_to_name = _build_id_to_name(guild)
        donations, supplies, ledger, deliveries = parse_log(raw)
        sections = build_markdown_sections(donations, supplies, ledger, id_to_name)
        totals_sec = [sections[1]]

        await _send_sections_interaction(interaction, totals_sec, already_responded=True)

    @bot.tree.command(
        name="logsupply_range",
        description="Show only Supply section for a date range",
    )
    @app_commands.describe(
        start_str="Start date (DD-MM-YYYY)",
        end_str="End date (DD-MM-YYYY)",
    )
    async def logsupply_range_slash(
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
                "❌ Use format: `DD-MM-YYYY` for both dates.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        raw = await build_camp_raw_log(interaction.client, start, end)
        guild = interaction.guild
        id_to_name = _build_id_to_name(guild)
        donations, supplies, ledger, deliveries = parse_log(raw)
        sections = build_markdown_sections(donations, supplies, ledger, id_to_name)
        supply_sec = [sections[2]]

        await _send_sections_interaction(interaction, supply_sec, already_responded=True)

    @bot.tree.command(
        name="logledger_range",
        description="Show only Ledger section for a date range",
    )
    @app_commands.describe(
        start_str="Start date (DD-MM-YYYY)",
        end_str="End date (DD-MM-YYYY)",
    )
    async def logledger_range_slash(
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
                "❌ Use format: `DD-MM-YYYY` for both dates.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        raw = await build_camp_raw_log(interaction.client, start, end)
        guild = interaction.guild
        id_to_name = _build_id_to_name(guild)
        donations, supplies, ledger, deliveries = parse_log(raw)
        sections = build_markdown_sections(donations, supplies, ledger, id_to_name)
        ledger_sec = [sections[3]]

        await _send_sections_interaction(interaction, ledger_sec, already_responded=True)

    @bot.tree.command(
        name="logdelivery_range",
        description="Show delivery missions (stock sales) for a date range",
    )
    @app_commands.describe(
        start_str="Start date (DD-MM-YYYY)",
        end_str="End date (DD-MM-YYYY)",
    )
    async def logdelivery_range_slash(
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
                "❌ Use format: `DD-MM-YYYY` for both dates.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(thinking=True)

        raw = await build_camp_raw_log(interaction.client, start, end)
        guild = interaction.guild
        id_to_name = _build_id_to_name(guild)
        donations, supplies, ledger, deliveries = parse_log(raw)

        delivery_table = build_delivery_table(deliveries, id_to_name)
        await _send_sections_interaction(
            interaction, [delivery_table], already_responded=True
        )
