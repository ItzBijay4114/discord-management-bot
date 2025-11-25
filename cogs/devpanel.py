# cogs/devpanel.py
from typing import List

import discord
from discord.ext import commands
from discord import app_commands

from utils.storage import get_server_config, update_server_config


class DevSelect(discord.ui.Select):
    def __init__(self, cog: "DevPanelCog", devs: List[int]):
        self.cog = cog
        options = [
            discord.SelectOption(label=str(dev_id), description="Developer", value=str(dev_id))
            for dev_id in devs
        ]
        super().__init__(
            placeholder="Select a developer to contact...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="dev_select"
        )

    async def callback(self, interaction: discord.Interaction):
        dev_id = int(self.values[0])
        await self.cog.handle_open_dev_channel(interaction, dev_id)


class DevPanelView(discord.ui.View):
    def __init__(self, cog: "DevPanelCog", dev_ids: List[int]):
        super().__init__(timeout=None)
        self.cog = cog
        self.add_item(DevSelect(cog, dev_ids))


class DevPanelCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    dev_group = app_commands.Group(
        name="devpanel",
        description="Configure and use the dev contact panel."
    )

    @dev_group.command(name="add", description="Add a developer to the dev contact list.")
    @app_commands.describe(user="Developer to add")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def add_dev(self, interaction: discord.Interaction, user: discord.Member):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        cfg = get_server_config(guild.id)
        devs = cfg.get("dev_ids", [])
        if user.id not in devs:
            devs.append(user.id)
        cfg["dev_ids"] = devs
        update_server_config(guild.id, **cfg)

        await interaction.response.send_message(f"{user.mention} added as a dev contact.", ephemeral=True)

    @dev_group.command(name="remove", description="Remove a developer from the dev contact list.")
    @app_commands.describe(user="Developer to remove")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def remove_dev(self, interaction: discord.Interaction, user: discord.Member):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        cfg = get_server_config(guild.id)
        devs = cfg.get("dev_ids", [])
        if user.id in devs:
            devs.remove(user.id)
        cfg["dev_ids"] = devs
        update_server_config(guild.id, **cfg)

        await interaction.response.send_message(f"{user.mention} removed from dev contacts.", ephemeral=True)

    @dev_group.command(name="panel", description="Post the dev contact panel in this channel.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def dev_panel(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        cfg = get_server_config(guild.id)
        devs = cfg.get("dev_ids", [])
        if not devs:
            return await interaction.response.send_message("No developers configured. Use `/devpanel add` first.", ephemeral=True)

        view = DevPanelView(self, devs)
        embed = discord.Embed(
            title="Contact a Developer",
            description=(
                "Use the dropdown below to open a private channel with a developer.\n"
                "Only you, the selected developer, and optionally admins will see it."
            ),
            color=discord.Color.green()
        )
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Dev panel created.", ephemeral=True)

    async def handle_open_dev_channel(self, interaction: discord.Interaction, dev_id: int):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        cfg = get_server_config(guild.id)
        cat_id = cfg.get("dev_category_id")
        if not cat_id:
            return await interaction.response.send_message(
                "Dev category not configured. Ask an admin to set it with `/config channels`.",
                ephemeral=True
            )

        category = guild.get_channel(cat_id)
        if not category or not isinstance(category, discord.CategoryChannel):
            return await interaction.response.send_message("Configured dev category not found.", ephemeral=True)

        dev_member = guild.get_member(dev_id)
        if not dev_member:
            return await interaction.response.send_message("Developer not found in this server.", ephemeral=True)

        user = interaction.user

        # Create a private channel
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
            dev_member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }

        channel_name = f"dev-{user.name[:10]}-{dev_member.name[:10]}"
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"Private dev channel between {user} and {dev_member}"
        )

        await channel.send(
            content=(
                f"Private dev channel opened.\n"
                f"- User: {user.mention}\n"
                f"- Developer: {dev_member.mention}\n\n"
                f"Use this channel to discuss your task or project in detail."
            )
        )

        await interaction.response.send_message(
            f"Private dev channel created: {channel.mention}",
            ephemeral=True
        )

        # Log it
        from cogs.tasks import TasksCog  # to reuse log_action style is messy; so do direct log
        from utils.storage import get_server_config
        cfg2 = get_server_config(guild.id)
        logs_id = cfg2.get("logs_channel_id")
        if logs_id:
            logs_channel = guild.get_channel(logs_id)
            if logs_channel and isinstance(logs_channel, discord.TextChannel):
                embed = discord.Embed(
                    title="Private Dev Channel Created",
                    description=(
                        f"Channel: {channel.mention}\n"
                        f"User: {user.mention}\n"
                        f"Dev: {dev_member.mention}"
                    ),
                    color=discord.Color.dark_green()
                )
                await logs_channel.send(embed=embed)


async def setup(bot: commands.Bot):
    cog = DevPanelCog(bot)
    bot.tree.add_command(cog.dev_group)
    await bot.add_cog(cog)
