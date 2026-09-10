"""
cogs/support.py
Support commands: setwelcome, setgoodbye, invitebot, userinfo, serverinfo,
verifica (verification panel), roleverified, roleunverified, level,
leaderboard, serverlist, membercount, help.

Also handles: welcome/goodbye messages, auto-assigning the unverified role
on join, the verification button flow, and message-based XP/leveling.
"""

import time

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils


def _account_flags(member: discord.User) -> list:
    """A very small heuristic account-status check, purely informational -
    it never blocks verification, it just flags things for staff to see."""
    flags = []
    account_age_days = (discord.utils.utcnow() - member.created_at).days
    if account_age_days < 7:
        flags.append(f"Account created only {account_age_days} day(s) ago")
    if member.default_avatar == member.display_avatar and not member.avatar:
        flags.append("No custom avatar set")
    return flags


class VerifyView(discord.ui.View):
    """Persistent view for the verification panel - survives bot restarts
    because it has no timeout and a fixed custom_id per button."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Verify now", style=discord.ButtonStyle.success, emoji="✅", custom_id="poko_verify_button")
    async def verify(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild = interaction.guild
        cfg = db.DB.guild_config(guild.id)
        verified_role_id = cfg.get("verified_role")
        unverified_role_id = cfg.get("unverified_role")

        if not verified_role_id:
            return await interaction.response.send_message(
                "Verification isn't configured yet - ask a staff member to run `poko roleverified`.",
                ephemeral=True,
            )

        verified_role = guild.get_role(int(verified_role_id))
        if not verified_role:
            return await interaction.response.send_message(
                "The configured verified role no longer exists - ask staff to reconfigure it.",
                ephemeral=True,
            )

        member = interaction.user
        if verified_role in member.roles:
            return await interaction.response.send_message("You're already verified! ✅", ephemeral=True)

        flags = _account_flags(member)
        try:
            await member.add_roles(verified_role, reason="Poko Security verification")
            if unverified_role_id:
                unverified_role = guild.get_role(int(unverified_role_id))
                if unverified_role and unverified_role in member.roles:
                    await member.remove_roles(unverified_role, reason="Poko Security verification")
        except discord.Forbidden:
            return await interaction.response.send_message(
                "I don't have permission to manage roles - ask staff to check my role position/permissions.",
                ephemeral=True,
            )

        await interaction.response.send_message("✅ You have been verified! Welcome aboard.", ephemeral=True)

        log_channel_id = cfg.get("log_channel")
        if flags and log_channel_id:
            log_channel = guild.get_channel(int(log_channel_id))
            if log_channel:
                embed = utils.make_embed(
                    title="⚠️ Verification flag",
                    description=f"{member.mention} verified but the account check noticed:\n- " + "\n- ".join(flags),
                    color=config.COLOR_ERROR,
                )
                await log_channel.send(embed=embed)


class Support(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._xp_cooldowns = {}
        bot.add_view(VerifyView())  # register persistent view on cog load

    # ------------------------------------------------------------------
    # WELCOME / GOODBYE
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="setwelcome", description="Set the channel used for welcome messages.")
    @app_commands.describe(channel="Channel to send welcome messages in")
    @commands.has_permissions(manage_guild=True)
    async def setwelcome(self, ctx: commands.Context, channel: discord.TextChannel):
        db.DB.set_guild_config(ctx.guild.id, welcome_channel=channel.id)
        await ctx.send(embed=utils.success_embed(f"👋 Welcome messages will now be sent in {channel.mention}."))

    @commands.hybrid_command(name="setgoodbye", description="Set the channel used for goodbye messages.")
    @app_commands.describe(channel="Channel to send goodbye messages in")
    @commands.has_permissions(manage_guild=True)
    async def setgoodbye(self, ctx: commands.Context, channel: discord.TextChannel):
        db.DB.set_guild_config(ctx.guild.id, goodbye_channel=channel.id)
        await ctx.send(embed=utils.success_embed(f"👋 Goodbye messages will now be sent in {channel.mention}."))

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        cfg = db.DB.guild_config(member.guild.id)

        welcome_channel_id = cfg.get("welcome_channel")
        if welcome_channel_id:
            channel = member.guild.get_channel(int(welcome_channel_id))
            if channel:
                text = cfg.get("welcome_message", "Welcome {mention} to **{guild}**! 🎉").format(
                    mention=member.mention, user=str(member), guild=member.guild.name
                )
                await channel.send(text)

        unverified_role_id = cfg.get("unverified_role")
        if unverified_role_id:
            role = member.guild.get_role(int(unverified_role_id))
            if role:
                try:
                    await member.add_roles(role, reason="Auto-assigned unverified role on join")
                except discord.Forbidden:
                    pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        cfg = db.DB.guild_config(member.guild.id)
        goodbye_channel_id = cfg.get("goodbye_channel")
        if goodbye_channel_id:
            channel = member.guild.get_channel(int(goodbye_channel_id))
            if channel:
                text = cfg.get("goodbye_message", "**{user}** left the server. 👋").format(
                    mention=member.mention, user=str(member), guild=member.guild.name
                )
                await channel.send(text)

    # ------------------------------------------------------------------
    # INVITE
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="invitebot", description="Get an invite link for Poko Bot.")
    async def invitebot(self, ctx: commands.Context):
        perms = discord.Permissions(
            ban_members=True, kick_members=True, moderate_members=True,
            manage_channels=True, manage_messages=True, manage_roles=True,
            read_messages=True, send_messages=True, embed_links=True,
            attach_files=True, read_message_history=True, add_reactions=True,
        )
        invite_url = discord.utils.oauth_url(self.bot.user.id, permissions=perms, scopes=("bot", "applications.commands"))
        await ctx.send(embed=utils.make_embed(
            title="🔗 Invite Poko Bot",
            description=f"[Click here to invite me to your server]({invite_url})",
            color=config.COLOR_POKO,
        ))

    # ------------------------------------------------------------------
    # USERINFO / SERVERINFO
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="userinfo", description="Show information about a member.")
    @app_commands.describe(member="Member to check (default: yourself)")
    async def userinfo(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        embed = utils.make_embed(title=f"👤 {member}", color=config.COLOR_POKO)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="ID", value=member.id, inline=True)
        embed.add_field(name="Nickname", value=member.nick or "None", inline=True)
        embed.add_field(name="Bot", value="Yes" if member.bot else "No", inline=True)
        embed.add_field(name="Joined server", value=discord.utils.format_dt(member.joined_at, "R") if member.joined_at else "Unknown", inline=True)
        embed.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "R"), inline=True)
        roles = [r.mention for r in member.roles if r.name != "@everyone"]
        embed.add_field(name=f"Roles ({len(roles)})", value=" ".join(roles) if roles else "None", inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="serverinfo", description="Show information about this server.")
    async def serverinfo(self, ctx: commands.Context):
        guild = ctx.guild
        embed = utils.make_embed(title=f"🏠 {guild.name}", color=config.COLOR_POKO)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
        embed.add_field(name="Owner", value=str(guild.owner), inline=True)
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Created", value=discord.utils.format_dt(guild.created_at, "R"), inline=True)
        embed.add_field(name="Text channels", value=len(guild.text_channels), inline=True)
        embed.add_field(name="Voice channels", value=len(guild.voice_channels), inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="membercount", description="Show how many members are in this server.")
    async def membercount(self, ctx: commands.Context):
        await ctx.send(embed=utils.make_embed(
            title="👥 Member Count",
            description=f"**{ctx.guild.name}** has **{ctx.guild.member_count}** members.",
            color=config.COLOR_INFO,
        ))

    @commands.hybrid_command(name="serverlist", description="List every server Poko Bot is in. (restricted)")
    @utils.is_special_user()
    async def serverlist(self, ctx: commands.Context):
        guilds = self.bot.guilds
        lines = [f"• **{g.name}** ({g.member_count} members) — `{g.id}`" for g in guilds]
        text = "\n".join(lines) or "No servers."
        embed = utils.make_embed(title=f"🌐 Servers ({len(guilds)})", description=text[:4000], color=config.COLOR_INFO)
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    # VERIFICATION
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="verifica", aliases=["verify"], description="Post the Poko Security verification panel in this channel.")
    @commands.has_permissions(manage_guild=True)
    async def verifica(self, ctx: commands.Context):
        embed = utils.make_embed(
            title="✅ SECURITY VERIFICATION ⚠️",
            description=(
                "Welcome! To access the rest of the server you need to verify.\n\n"
                "**How it works:**\n"
                "1️⃣ Press the ✅ **Verify now** button below\n"
                "2️⃣ The system checks your account (age, avatar, global blacklist)\n"
                "3️⃣ If everything looks fine, you instantly get the ✅ **Verified** role\n\n"
                "This protects the server from fake accounts, alts, and spam bots.\n"
                "If the check flags something suspicious, staff will be notified but you can still "
                "verify — no automatic ban.\n\n"
                "*Poko Security*"
            ),
            color=config.COLOR_POKO,
        )
        await ctx.send(embed=embed, view=VerifyView())

    @commands.hybrid_command(name="roleverified", description="Configure the role given to members after they verify.")
    @app_commands.describe(role="The verified role")
    @commands.has_permissions(manage_roles=True)
    async def roleverified(self, ctx: commands.Context, role: discord.Role):
        db.DB.set_guild_config(ctx.guild.id, verified_role=role.id)
        await ctx.send(embed=utils.success_embed(f"The verified role has been set to {role.mention}."))

    @commands.hybrid_command(name="roleunverified", description="Configure the role auto-assigned to new members before they verify.")
    @app_commands.describe(role="The unverified role")
    @commands.has_permissions(manage_roles=True)
    async def roleunverified(self, ctx: commands.Context, role: discord.Role):
        db.DB.set_guild_config(ctx.guild.id, unverified_role=role.id)
        await ctx.send(embed=utils.success_embed(f"The unverified role has been set to {role.mention}."))

    # ------------------------------------------------------------------
    # LEVELS
    # ------------------------------------------------------------------
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        now = time.time()
        key = (message.guild.id, message.author.id)
        last = self._xp_cooldowns.get(key, 0)
        if now - last < config.XP_MESSAGE_COOLDOWN_SECONDS:
            return
        self._xp_cooldowns[key] = now
        leveled_up, level, pokash = db.DB.add_xp(message.guild.id, message.author.id, config.XP_PER_MESSAGE)
        if leveled_up:
            try:
                await message.channel.send(
                    f"🎉 {message.author.mention} you are on level {level}! You earned {config.POKASH_PER_LEVEL} {config.CURRENCY_NAME} {config.CURRENCY_EMOJI}"
                )
            except discord.Forbidden:
                pass

    @commands.hybrid_command(name="level", description="Show a member's level.")
    @app_commands.describe(member="Member to check (default: yourself)")
    async def level(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        data = db.DB.user(ctx.guild.id, member.id)
        await ctx.send(f"{member.mention} you are on level {data['level']}!")

    @commands.hybrid_command(name="leaderboard", description="Show the worldwide top 10 by level.")
    async def leaderboard(self, ctx: commands.Context):
        top = db.DB.global_level_leaderboard(10)
        if not top:
            return await ctx.send(embed=utils.make_embed(description="No data yet.", color=config.COLOR_INFO))
        lines = []
        for i, (user_id, guild_id, level, xp) in enumerate(top, start=1):
            user = self.bot.get_user(user_id)
            name = str(user) if user else f"User {user_id}"
            lines.append(f"**#{i}** — {name} — Level **{level}**")
        await ctx.send(embed=utils.make_embed(title="🏆 Worldwide Leaderboard", description="\n".join(lines), color=config.COLOR_POKO))

    # ------------------------------------------------------------------
    # HELP
    # ------------------------------------------------------------------
    @commands.hybrid_command(name="help", description="Show all Poko Bot commands.")
    async def help_command(self, ctx: commands.Context):
        embed = utils.make_embed(title="📖 Poko Bot — Help", color=config.COLOR_POKO,
                                  description="Prefix: `poko` / `Poko` — or use `/` slash commands.")
        embed.add_field(
            name="🛡️ Moderation",
            value="`ban` `unban` `kick` `mute` `unmute` `warn` `leavewarn` `warnshow` `purge` `lock` `unlock` `message` `msgmanage add/remove` `pex` `depex`",
            inline=False,
        )
        embed.add_field(
            name="💰 Economy",
            value="`cash` `add` `remove` `tris` `mine` `coinflip/cf` `give` `blackjack` `lucky` `hunt` `fish` `inventory` `questlist`",
            inline=False,
        )
        embed.add_field(
            name="🎉 Fun",
            value="`8ball` `gay` `aura` `kill` `slap` `kiss` `hug` `clap` `marry` `divorce` `marriagestatus` `roll` `ship` `say`",
            inline=False,
        )
        embed.add_field(
            name="🛠️ Support",
            value="`setwelcome` `setgoodbye` `invitebot` `userinfo` `serverinfo` `verifica` `roleverified` `roleunverified` `level` `leaderboard` `serverlist` `membercount` `help`",
            inline=False,
        )
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=utils.error_embed("You don't have permission to use this command."))
        elif isinstance(error, commands.CheckFailure):
            await ctx.send(embed=utils.error_embed(str(error) or "You can't use this command."))
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(embed=utils.error_embed("I couldn't find that member."))
        elif isinstance(error, commands.RoleNotFound):
            await ctx.send(embed=utils.error_embed("I couldn't find that role."))
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Support(bot))
