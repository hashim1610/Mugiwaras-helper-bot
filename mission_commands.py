# mission_commands.py

import discord
from discord.ext import commands
from discord import app_commands

import yaml
from pathlib import Path

# --------------------------------------------------------------
# LOAD CONFIG.YML AND CAMP LOG BOOK CHANNEL ID
# --------------------------------------------------------------
CONFIG_PATH = Path("config.yml")

if not CONFIG_PATH.exists():
    raise RuntimeError("config.yml not found next to mission_commands.py")

with CONFIG_PATH.open("r", encoding="utf-8") as f:
    CONFIG = yaml.safe_load(f) or {}

discord_cfg = CONFIG.get("discord", {})
camp_log_book_raw = discord_cfg.get("camp_log_book_channel_id")

if camp_log_book_raw is None:
    raise RuntimeError(
        "Missing 'discord.camp_log_book_channel_id' in config.yml"
    )

CAMP_LOG_BOOK_CHANNEL_ID = int(camp_log_book_raw)

MISSION_SEPARATOR = "-" * 53


# --------------------------------------------------------------
# CHANNEL CHECK — restrict commands to ONE channel
# --------------------------------------------------------------
def in_log_book_channel(interaction: discord.Interaction) -> bool:
    return interaction.channel_id == CAMP_LOG_BOOK_CHANNEL_ID


# --------------------------------------------------------------
# MAIN COG
# --------------------------------------------------------------
class MissionCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Slash command groups
    mission = app_commands.Group(
        name="mission",
        description="Mission utilities (supply & delivery)."
    )

    mission_legacy = app_commands.Group(
        name="mission_legacy",
        description="Backfill old missions manually."
    )

    # ----------------------------------------------------------
    # HELPER FUNCTIONS
    # ----------------------------------------------------------
    def build_mission_block(self, mission_type: str, participants: str) -> str:
        return (
            f"{mission_type}\n"
            f">> {participants}\n"
            f"{MISSION_SEPARATOR}"
        )

    # ----------------------------------------------------------
    # /mission supply
    # ----------------------------------------------------------
    @mission.command(
        name="supply",
        description="Post a SUPPLY MISSION line."
    )
    @app_commands.check(in_log_book_channel)
    @app_commands.describe(
        participants="Mention players (example: @Daddy [Owner] @Gerralt [Manager])"
    )
    async def mission_supply(
        self,
        interaction: discord.Interaction,
        participants: str
    ):
        text = self.build_mission_block("SUPPLY MISSION", participants)
        # 👇 Single public message, no ephemeral reply, no thread
        await interaction.response.send_message(text)

    # ----------------------------------------------------------
    # /mission delivery
    # ----------------------------------------------------------
    @mission.command(
        name="delivery",
        description="Post a DELIVERY MISSION line."
    )
    @app_commands.check(in_log_book_channel)
    @app_commands.describe(
        participants="Mention players (example: @Mikey [Manager] @Daddy [Owner])"
    )
    async def mission_delivery(
        self,
        interaction: discord.Interaction,
        participants: str
    ):
        text = self.build_mission_block("DELIVERY MISSION", participants)
        # 👇 Single public message
        await interaction.response.send_message(text)

    # ----------------------------------------------------------
    # /mission_legacy supply
    # ----------------------------------------------------------
    @mission_legacy.command(
        name="supply",
        description="Backfill a SUPPLY MISSION with a manual date."
    )
    @app_commands.check(in_log_book_channel)
    @app_commands.describe(
        date_text="Original date/time (example: '11/23/2025 4:05 PM')",
        participants="Mention players"
    )
    async def mission_supply_legacy(
        self,
        interaction: discord.Interaction,
        date_text: str,
        participants: str
    ):
        mission_text = self.build_mission_block("SUPPLY MISSION", participants)
        full_text = f"{date_text}\n{mission_text}"
        # 👇 Everyone sees the backfilled entry
        await interaction.response.send_message(full_text)

    # ----------------------------------------------------------
    # /mission_legacy delivery
    # ----------------------------------------------------------
    @mission_legacy.command(
        name="delivery",
        description="Backfill a DELIVERY MISSION with a manual date."
    )
    @app_commands.check(in_log_book_channel)
    @app_commands.describe(
        date_text="Original date/time (example: '12/05/2025 10:32 PM')",
        participants="Mention players"
    )
    async def mission_delivery_legacy(
        self,
        interaction: discord.Interaction,
        date_text: str,
        participants: str
    ):
        mission_text = self.build_mission_block("DELIVERY MISSION", participants)
        full_text = f"{date_text}\n{mission_text}"
        # 👇 Everyone sees the backfilled entry
        await interaction.response.send_message(full_text)


# --------------------------------------------------------------
# SETUP
# --------------------------------------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(MissionCommands(bot))
