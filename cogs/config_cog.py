# cogs/config_cog.py
import os
from typing import Optional

import discord
from discord.ext import commands
from discord import app_commands

from utils.storage import get_server_config, update_server_config

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"


class ConfigCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # Group: /config
    config_group = app_commands.Group(
        name="config",
        description="Configure the dev bot for this server.",
        default_permissions=discord.Permissions(administrator=True),
    )

    @config_group.command(name="channels", description="Set logs and task channels.")
    @app_commands.describe(
        logs_channel="Channel for logging actions",
        tasks_channel="Channel where task panels/messages are posted",
        dev_category="Category where private dev channels are created"
    )
    async def config_channels(
        self,
        interaction: discord.Interaction,
        logs_channel: Optional[discord.TextChannel],
        tasks_channel: Optional[discord.TextChannel],
        dev_category: Optional[discord.CategoryChannel]
    ):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True
            )

        cfg = get_server_config(guild.id)
        if logs_channel:
            cfg["logs_channel_id"] = logs_channel.id
        if tasks_channel:
            cfg["tasks_channel_id"] = tasks_channel.id
        if dev_category:
            cfg["dev_category_id"] = dev_category.id

        update_server_config(guild.id, **cfg)
        await interaction.response.send_message(
            "Configuration updated.",
            ephemeral=True
        )

    @config_group.command(name="ai", description="Enable/disable AI helper.")
    @app_commands.describe(enabled="Enable (true) or disable (false) AI helper.")
    async def config_ai(
        self,
        interaction: discord.Interaction,
        enabled: bool
    ):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True
            )

        if enabled and not os.getenv(GEMINI_API_KEY_ENV):
            return await interaction.response.send_message(
                "AI cannot be enabled: GEMINI_API_KEY missing in environment.",
                ephemeral=True
            )

        cfg = get_server_config(guild.id)
        cfg["ai_enabled"] = enabled
        update_server_config(guild.id, **cfg)
        await interaction.response.send_message(
            f"AI helper {'enabled' if enabled else 'disabled'} for this server.",
            ephemeral=True
        )

    @config_group.command(name="show", description="Show current config.")
    async def config_show(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message(
                "This command can only be used in a server.",
                ephemeral=True
            )

        cfg = get_server_config(guild.id)
        logs_id = cfg.get("logs_channel_id")
        tasks_id = cfg.get("tasks_channel_id")
        dev_cat_id = cfg.get("dev_category_id")
        ai_enabled = cfg.get("ai_enabled", False)

        desc = []
        desc.append(f"Logs channel: <#{logs_id}>" if logs_id else "Logs channel: not set")
        desc.append(f"Tasks channel: <#{tasks_id}>" if tasks_id else "Tasks channel: not set")
        desc.append(f"Dev category: <#{dev_cat_id}>" if dev_cat_id else "Dev category: not set")
        desc.append(f"AI enabled: {ai_enabled}")

        embed = discord.Embed(
            title="Server Configuration",
            description="\n".join(desc),
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    cog = ConfigCog(bot)
    bot.tree.add_command(cog.config_group)
    await bot.add_cog(cog)
