# cogs/tasks.py
from typing import Optional, List

import discord
from discord.ext import commands
from discord import app_commands

from utils.storage import (
    get_server_config,
    create_task,
    update_task,
    get_task,
    list_tasks,
    get_guild_tasks,
    save_guild_tasks,
)


class TaskCreateModal(discord.ui.Modal, title="Create New Task"):
    title_input = discord.ui.TextInput(
        label="Task Title",
        placeholder="e.g. Implement enemy AI behavior",
        max_length=100
    )
    description_input = discord.ui.TextInput(
        label="Task Description",
        style=discord.TextStyle.paragraph,
        placeholder="Describe the task details, requirements, notes...",
        max_length=2000
    )
    priority_input = discord.ui.TextInput(
        label="Priority (Low/Medium/High)",
        placeholder="Medium",
        max_length=20,
        required=False
    )

    def __init__(self, cog: "TasksCog", channel: discord.TextChannel):
        super().__init__()
        self.cog = cog
        self.channel = channel

    async def on_submit(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message(
                "This must be used in a server.",
                ephemeral=True
            )

        cfg = get_server_config(guild.id)
        tasks_channel_id = cfg.get("tasks_channel_id")
        if not tasks_channel_id:
            return await interaction.response.send_message(
                "Tasks channel not configured. Ask an admin to run `/config channels`.",
                ephemeral=True
            )

        tasks_channel = guild.get_channel(tasks_channel_id)
        if not tasks_channel:
            return await interaction.response.send_message(
                "Configured tasks channel not found.",
                ephemeral=True
            )

        priority = self.priority_input.value.strip() or "Medium"
        creator = interaction.user

        # Create task entry
        task = create_task(
            guild_id=guild.id,
            creator_id=creator.id,
            title=self.title_input.value,
            description=self.description_input.value,
            priority=priority,
        )

        task_id = task["id"]

        embed = discord.Embed(
            title=f"[Task #{task_id}] {task['title']}",
            description=task["description"],
            color=discord.Color.orange()
        )
        embed.add_field(name="Priority", value=priority, inline=True)
        embed.add_field(name="Status", value="Open", inline=True)
        embed.add_field(name="Assignee", value="Unassigned", inline=True)
        embed.set_footer(text=f"Created by {creator} (ID: {creator.id})")

        view = TaskMainView(self.cog, task_id)
        msg = await tasks_channel.send(embed=embed, view=view)

        # Update task with message/channel IDs
        update_task(
            guild_id=guild.id,
            task_id=task_id,
            message_id=msg.id,
            channel_id=tasks_channel.id
        )

        await interaction.response.send_message(
            f"Task #{task_id} created in {tasks_channel.mention}.",
            ephemeral=True
        )

        # Log creation
        await self.cog.log_action(
            guild,
            title=f"Task #{task_id} created",
            description=f"**Title:** {task['title']}\n**Creator:** {creator.mention}"
        )

        # Update task board (if configured)
        await self.cog.update_task_board(guild)


class TaskMainView(discord.ui.View):
    def __init__(self, cog: "TasksCog", task_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.task_id = task_id

    @discord.ui.button(label="Assign to Me", style=discord.ButtonStyle.primary, custom_id="task_assign_me")
    async def assign_me(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_assign_me(interaction, self.task_id)

    @discord.ui.button(label="Assign to Someone", style=discord.ButtonStyle.secondary, custom_id="task_assign_other")
    async def assign_other(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_assign_other(interaction, self.task_id)

    @discord.ui.button(label="Open Task Thread", style=discord.ButtonStyle.success, custom_id="task_open_thread")
    async def open_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_open_thread(interaction, self.task_id)


class AssignOtherModal(discord.ui.Modal, title="Assign Task to Someone"):
    user_id_input = discord.ui.TextInput(
        label="User ID or mention",
        placeholder="Paste user ID or mention the user in the channel.",
        max_length=50
    )

    def __init__(self, cog: "TasksCog", task_id: int):
        super().__init__()
        self.cog = cog
        self.task_id = task_id

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.handle_assign_other_submit(interaction, self.task_id, self.user_id_input.value)


class TaskThreadView(discord.ui.View):
    def __init__(self, cog: "TasksCog", task_id: int):
        super().__init__(timeout=None)
        self.cog = cog
        self.task_id = task_id

    @discord.ui.button(label="Mark In Progress", style=discord.ButtonStyle.primary, custom_id="task_in_progress")
    async def in_progress(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_status_change(interaction, self.task_id, "In Progress")

    @discord.ui.button(label="Submit Work", style=discord.ButtonStyle.secondary, custom_id="task_submit_work")
    async def submit_work(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_submit_work(interaction, self.task_id)

    @discord.ui.button(label="Mark Done", style=discord.ButtonStyle.success, custom_id="task_mark_done")
    async def mark_done(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cog.handle_mark_done(interaction, self.task_id)


class SubmitWorkModal(discord.ui.Modal, title="Submit Work for Task"):
    notes_input = discord.ui.TextInput(
        label="Summary / Notes (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=1000
    )

    def __init__(self, cog: "TasksCog", task_id: int):
        super().__init__()
        self.cog = cog
        self.task_id = task_id

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.handle_submit_work_notes(interaction, self.task_id, self.notes_input.value)


class TaskPanelView(discord.ui.View):
    def __init__(self, cog: "TasksCog"):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(label="Create Task", style=discord.ButtonStyle.success, custom_id="panel_create_task")
    async def create_task(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = TaskCreateModal(self.cog, interaction.channel)
        await interaction.response.send_modal(modal)


class TasksCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ===== Slash commands =====

    @app_commands.command(name="taskpanel", description="Post the Task Management Panel in this channel.")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def taskpanel(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message(
                "This command must be used in a server.",
                ephemeral=True
            )

        view = TaskPanelView(self)
        embed = discord.Embed(
            title="Task Management Panel",
            description=(
                "Use the buttons below to create and manage tasks.\n\n"
                "**Flow:**\n"
                "1. Click **Create Task**\n"
                "2. Assign the task and open its thread\n"
                "3. Use the thread buttons to update status and submit work\n"
                "4. When done, mark it completed (auto-logged & board updated)"
            ),
            color=discord.Color.blurple()
        )

        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("Task panel created.", ephemeral=True)

    @app_commands.command(name="tasks", description="List tasks for this server.")
    @app_commands.describe(
        status="Filter by status (Open, In Progress, Completed)",
        mine="Only show tasks assigned to you"
    )
    async def tasks_list(
        self,
        interaction: discord.Interaction,
        status: Optional[str] = None,
        mine: Optional[bool] = False
    ):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        all_tasks = list_tasks(guild.id)
        user_id = interaction.user.id

        # Filter tasks
        filtered: List[dict] = []
        for t in all_tasks.values():
            if status and t["status"].lower() != status.lower():
                continue
            if mine and t.get("assignee_id") != user_id:
                continue
            filtered.append(t)

        if not filtered:
            return await interaction.response.send_message(
                "No tasks found with that filter.",
                ephemeral=True
            )

        embed = discord.Embed(
            title="Task List",
            description=f"Found {len(filtered)} task(s).",
            color=discord.Color.blue()
        )

        # Show up to 20 tasks
        for t in sorted(filtered, key=lambda x: x["id"])[:20]:
            assignee = f"<@{t['assignee_id']}>" if t.get("assignee_id") else "Unassigned"
            line = (
                f"**Title:** {t['title']}\n"
                f"**Status:** {t['status']} | **Priority:** {t['priority']}\n"
                f"**Assignee:** {assignee}"
            )
            embed.add_field(
                name=f"Task #{t['id']}",
                value=line,
                inline=False
            )

        await interaction.response.send_message(embed=embed, ephemeral=False)

    @app_commands.command(
        name="tasksboard",
        description="Set or create the persistent task board in this channel."
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def tasks_board(self, interaction: discord.Interaction):
        """
        Creates or moves the task board message to the current channel.
        The board auto-updates whenever tasks change.
        """
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        cfg = get_server_config(guild.id)
        board_channel_id = cfg.get("task_board_channel_id")
        board_message_id = cfg.get("task_board_message_id")

        # If an old board exists, try to delete it
        if board_channel_id and board_message_id:
            old_channel = guild.get_channel(board_channel_id)
            if isinstance(old_channel, discord.TextChannel):
                try:
                    old_msg = await old_channel.fetch_message(board_message_id)
                    await old_msg.delete()
                except discord.NotFound:
                    pass

        # Create new board message in current channel
        embed = discord.Embed(
            title="Task Board",
            description="Loading tasks...",
            color=discord.Color.teal()
        )
        msg = await interaction.channel.send(embed=embed)

        # Save new board reference
        from utils.storage import update_server_config as _update
        _update(
            guild.id,
            task_board_channel_id=interaction.channel.id,
            task_board_message_id=msg.id
        )

        # Update board content
        await self.update_task_board(guild)

        await interaction.response.send_message(
            f"Task board created/updated in {interaction.channel.mention}.",
            ephemeral=True
        )

    # ===== Logging & board helpers =====

    async def log_action(self, guild: discord.Guild, title: str, description: str):
        from utils.storage import get_server_config
        cfg = get_server_config(guild.id)
        logs_id = cfg.get("logs_channel_id")
        if not logs_id:
            return
        channel = guild.get_channel(logs_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return
        embed = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.dark_grey()
        )
        await channel.send(embed=embed)

    async def update_task_board(self, guild: discord.Guild):
        """
        Updates the persistent task board message with current tasks.
        Shows open & in-progress tasks; completed can be omitted or shown at bottom.
        """
        from utils.storage import get_server_config
        cfg = get_server_config(guild.id)
        board_channel_id = cfg.get("task_board_channel_id")
        board_message_id = cfg.get("task_board_message_id")

        if not board_channel_id or not board_message_id:
            return

        channel = guild.get_channel(board_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            msg = await channel.fetch_message(board_message_id)
        except discord.NotFound:
            return

        all_tasks = list_tasks(guild.id)
        if not all_tasks:
            embed = discord.Embed(
                title="Task Board",
                description="No tasks yet.",
                color=discord.Color.teal()
            )
            await msg.edit(embed=embed)
            return

        open_tasks = [t for t in all_tasks.values() if t["status"] in ("Open", "In Progress")]
        done_tasks = [t for t in all_tasks.values() if t["status"] == "Completed"]

        embed = discord.Embed(
            title="Task Board",
            description=f"Open/In Progress: {len(open_tasks)} | Completed: {len(done_tasks)}",
            color=discord.Color.teal()
        )

        # Show up to 15 open/in-progress tasks
        for t in sorted(open_tasks, key=lambda x: x["id"])[:15]:
            assignee = f"<@{t['assignee_id']}>" if t.get("assignee_id") else "Unassigned"
            line = (
                f"**Title:** {t['title']}\n"
                f"**Status:** {t['status']} | **Priority:** {t['priority']}\n"
                f"**Assignee:** {assignee}"
            )
            embed.add_field(
                name=f"Task #{t['id']}",
                value=line,
                inline=False
            )

        if done_tasks:
            # Show count, not details, to keep board clean
            done_ids = ", ".join(
                f"#{t['id']}" for t in sorted(done_tasks, key=lambda x: x["id"])[:20]
            )
            embed.add_field(
                name="Recently Completed",
                value=done_ids,
                inline=False
            )

        await msg.edit(embed=embed)

    # ===== Internal helpers =====

    async def refresh_task_message(self, guild: discord.Guild, task: dict):
        channel = guild.get_channel(task.get("channel_id"))
        message_id = task.get("message_id")
        if not channel or not isinstance(channel, discord.TextChannel) or not message_id:
            return

        try:
            msg = await channel.fetch_message(message_id)
        except discord.NotFound:
            return

        assignee_id = task.get("assignee_id")
        assignee_text = f"<@{assignee_id}>" if assignee_id else "Unassigned"

        embed = discord.Embed(
            title=f"[Task #{task['id']}] {task['title']}",
            description=task["description"],
            color=discord.Color.orange()
        )
        embed.add_field(name="Priority", value=task["priority"], inline=True)
        embed.add_field(name="Status", value=task["status"], inline=True)
        embed.add_field(name="Assignee", value=assignee_text, inline=True)
        embed.set_footer(text=f"Creator ID: {task['creator_id']}")

        view = TaskMainView(self, task["id"])
        await msg.edit(embed=embed, view=view)

    async def ensure_task_thread(self, interaction: discord.Interaction, task: dict) -> Optional[discord.Thread]:
        guild = interaction.guild
        if not guild:
            return None
        channel = guild.get_channel(task.get("channel_id"))
        if not channel or not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message("Task channel not found.", ephemeral=True)
            return None

        thread_id = task.get("thread_id")
        thread: Optional[discord.Thread] = None

        if thread_id:
            thread = guild.get_thread(thread_id)

        if not thread:
            # create a new thread from original message
            try:
                msg = await channel.fetch_message(task["message_id"])
            except discord.NotFound:
                await interaction.response.send_message("Cannot locate task message to create a thread.", ephemeral=True)
                return None

            thread = await msg.create_thread(
                name=f"Task #{task['id']} - {task['title'][:50]}",
                auto_archive_duration=1440  # 24 hours
            )
            update_task(guild.id, task["id"], thread_id=thread.id)

            # post initial controls
            await thread.send(
                content=f"Thread for **Task #{task['id']}**.\n"
                        f"Use this thread to post updates, images, and final work.",
                view=TaskThreadView(self, task["id"])
            )

        return thread

    # ===== Button handlers =====

    async def handle_assign_me(self, interaction: discord.Interaction, task_id: int):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)
        task = get_task(guild.id, task_id)
        if not task:
            return await interaction.response.send_message("Task not found.", ephemeral=True)

        update_task(guild.id, task_id, assignee_id=interaction.user.id)
        task = get_task(guild.id, task_id)
        await self.refresh_task_message(guild, task)

        await self.log_action(
            guild,
            f"Task #{task_id} assigned",
            f"Assigned to {interaction.user.mention}"
        )
        await interaction.response.send_message(f"Task #{task_id} assigned to you.", ephemeral=True)

        await self.update_task_board(guild)

    async def handle_assign_other(self, interaction: discord.Interaction, task_id: int):
        modal = AssignOtherModal(self, task_id)
        await interaction.response.send_modal(modal)

    async def handle_assign_other_submit(self, interaction: discord.Interaction, task_id: int, user_str: str):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        # Try to parse mention or ID
        user_id = None
        if user_str.startswith("<@") and user_str.endswith(">"):
            # mention
            user_str = user_str.strip("<@!>")
        try:
            user_id = int(user_str)
        except ValueError:
            pass

        if not user_id:
            return await interaction.response.send_message("Could not parse user ID.", ephemeral=True)

        member = guild.get_member(user_id)
        if not member:
            return await interaction.response.send_message("User not found in this server.", ephemeral=True)

        task = get_task(guild.id, task_id)
        if not task:
            return await interaction.response.send_message("Task not found.", ephemeral=True)

        update_task(guild.id, task_id, assignee_id=member.id)
        task = get_task(guild.id, task_id)
        await self.refresh_task_message(guild, task)
        await self.log_action(
            guild,
            f"Task #{task_id} assigned",
            f"Assigned to {member.mention} by {interaction.user.mention}"
        )
        await interaction.response.send_message(f"Task #{task_id} assigned to {member.mention}.", ephemeral=True)

        await self.update_task_board(guild)

    async def handle_open_thread(self, interaction: discord.Interaction, task_id: int):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        task = get_task(guild.id, task_id)
        if not task:
            return await interaction.response.send_message("Task not found.", ephemeral=True)

        thread = await self.ensure_task_thread(interaction, task)
        if not thread:
            return

        await interaction.response.send_message(
            f"Task thread: {thread.mention}",
            ephemeral=True
        )

    async def handle_status_change(self, interaction: discord.Interaction, task_id: int, new_status: str):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        task = get_task(guild.id, task_id)
        if not task:
            return await interaction.response.send_message("Task not found.", ephemeral=True)

        update_task(guild.id, task_id, status=new_status)
        task = get_task(guild.id, task_id)
        await self.refresh_task_message(guild, task)
        await self.log_action(
            guild,
            f"Task #{task_id} status updated",
            f"New status: **{new_status}** by {interaction.user.mention}"
        )
        await interaction.response.send_message(f"Status updated to {new_status}.", ephemeral=True)

        await self.update_task_board(guild)

    async def handle_submit_work(self, interaction: discord.Interaction, task_id: int):
        modal = SubmitWorkModal(self, task_id)
        await interaction.response.send_modal(modal)

    async def handle_submit_work_notes(self, interaction: discord.Interaction, task_id: int, notes: str):
        # Notes will just be posted in the thread
        thread = interaction.channel
        if not isinstance(thread, discord.Thread):
            return await interaction.response.send_message(
                "This must be used inside the task thread.",
                ephemeral=True
            )

        msg_content = "Work submission notes:"
        if notes:
            msg_content += f"\n{notes}"
        await thread.send(content=msg_content)

        await interaction.response.send_message(
            "Submission notes recorded. Attach your images/files in this thread as messages.",
            ephemeral=True
        )

    async def handle_mark_done(self, interaction: discord.Interaction, task_id: int):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message("Server only.", ephemeral=True)

        task = get_task(guild.id, task_id)
        if not task:
            return await interaction.response.send_message("Task not found.", ephemeral=True)

        assignee_id = task.get("assignee_id")
        if assignee_id and assignee_id != interaction.user.id and not interaction.user.guild_permissions.manage_messages:
            # allow managers to override
            return await interaction.response.send_message(
                "Only the assignee or a manager can mark this task as done.",
                ephemeral=True
            )

        update_task(guild.id, task_id, status="Completed")
        task = get_task(guild.id, task_id)
        await self.refresh_task_message(guild, task)

        # Attempt to archive thread
        thread_id = task.get("thread_id")
        if thread_id:
            thread = guild.get_thread(thread_id)
            if thread:
                await thread.edit(archived=True, locked=True)

        assignee_text = f"<@{assignee_id}>" if assignee_id else "Unassigned"
        await self.log_action(
            guild,
            f"Task #{task_id} completed",
            f"**Title:** {task['title']}\n**Assignee:** {assignee_text}\nMarked done by {interaction.user.mention}"
        )

        await interaction.response.send_message("Task marked as completed and logged.", ephemeral=True)

        await self.update_task_board(guild)


async def setup(bot: commands.Bot):
    await bot.add_cog(TasksCog(bot))
