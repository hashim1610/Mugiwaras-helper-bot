import os
import discord
from discord.ext import commands

# Get token from Railway environment variables
TOKEN = os.getenv("TOKEN")

intents = discord.Intents.default()
intents.message_content = True  # important so bot can read messages

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")


@bot.command()
async def count(ctx, *, text: str):
    chars = len(text)
    words = len(text.split())
    await ctx.send(f"Characters: {chars}, Words: {words}")


bot.run(TOKEN)
