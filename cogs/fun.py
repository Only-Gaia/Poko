"""
cogs/fun.py
Fun commands: 8ball, gay, aura, kill/slap/kiss/hug/clap/marry/divorce/
marriagestatus, roll, ship, say.
"""

import random
import time

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils


EIGHT_BALL_ANSWERS = [
    "It is certain.", "Without a doubt.", "Yes, definitely.", "You may rely on it.",
    "As I see it, yes.", "Most likely.", "Outlook good.", "Yes.",
    "Reply hazy, try again.", "Ask again later.", "Better not tell you now.",
    "Cannot predict now.", "Concentrate and ask again.",
    "Don't count on it.", "My reply is no.", "My sources say no.",
    "Outlook not so good.", "Very doubtful.",
]

ACTION_VERBS = {
    "kill": "kills",
    "slap": "slaps",
    "kiss": "kisses",
    "hug": "hugs",
    "clap": "claps for",
}


def _human_duration(seconds: int) -> str:
    units = [("year", 31536000), ("month", 2592000), ("day", 86400), ("hour", 3600), ("minute", 60), ("second", 1)]
    parts = []
    for name, secs in units:
        value = seconds // secs
        seconds -= value * secs
        if value > 0:
            parts.append(f"{value} {name}{'s' if value != 1 else ''}")
    return ", ".join(parts[:3]) if parts else "less than a second"


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="8ball", description="Ask the magic 8-ball a question.")
    @app_commands.describe(question="Your yes/no question")
    async def eight_ball(self, ctx: commands.Context, *, question: str):
        answer = random.choice(EIGHT_BALL_ANSWERS)
        embed = utils.make_embed(title="🎱 Magic 8-Ball", color=config.COLOR_POKO)
        embed.add_field(name="Question", value=question, inline=False)
        embed.add_field(name="Answer", value=answer, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="gay", description="Calculate how gay someone is (100% for fun, purely random!).")
    @app_commands.describe(member="Member to calculate (default: yourself)")
    async def gay(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        percent = random.randint(0, 100)
        bar = "🏳️‍🌈" * (percent // 10) + "⬛" * (10 - percent // 10)
        await ctx.send(embed=utils.make_embed(
            title="🏳️‍🌈 Gay Calculator",
            description=f"{member.mention} is **{percent}%** gay!\n{bar}",
            color=config.COLOR_POKO,
        ))

    @commands.hybrid_command(name="aura", description="Calculate someone's aura points (purely random, just for fun).")
    @app_commands.describe(member="Member to calculate (default: yourself)")
    async def aura(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        points = random.randint(-10000, 10000)
        emoji = "✨" if points >= 0 else "💀"
        await ctx.send(embed=utils.make_embed(
            title=f"{emoji} Aura Calculator",
            description=f"{member.mention} has **{points:,}** aura points!",
            color=config.COLOR_POKO,
        ))

    # ------------------------------------------------------------------
    async def _action_command(self, ctx: commands.Context, member: discord.Member, action: str):
        gif = await utils.fetch_action_gif(action)
        verb = ACTION_VERBS[action]
        if member.id == ctx.author.id:
            desc = f"{ctx.author.mention} {verb} themselves... okay then."
        else:
            desc = f"{ctx.author.mention} {verb} {member.mention}!"
        embed = utils.make_embed(description=desc, color=config.COLOR_POKO)
        if gif:
            embed.set_image(url=gif)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="kill", description="Kill someone (in a fun, non-serious way).")
    @app_commands.describe(member="Member to target")
    async def kill(self, ctx: commands.Context, member: discord.Member):
        await self._action_command(ctx, member, "kill")

    @commands.hybrid_command(name="slap", description="Slap someone.")
    @app_commands.describe(member="Member to target")
    async def slap(self, ctx: commands.Context, member: discord.Member):
        await self._action_command(ctx, member, "slap")

    @commands.hybrid_command(name="kiss", description="Kiss someone.")
    @app_commands.describe(member="Member to target")
    async def kiss(self, ctx: commands.Context, member: discord.Member):
        await self._action_command(ctx, member, "kiss")

    @commands.hybrid_command(name="hug", description="Hug someone.")
    @app_commands.describe(member="Member to target")
    async def hug(self, ctx: commands.Context, member: discord.Member):
        await self._action_command(ctx, member, "hug")

    @commands.hybrid_command(name="clap", description="Clap for someone.")
    @app_commands.describe(member="Member to target")
    async def clap(self, ctx: commands.Context, member: discord.Member):
        await self._action_command(ctx, member, "clap")

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="marry", description="Propose marriage to someone!")
    @app_commands.describe(member="Member to propose to")
    async def marry(self, ctx: commands.Context, member: discord.Member):
        if member.id == ctx.author.id:
            return await ctx.send(embed=utils.error_embed("You can't marry yourself!"))
        if member.bot:
            return await ctx.send(embed=utils.error_embed("You can't marry a bot!"))
        author_data = db.DB.user(ctx.guild.id, ctx.author.id)
        target_data = db.DB.user(ctx.guild.id, member.id)
        if author_data["married_to"]:
            return await ctx.send(embed=utils.error_embed("You are already married! Use `divorce` first."))
        if target_data["married_to"]:
            return await ctx.send(embed=utils.error_embed(f"{member.display_name} is already married!"))

        now = int(time.time())
        db.DB.update_user(ctx.guild.id, ctx.author.id, married_to=str(member.id), married_since=now)
        db.DB.update_user(ctx.guild.id, member.id, married_to=str(ctx.author.id), married_since=now)

        gif = await utils.fetch_action_gif("marry")
        embed = utils.make_embed(
            title="💍 Marriage!",
            description=f"{ctx.author.mention} and {member.mention} are now married! Congratulations!",
            color=config.COLOR_SUCCESS,
        )
        if gif:
            embed.set_image(url=gif)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="divorce", description="Divorce your current partner.")
    async def divorce(self, ctx: commands.Context):
        author_data = db.DB.user(ctx.guild.id, ctx.author.id)
        partner_id = author_data.get("married_to")
        if not partner_id:
            return await ctx.send(embed=utils.error_embed("You aren't married!"))

        db.DB.update_user(ctx.guild.id, ctx.author.id, married_to=None, married_since=None)
        db.DB.update_user(ctx.guild.id, int(partner_id), married_to=None, married_since=None)

        partner = ctx.guild.get_member(int(partner_id))
        partner_name = partner.mention if partner else f"<@{partner_id}>"

        gif = await utils.fetch_action_gif("divorce")
        embed = utils.make_embed(
            title="💔 Divorce",
            description=f"{ctx.author.mention} and {partner_name} are no longer married.",
            color=config.COLOR_ERROR,
        )
        if gif:
            embed.set_image(url=gif)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="marriagestatus", description="See how long a member has been married.")
    @app_commands.describe(member="Member to check (default: yourself)")
    async def marriagestatus(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        data = db.DB.user(ctx.guild.id, member.id)
        if not data.get("married_to"):
            return await ctx.send(embed=utils.make_embed(description=f"{member.display_name} is not married.", color=config.COLOR_INFO))
        partner = ctx.guild.get_member(int(data["married_to"]))
        partner_name = partner.display_name if partner else "someone who left the server"
        duration = _human_duration(int(time.time()) - data["married_since"])
        await ctx.send(embed=utils.make_embed(
            title="💍 Marriage Status",
            description=f"{member.display_name} has been married to **{partner_name}** for **{duration}**.",
            color=config.COLOR_POKO,
        ))

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="roll", description="Roll dice, e.g. 1d20, 2d6.")
    @app_commands.describe(dice="Dice notation, e.g. 1d20 (default: 1d100)")
    async def roll(self, ctx: commands.Context, dice: str = "1d100"):
        try:
            count, sides = dice.lower().split("d")
            count = int(count) if count else 1
            sides = int(sides)
            count = max(1, min(count, 20))
            sides = max(2, min(sides, 1000))
        except ValueError:
            return await ctx.send(embed=utils.error_embed("Invalid format. Use e.g. `1d20` or `2d6`."))
        rolls = [random.randint(1, sides) for _ in range(count)]
        await ctx.send(embed=utils.make_embed(
            title="🎲 Roll",
            description=f"Rolled `{dice}`: {', '.join(str(r) for r in rolls)}\n**Total: {sum(rolls)}**",
            color=config.COLOR_POKO,
        ))

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="ship", description="See the compatibility between two members.")
    @app_commands.describe(member1="First member", member2="Second member (default: yourself)")
    async def ship(self, ctx: commands.Context, member1: discord.Member, member2: discord.Member = None):
        member2 = member2 or ctx.author
        seed = member1.id + member2.id
        percent = seed % 101
        bar_filled = "❤️" * (percent // 10)
        bar_empty = "🖤" * (10 - percent // 10)
        ship_name = member1.display_name[:len(member1.display_name) // 2] + member2.display_name[len(member2.display_name) // 2:]
        await ctx.send(embed=utils.make_embed(
            title="💘 Ship Calculator",
            description=(
                f"{member1.mention} 💞 {member2.mention}\n\n"
                f"Ship name: **{ship_name}**\n"
                f"Compatibility: **{percent}%**\n{bar_filled}{bar_empty}"
            ),
            color=config.COLOR_POKO,
        ))

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="say", description="Make the bot say something.")
    @app_commands.describe(text="What the bot should say")
    @commands.has_permissions(manage_messages=True)
    async def say(self, ctx: commands.Context, *, text: str):
        if ctx.interaction:
            await ctx.interaction.response.send_message("Sent!", ephemeral=True)
        else:
            await ctx.message.delete()
        await ctx.channel.send(text)

    # ------------------------------------------------------------------
    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=utils.error_embed("You don't have permission to use this command."))
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(embed=utils.error_embed("I couldn't find that member."))
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Fun(bot))
