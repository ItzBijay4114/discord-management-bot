# cogs/ai_helper.py
import os
from typing import Literal

import aiohttp
import discord
from discord.ext import commands
from discord import app_commands

from utils.storage import get_server_config

GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
GEMINI_MODEL = "gemini-1.5-flash"  # adjust as needed

class AIHelperView(discord.ui.View):
    def __init__(self, cog: "AIHelperCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Brainstorm Ideas", style=discord.ButtonStyle.primary, custom_id="ai_brainstorm")
    async def brainstorm(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AIRequestModal(self.cog, mode="brainstorm")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Break Down Task", style=discord.ButtonStyle.secondary, custom_id="ai_breakdown")
    async def breakdown(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AIRequestModal(self.cog, mode="breakdown")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Ask General Question", style=discord.ButtonStyle.success, custom_id="ai_general")
    async def general(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = AIRequestModal(self.cog, mode="general")
        await interaction.response.send_modal(modal)


class AIRequestModal(discord.ui.Modal):
    question = discord.ui.TextInput(
        label="Describe what you need help with",
        style=discord.TextStyle.paragraph,
        max_length=2000
    )

    def __init__(self, cog: "AIHelperCog", mode: Literal["brainstorm", "breakdown", "general"]):
        title_map = {
            "brainstorm": "Brainstorm Ideas",
            "breakdown": "Break Down Task",
            "general": "Ask General Question"
        }
        super().__init__(title=title_map[mode])
        self.cog = cog
        self.mode = mode

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.handle_ai_request(interaction, self.mode, self.question.value)


class AIHelperCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api_key = os.getenv(GEMINI_API_KEY_ENV)

    @app_commands.command(name="aipanel", description="Post the AI helper panel (Gemini) in this channel.")
    async def aipanel(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        cfg = get_server_config(guild.id)
        if not cfg.get("ai_enabled", False):
            return await interaction.response.send_message(
                "AI helper is disabled. Ask an admin to run `/config ai enabled:true`.",
                ephemeral=True
            )

        if not self.api_key:
            return await interaction.response.send_message(
                "AI API key not configured on the server. (Missing GEMINI_API_KEY).",
                ephemeral=True
            )

        view = AIHelperView(self)
        embed = discord.Embed(
            title="AI Helper (Gemini)",
            description=(
                "Use the buttons below to:\n"
                "- Brainstorm new ideas (mechanics, levels, systems)\n"
                "- Break down complex tasks into steps\n"
                "- Ask general questions about game dev / scripting\n\n"
                "Responses will appear publicly in this channel."
            ),
            color=discord.Color.purple()
        )
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("AI panel created.", ephemeral=True)

    async def handle_ai_request(self, interaction: discord.Interaction, mode: str, text: str):
        guild = interaction.guild
        if guild:
            cfg = get_server_config(guild.id)
            if not cfg.get("ai_enabled", False):
                return await interaction.response.send_message(
                    "AI helper is disabled in this server.",
                    ephemeral=True
                )

        if not self.api_key:
            return await interaction.response.send_message(
                "AI API key is not configured on the bot.",
                ephemeral=True
            )

        await interaction.response.defer(thinking=True)

        system_prompt = ""
        if mode == "brainstorm":
            system_prompt = (
                "You are an AI assistant helping a Roblox game development team brainstorm ideas. "
                "Provide multiple concrete, creative ideas with bullet points or numbered lists."
            )
        elif mode == "breakdown":
            system_prompt = (
                "You are an AI assistant helping a Roblox game developer break down complex tasks. "
                "Return a list of clear, ordered steps, maybe with small notes or hints."
            )
        else:  # general
            system_prompt = (
                "You are an AI assistant helping a Roblox game developer with scripting, design, and workflow. "
                "Give concise but useful explanations with examples where necessary."
            )

        user_prompt = text.strip()

        try:
            response_text = await self.call_gemini_api(system_prompt, user_prompt)
        except Exception as e:
            return await interaction.followup.send(
                f"Error while contacting AI: {e}",
                ephemeral=True
            )

        embed = discord.Embed(
            title={
                "brainstorm": "AI Brainstorm Ideas",
                "breakdown": "AI Task Breakdown",
                "general": "AI Answer"
            }[mode],
            description=response_text[:4000],  # Discord limit
            color=discord.Color.purple()
        )
        embed.set_footer(text=f"Requested by {interaction.user}")

        await interaction.followup.send(embed=embed)

    async def call_gemini_api(self, system_prompt: str, user_prompt: str) -> str:
        """
        Minimal example of calling Gemini via REST.
        Adjust endpoint/model according to current Google AI API docs.
        """
        url = f"https://generativelanguage.googleapis.com/v1/models/{GEMINI_MODEL}:generateContent"
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key
        }
        payload = {
            "contents": [
                {
                    "role": "system",
                    "parts": [{"text": system_prompt}]
                },
                {
                    "role": "user",
                    "parts": [{"text": user_prompt}]
                }
            ]
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=headers) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"API error {resp.status}: {text}")
                data = await resp.json()

        # Parse the response; exact structure depends on API version
        # For Gemini, typical structure:
        # data["candidates"][0]["content"]["parts"][0]["text"]
        candidates = data.get("candidates", [])
        if not candidates:
            return "No response from AI."
        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        if not parts:
            return "No response from AI."
        return parts[0].get("text", "No text returned from AI.")

async def setup(bot: commands.Bot):
    await bot.add_cog(AIHelperCog(bot))
