# main.py
import os
import asyncio
from dotenv import load_dotenv

import discord
from discord.ext import commands
from aiohttp import web

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
        )

    async def setup_hook(self):
        await self.load_extension("cogs.config_cog")
        await self.load_extension("cogs.tasks")
        await self.load_extension("cogs.devpanel")
        await self.load_extension("cogs.ai_helper")

        await self.tree.sync()
        print("Slash commands synced.")


bot = DevBot()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")


# ---------- Minimal aiohttp web server for Render ----------

async def handle_root(request):
    return web.Response(text="Discord bot is running.", content_type="text/plain")


async def start_web_app():
    app = web.Application()
    app.add_routes([web.get("/", handle_root)])

    runner = web.AppRunner(app)
    await runner.setup()

    # Render provides the port in the PORT environment variable
    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server started on port {port}")


async def main_async():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN missing from environment or .env")

    # Run both the web server and the Discord bot concurrently
    await asyncio.gather(
        start_web_app(),
        bot.start(DISCORD_TOKEN)
    )


def main():
    asyncio.run(main_async())


if __name__ == "__main__":
    main()
