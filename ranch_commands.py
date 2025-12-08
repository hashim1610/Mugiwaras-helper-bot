# ranch_commands.py
from __future__ import annotations

from datetime import datetime, date
import io
import os

import discord
from discord import app_commands
import yaml

from chat_read import build_ranch_raw_log
from ranch_out import (
    parse_ranch_log,
    build_ranch_markdown_sections,          # still used by /ranch player
    build_ranchsummary_csv_bytes,
    build_ranch_player_markdown_sections,
)

# Commands only allowed here (same as camp_commands.py)
COMMAND_CHANNEL_ID = 1442401333692072027

CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yml")


def _chunk_text(text: str, limit: int = 1800):
    """
    Yield chunks of `text` that fit within the discord message limit
    (leaving room for ``` fencing and a bit of padding).
    """
    out = ""
    for ln in text.splitlines():
        if len(out) + len(ln) + 1 > limit:
            if out:
                yield out
            out = ""
        out += ln + "\n"
    if out:
        yield out


async def _send_sections_interaction(
    interaction: discord.Interaction,
    sections: list[str],
    already_responded: bool = False,
):
    """
    Send a list of markdown sections as separate ```md blocks,
    obeying Discord's 'only one initial response' rule.
    """
    first_send = not already_responded

    for sec in sections:
        if not sec or not sec.strip():
            continue

        for chunk in _chunk_text(sec):
            msg = f"```md\n{chunk}\n```"

            if first_send:
                # If we've not replied yet, use the initial response.
                if already_responded:
                    await interaction.followup.send(msg)
                else:
                    await interaction.response.send_message(msg)
                first_send = False
            else:
                await interaction.followup.send(msg)


def _load_prices() -> dict:
    """
    Load prices for egg and milk from config.yml.
    Defaults to 1.0 if missing.
    """
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f) or {}
    except Exception as e:
        print(f"⚠ Failed to load config.yml in _load_prices: {e}")
        cfg = {}

    prices_cfg = cfg.get("prices", {}) or {}

    return {
        "egg": float(prices_cfg.get("egg", 1.0)),
        "milk": float(prices_cfg.get("milk", 1.0)),
    }


def _save_prices(prices: dict) -> None:
    """
    Save prices for egg and milk back to config.yml.
    Keeps other config sections intact.
    """
    try:
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = yaml.safe_load(f) or {}
        except FileNotFoundError:
            cfg = {}
        except Exception as e:
            print(f"⚠ Failed to load config.yml in _save_prices: {e}")
            cfg = {}

        if not isinstance(cfg, dict):
            cfg = {}

        if "prices" not in cfg or not isinstance(cfg["prices"], dict):
            cfg["prices"] = {}

        cfg["prices"]["egg"] = float(prices.get("egg", 1.0))
        cfg["prices"]["milk"] = float(prices.get("milk", 1.0))

        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, sort_keys=False)

    except Exception as e:
        print(f"❌ Failed to save prices to config.yml: {e}")


def _parse_ddmmyyyy(s: str) -> date | None:
    """
    Parse a date string in DD-MM-YYYY format.
    Returns a date or None if invalid.
    """
    try:
        return datetime.strptime(s.strip(), "%d-%m-%Y").date()
    except Exception:
        return None


class RanchCommands(app_commands.Group):
    """
    Slash command group: /ranch ...
    Register this group on your bot like:

        bot.tree.add_command(RanchCommands(bot))
    """

    def __init__(self, bot: discord.Client):
        super().__init__(name="ranch", description="Ranch log commands")
        self.bot = bot

    # -----------------------------
    # /ranch summary (with date range, CSV only)
    # -----------------------------
    @app_commands.command(
        name="summary",
        description="Summarise ranch logs in a date range (DD-MM-YYYY) and output CSV only.",
    )
    @app_commands.describe(
        start="Start date (DD-MM-YYYY, inclusive)",
        end="End date (DD-MM-YYYY, inclusive)",
    )
    async def ranch_summary(
        self,
        interaction: discord.Interaction,
        start: str,
        end: str,
    ):
        # Restrict usage to the command channel, just like camp_commands.py
        if interaction.channel_id != COMMAND_CHANNEL_ID:
            await interaction.response.send_message(
                f"This command can only be used in <#{COMMAND_CHANNEL_ID}>.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command must be used in a guild.", ephemeral=True
            )
            return

        # Parse dates before deferring (so we can send errors cleanly)
        start_date = _parse_ddmmyyyy(start)
        end_date = _parse_ddmmyyyy(end)

        if start_date is None:
            await interaction.response.send_message(
                f"Invalid start date format: `{start}`. Use **DD-MM-YYYY**.",
                ephemeral=True,
            )
            return

        if end_date is None:
            await interaction.response.send_message(
                f"Invalid end date format: `{end}`. Use **DD-MM-YYYY**.",
                ephemeral=True,
            )
            return

        if end_date < start_date:
            await interaction.response.send_message(
                "End date must be **on or after** start date.",
                ephemeral=True,
            )
            return

        # Heavy work -> defer
        await interaction.response.defer(thinking=True)
        # From this point on we must use interaction.followup.*

        raw_log: str = await build_ranch_raw_log(
            self.bot,
            start_date=start_date,
            end_date=end_date,
        )

        events = parse_ranch_log(raw_log)

        if not events:
            await interaction.followup.send(
                f"No ranch events found between **{start}** and **{end}**."
            )
            return

        prices = _load_prices()
        csv_bytes = build_ranchsummary_csv_bytes(events, prices)

        # CSV filename in DD-MM-YYYY
        today_str = datetime.utcnow().strftime("%d-%m-%Y")
        csv_filename = f"ranch_summary_{start}_to_{end}_{today_str}.csv".replace(" ", "_")
        csv_file = discord.File(
            io.BytesIO(csv_bytes),
            filename=csv_filename,
        )
        await interaction.followup.send(
            content=(
                f"Ranch summary CSV for **{start}** to **{end}**.\n"
                f"Current prices: egg={prices['egg']:.2f}, milk={prices['milk']:.2f}"
            ),
            file=csv_file,
        )

    # -----------------------------
    # /ranch player
    # -----------------------------
    @app_commands.command(
        name="player",
        description="Show ranch stats for a specific player (all time).",
    )
    @app_commands.describe(
        member="Player to get ranch stats for",
    )
    async def ranch_player(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
    ):
        # Restrict usage to the command channel
        if interaction.channel_id != COMMAND_CHANNEL_ID:
            await interaction.response.send_message(
                f"This command can only be used in <#{COMMAND_CHANNEL_ID}>.",
                ephemeral=True,
            )
            return

        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message(
                "This command must be used in a guild.", ephemeral=True
            )
            return

        # Might be heavy depending on log size -> defer
        await interaction.response.defer(thinking=True)

        raw_log: str = await build_ranch_raw_log(
            self.bot,
            start_date=None,
            end_date=None,
        )

        events = parse_ranch_log(raw_log)

        if not events:
            await interaction.followup.send("No ranch events found in the scanned logs.")
            return

        prices = _load_prices()

        sections = build_ranch_player_markdown_sections(
            events,
            discord_id=str(member.id),
            user_mention=member.mention,
            prices=prices,
        )

        if not sections:
            await interaction.followup.send(
                f"No ranch events found for {member.mention}."
            )
            return

        await _send_sections_interaction(
            interaction,
            sections,
            already_responded=True,
        )

    # -----------------------------
    # /ranch setprice
    # -----------------------------
    @app_commands.command(
        name="setprice",
        description="Set the price for eggs or milk. (Only 'egg' and 'milk' are allowed.)",
    )
    @app_commands.describe(
        item="Item to set price for ('egg' or 'milk')",
        value="Price per unit (must be > 0)",
    )
    async def ranch_setprice(
        self,
        interaction: discord.Interaction,
        item: str,
        value: float,
    ):
        # Restrict usage to the command channel
        if interaction.channel_id != COMMAND_CHANNEL_ID:
            await interaction.response.send_message(
                f"This command can only be used in <#{COMMAND_CHANNEL_ID}>.",
                ephemeral=True,
            )
            return

        item_key = item.lower().strip()
        if item_key in ("egg", "eggs"):
            item_key = "egg"
        elif item_key in ("milk", "milks"):
            item_key = "milk"
        else:
            await interaction.response.send_message(
                "Item must be either **egg** or **milk**.",
                ephemeral=True,
            )
            return

        if value <= 0:
            await interaction.response.send_message(
                "Price must be **greater than 0**.",
                ephemeral=True,
            )
            return

        prices = _load_prices()
        prices[item_key] = float(value)
        _save_prices(prices)

        await interaction.response.send_message(
            f"Set price of **{item_key}** to **{value:.2f}**.\n"
            f"Current prices: egg={prices['egg']:.2f}, milk={prices['milk']:.2f}",
            ephemeral=True,
        )
