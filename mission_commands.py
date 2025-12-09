# mission_commands.py

import discord
from discord.ext import commands
from discord import app_commands

# --------------------------------------------------------------
# LOAD CONFIG (adjust import if your project loads config differently)
# --------------------------------------------------------------
from config import CONFIG   # <--- change this if needed

CAMP_LOG_BOOK_CHANNEL_ID = int(CONFIG["camp_log_book_channel_id"])

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
        description="Mission utilities (supply, delivery, week banners)."
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

    def build_week_banner(self, week: int, year: int, opened: bool) -> str:
        if opened:
            status_line = f"-🟢\n WEEK {week} of {year} - OPENED 🟢\n-"
        else:
            status_line = f"-❌\n WEEK {week} of {year} - CLOSED ❌\n-"

        return (
            "---------------------------------------\n"
            f"{status_line}\n"
            "---------------------------------------"
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
        await interaction.channel.send(text)

        await interaction.response.send_message(
            "📦 Logged SUPPLY MISSION.",
            ephemeral=True
        )

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
        await interaction.channel.send(text)

        await interaction.response.send_message(
            "🚚 Logged DELIVERY MISSION.",
            ephemeral=True
        )

    # ----------------------------------------------------------
    # /mission week_open
    # ----------------------------------------------------------
    @mission.command(
        name="week_open",
        description="Post the WEEK OPENED banner."
    )
    @app_commands.check(in_log_book_channel)
    @app_commands.describe(
        week="ISO week number",
        year="Year (leave empty to use current year)"
    )
    async def mission_week_open(
        self,
        interaction: discord.Interaction,
        week: int,
        year: int | None = None
    ):
        from datetime import datetime
        if year is None:
            year = datetime.utcnow().year

        text = self.build_week_banner(week, year, opened=True)
        await interaction.channel.send(text)

        await interaction.response.send_message(
            f"🟢 Logged WEEK {week} OPENED.",
            ephemeral=True
        )

    # ----------------------------------------------------------
    # /mission week_close
    # ----------------------------------------------------------
    @mission.command(
        name="week_close",
        description="Post the WEEK CLOSED banner."
    )
    @app_commands.check(in_log_book_channel)
    @app_commands.describe(
        week="ISO week number",
        year="Year (leave empty to use current year)"
    )
    async def mission_week_close(
        self,
        interaction: discord.Interaction,
        week: int,
        year: int | None = None
    ):
        from datetime import datetime
        if year is None:
            year = datetime.utcnow().year

        text = self.build_week_banner(week, year, opened=False)
        await interaction.channel.send(text)

        await interaction.response.send_message(
            f"❌ Logged WEEK {week} CLOSED.",
            ephemeral=True
        )

    # ----------------------------------------------------------
    # /mission_legacy supply
    # ----------------------------------------------------------
    @mission_legacy.command(
        name="supply",
        description="Backfill an older SUPPLY MISSION with a manual date."
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

        await interaction.channel.send(full_text)

        await interaction.response.send_message(
            f"📦 Backfilled SUPPLY MISSION for {date_text}.",
            ephemeral=True
        )

    # ----------------------------------------------------------
    # /mission_legacy delivery
    # ----------------------------------------------------------
    @mission_legacy.command(
        name="delivery",
        description="Backfill an older DELIVERY MISSION with a manual date."
    )
    @app_commands.check(in_log_book_channel)
    @app_commands.describe(
        date_text="Original date/time",
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

        await interaction.channel.send(full_text)

        await interaction.response.send_message(
            f"🚚 Backfilled DELIVERY MISSION for {date_text}.",
            ephemeral=True
        )


# --------------------------------------------------------------
# SETUP
# --------------------------------------------------------------
async def setup(bot: commands.Bot):
    await bot.add_cog(MissionCommands(bot))
