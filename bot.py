# bot.py
import os
import asyncio
import discord
from discord.ext import commands

from camp_commands import register_camp_commands
from ranch_commands import RanchCommands  # /ranch group

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("❌ Environment variable TOKEN not found!")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# Register all slash commands BEFORE syncing
register_camp_commands(bot)

# Register the /ranch command group
bot.tree.add_command(RanchCommands(bot))


@bot.event
async def on_ready():
    print(f"✔ Logged in as {bot.user} (ID {bot.user.id})")

    # Print commands we see locally
    print("Registered application commands (local):")
    for cmd in bot.tree.walk_commands():
        print(f" - /{cmd.name}")

    # Sync slash commands globally
    try:
        synced = await bot.tree.sync()
        print(f"✔ Globally synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")


async def main():
    async with bot:
        # 👇 Load the mission command set (mission + mission_legacy)
        # If mission_commands.py is next to bot.py, this is correct:
        await bot.load_extension("mission_commands")

        # If instead you put it in a "cogs" folder as cogs/mission_commands.py,
        # use this line instead:
        # await bot.load_extension("cogs.mission_commands")

        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
