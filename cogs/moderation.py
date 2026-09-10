"""
cogs/moderation.py
Moderation commands: ban, unban, kick, mute, unmute, warn, leavewarn,
warnshow, purge, lock, unlock, message, message add/remove, pex, depex.

All commands work both as text commands ("poko ban @user reason") and as
native "/" slash commands, because they are declared as hybrid commands.
"""

import datetime as dt

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils


class Moderation(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------------------
    # BAN / UNBAN
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="ban", description="Ban a member from the server.")
    @app_commands.describe(member="The member to ban", reason="Reason for the ban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send(embed=utils.error_embed("You cannot ban someone with an equal or higher role."))
        try:
            await member.send(embed=utils.make_embed(
                title=f"You were banned from {ctx.guild.name}",
                description=f"**Reason:** {reason}",
                color=config.COLOR_ERROR,
            ))
        except discord.Forbidden:
            pass
        await ctx.guild.ban(member, reason=f"{reason} | by {ctx.author}")
        await ctx.send(embed=utils.success_embed(f"🔨 **{member}** has been banned.\n**Reason:** {reason}"))

    @commands.hybrid_command(name="unban", description="Unban a user by their ID.")
    @app_commands.describe(user_id="The ID of the user to unban")
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    async def unban(self, ctx: commands.Context, user_id: str):
        try:
            user = await self.bot.fetch_user(int(user_id))
        except (ValueError, discord.NotFound):
            return await ctx.send(embed=utils.error_embed("Invalid user ID."))
        try:
            await ctx.guild.unban(user)
        except discord.NotFound:
            return await ctx.send(embed=utils.error_embed("That user is not banned."))
        await ctx.send(embed=utils.success_embed(f"✅ **{user}** has been unbanned."))

    # ------------------------------------------------------------------
    # KICK
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="kick", description="Kick a member from the server.")
    @app_commands.describe(member="The member to kick", reason="Reason for the kick")
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        if member.top_role >= ctx.author.top_role and ctx.author.id != ctx.guild.owner_id:
            return await ctx.send(embed=utils.error_embed("You cannot kick someone with an equal or higher role."))
        try:
            await member.send(embed=utils.make_embed(
                title=f"You were kicked from {ctx.guild.name}",
                description=f"**Reason:** {reason}",
                color=config.COLOR_ERROR,
            ))
        except discord.Forbidden:
            pass
        await member.kick(reason=f"{reason} | by {ctx.author}")
        await ctx.send(embed=utils.success_embed(f"👢 **{member}** has been kicked.\n**Reason:** {reason}"))

    # ------------------------------------------------------------------
    # MUTE / UNMUTE (uses Discord's native timeout)
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="mute", description="Timeout (mute) a member.")
    @app_commands.describe(member="The member to mute", minutes="Duration in minutes (default 10)", reason="Reason")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def mute(self, ctx: commands.Context, member: discord.Member, minutes: int = 10, *, reason: str = "No reason provided"):
        minutes = max(1, min(minutes, 40320))  # discord's hard cap is 28 days
        until = discord.utils.utcnow() + dt.timedelta(minutes=minutes)
        await member.timeout(until, reason=f"{reason} | by {ctx.author}")
        await ctx.send(embed=utils.success_embed(f"🔇 **{member}** has been muted for **{minutes} minute(s)**.\n**Reason:** {reason}"))

    @commands.hybrid_command(name="unmute", description="Remove a member's timeout.")
    @app_commands.describe(member="The member to unmute")
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        await member.timeout(None, reason=f"Unmuted by {ctx.author}")
        await ctx.send(embed=utils.success_embed(f"🔊 **{member}** has been unmuted."))

    # ------------------------------------------------------------------
    # WARN / LEAVEWARN / WARNSHOW
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="warn", description="Warn a member.")
    @app_commands.describe(member="The member to warn", reason="Reason for the warning")
    @commands.has_permissions(moderate_members=True)
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        total = db.DB.add_warn(ctx.guild.id, member.id, reason, ctx.author.id)
        try:
            await member.send(embed=utils.make_embed(
                title=f"You were warned in {ctx.guild.name}",
                description=f"**Reason:** {reason}\n**Total warns:** {total}",
                color=config.COLOR_ERROR,
            ))
        except discord.Forbidden:
            pass
        await ctx.send(embed=utils.success_embed(f"⚠️ **{member}** has been warned.\n**Reason:** {reason}\n**Total warns:** {total}"))

    @commands.hybrid_command(name="leavewarn", description="Remove a specific warning from a member.")
    @app_commands.describe(member="The member", index="Warn number to remove, as shown in /warnshow (starts at 1)")
    @commands.has_permissions(moderate_members=True)
    async def leavewarn(self, ctx: commands.Context, member: discord.Member, index: int):
        ok = db.DB.remove_warn(ctx.guild.id, member.id, index - 1)
        if not ok:
            return await ctx.send(embed=utils.error_embed("That warn number doesn't exist."))
        await ctx.send(embed=utils.success_embed(f"🗑️ Removed warn **#{index}** from **{member}**."))

    @commands.hybrid_command(name="warnshow", description="Show all warnings a member has.")
    @app_commands.describe(member="The member")
    @commands.has_permissions(moderate_members=True)
    async def warnshow(self, ctx: commands.Context, member: discord.Member):
        warns = db.DB.get_warns(ctx.guild.id, member.id)
        if not warns:
            return await ctx.send(embed=utils.make_embed(description=f"**{member}** has no warnings.", color=config.COLOR_INFO))
        embed = utils.make_embed(title=f"Warnings for {member}", color=config.COLOR_ERROR)
        for i, w in enumerate(warns, start=1):
            mod = ctx.guild.get_member(w["moderator"])
            embed.add_field(
                name=f"#{i} — <t:{w['time']}:R>",
                value=f"**Reason:** {w['reason']}\n**By:** {mod.mention if mod else w['moderator']}",
                inline=False,
            )
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # PURGE
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="purge", description="Delete a number of recent messages in this channel.")
    @app_commands.describe(amount="How many messages to delete (max 100)")
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True)
    async def purge(self, ctx: commands.Context, amount: int):
        amount = max(1, min(amount, 100))
        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=True)
        deleted = await ctx.channel.purge(limit=amount + (0 if ctx.interaction else 1))
        msg = await ctx.send(embed=utils.success_embed(f"🧹 Deleted **{len(deleted)}** messages."))
        await msg.delete(delay=4)

    # ------------------------------------------------------------------
    # LOCK / UNLOCK
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="lock", description="Lock a channel so @everyone can't send messages.")
    @app_commands.describe(channel="Channel to lock (default: this channel)")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def lock(self, ctx: commands.Context, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        db.DB.set_locked(ctx.guild.id, channel.id, True)
        await ctx.send(embed=utils.success_embed(f"🔒 {channel.mention} has been locked."))

    @commands.hybrid_command(name="unlock", description="Unlock a previously locked channel.")
    @app_commands.describe(channel="Channel to unlock (default: this channel)")
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def unlock(self, ctx: commands.Context, channel: discord.TextChannel = None):
        channel = channel or ctx.channel
        overwrite = channel.overwrites_for(ctx.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(ctx.guild.default_role, overwrite=overwrite)
        db.DB.set_locked(ctx.guild.id, channel.id, False)
        await ctx.send(embed=utils.success_embed(f"🔓 {channel.mention} has been unlocked."))

    # ------------------------------------------------------------------
    # MESSAGE / MESSAGE ADD / MESSAGE REMOVE
    # (saved macros the bot can post on demand - add/remove are locked to
    # the bot's designated owner, config.SPECIAL_USER_ID)
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="message", description="Send a saved custom message by name.")
    @app_commands.describe(name="Name of the saved message")
    @commands.has_permissions(manage_messages=True)
    async def message_cmd(self, ctx: commands.Context, name: str):
        content = db.DB.get_custom_message(ctx.guild.id, name)
        if content is None:
            names = ", ".join(db.DB.list_custom_messages(ctx.guild.id)) or "none yet"
            return await ctx.send(embed=utils.error_embed(f"No saved message called `{name}`.\nAvailable: {names}"))
        await ctx.send(content)

    @commands.hybrid_group(name="msgmanage", description="Add or remove a saved bot message (restricted).", fallback="help")
    async def msgmanage(self, ctx: commands.Context):
        await ctx.send(embed=utils.make_embed(
            description="Use `poko msgmanage add <name> <content>` or `poko msgmanage remove <name>`.",
        ))

    @msgmanage.command(name="add", description="Add or update a saved bot message.")
    @app_commands.describe(name="Name for the message", content="The message content to save")
    @utils.is_special_user()
    async def message_add(self, ctx: commands.Context, name: str, *, content: str):
        db.DB.set_custom_message(ctx.guild.id, name, content)
        await ctx.send(embed=utils.success_embed(f"💾 Saved message `{name}`."))

    @msgmanage.command(name="remove", description="Remove a saved bot message.")
    @app_commands.describe(name="Name of the message to remove")
    @utils.is_special_user()
    async def message_remove(self, ctx: commands.Context, name: str):
        ok = db.DB.remove_custom_message(ctx.guild.id, name)
        if not ok:
            return await ctx.send(embed=utils.error_embed(f"No saved message called `{name}`."))
        await ctx.send(embed=utils.success_embed(f"🗑️ Removed saved message `{name}`."))

    # ------------------------------------------------------------------
    # PEX / DEPEX (grant/revoke bot-level "staff" permission)
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="pex", description="Grant a member bot-staff permissions (moderation access).")
    @app_commands.describe(member="The member to grant permissions to")
    @commands.has_permissions(administrator=True)
    async def pex(self, ctx: commands.Context, member: discord.Member):
        db.DB.add_staff(ctx.guild.id, member.id)
        await ctx.send(embed=utils.success_embed(f"🛡️ **{member}** has been granted bot-staff permissions."))

    @commands.hybrid_command(name="depex", description="Revoke a member's bot-staff permissions.")
    @app_commands.describe(member="The member to revoke permissions from")
    @commands.has_permissions(administrator=True)
    async def depex(self, ctx: commands.Context, member: discord.Member):
        db.DB.remove_staff(ctx.guild.id, member.id)
        await ctx.send(embed=utils.success_embed(f"🛡️ **{member}**'s bot-staff permissions have been revoked."))

    # ------------------------------------------------------------------
    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=utils.error_embed("You don't have permission to use this command."))
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send(embed=utils.error_embed("I don't have the permissions needed to do that."))
        elif isinstance(error, commands.CheckFailure):
            await ctx.send(embed=utils.error_embed(str(error) or "You can't use this command."))
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(embed=utils.error_embed("I couldn't find that member."))
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Moderation(bot))
