# bot.py
import os
import discord
from discord.ext import commands

from camp_commands import register_camp_commands

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise RuntimeError("❌ Environment variable TOKEN not found!")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✔ Logged in as {bot.user} (ID {bot.user.id})")
    
    # Register slash commands
    register_camp_commands(bot)

    # Sync slash commands globally
    try:
        synced = await bot.tree.sync()
        print(f"✔ Globally synced {len(synced)} slash commands")
    except Exception as e:
        print(f"❌ Failed to sync slash commands: {e}")


if __name__ == "__main__":
    bot.run(TOKEN)
