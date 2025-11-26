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
        super().__init__(command_prefix="!", intents=intents)

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

    port = int(os.environ.get("PORT", "10000"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Web server started on port {port}")


async def start_everything():
    # Start web server without blocking the bot
    asyncio.create_task(start_web_app())
    # Now let discord.py manage reconnection with bot.run
    # We don't call bot.run here because it's blocking and not awaitable; instead,
    # we start this coroutine from main() before bot.run.
    # This function just ensures web app is started early.


def main():
    if not DISCORD_TOKEN:
        raise RuntimeError("DISCORD_TOKEN missing from environment or .env")

    # Start the web app in a background event loop and then run the bot using bot.run
    async def runner():
        await start_everything()

    # Create a loop, start web app, then run bot using that loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(runner())

    # bot.run creates and manages its own internal loop; we call it after web app is running
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
