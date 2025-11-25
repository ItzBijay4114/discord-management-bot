# main.py
import os
import asyncio
from dotenv import load_dotenv

import discord
from discord.ext import commands

load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

class DevBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            application_id=None,  # optional if you want
        )

    async def setup_hook(self):
        # Load cogs
        await self.load_extension("cogs.config_cog")
        await self.load_extension("cogs.tasks")
        await self.load_extension("cogs.devpanel")
        await self.load_extension("cogs.ai_helper")

        # Sync slash commands
        await self.tree.sync()
        print("Slash commands synced.")

bot = DevBot()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN missing from .env")
    bot.run(DISCORD_TOKEN)

if __name__ == "__main__":
    main()
