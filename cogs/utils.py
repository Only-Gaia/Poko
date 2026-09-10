"""
utils.py
Small shared helpers used by every cog.
"""

import random
import discord
from discord.ext import commands

import config
import database as db


def is_special_user():
    """Command check: only config.SPECIAL_USER_ID may run this command."""
    async def predicate(ctx: commands.Context):
        if ctx.author.id != config.SPECIAL_USER_ID:
            raise commands.CheckFailure(
                "Only the bot's designated owner can use this command."
            )
        return True
    return commands.check(predicate)


def is_staff():
    """Command check: passes for real Discord permission holders (Administrator,
    or the specific permission relevant to the cog) OR users added via
    `poko pex`. Individual commands still layer their own discord permission
    requirement on top of this where it matters (see moderation.py)."""
    async def predicate(ctx: commands.Context):
        if ctx.author.id == config.SPECIAL_USER_ID:
            return True
        if ctx.guild and ctx.author.guild_permissions.administrator:
            return True
        if ctx.guild and db.DB.is_staff(ctx.guild.id, ctx.author.id):
            return True
        raise commands.CheckFailure(
            "You need to be a server administrator or be granted `pex` to use this command."
        )
    return commands.check(predicate)


def make_embed(title: str = None, description: str = None, color: int = config.COLOR_INFO):
    embed = discord.Embed(title=title, description=description, color=color)
    return embed


def error_embed(description: str):
    return make_embed(title="❌ Error", description=description, color=config.COLOR_ERROR)


def success_embed(description: str):
    return make_embed(title="✅ Success", description=description, color=config.COLOR_SUCCESS)


def win_chance_bonus(luck_points: int) -> float:
    """Convert luck points into an extra win-chance fraction, capped at
    config.MAX_LUCK_WIN_BONUS percent (e.g. 50 luck points cap -> +0.50)."""
    capped = min(luck_points, config.MAX_LUCK)
    bonus_percent = min(config.MAX_LUCK_WIN_BONUS, capped / config.MAX_LUCK * 100)
    # scale: MAX_LUCK points -> MAX_LUCK_WIN_BONUS percent bonus
    bonus_percent = (capped / config.MAX_LUCK) * config.MAX_LUCK_WIN_BONUS
    return bonus_percent / 100.0


def format_pokash(amount: int) -> str:
    return f"{amount:,} {config.CURRENCY_EMOJI}"


async def fetch_action_gif(action: str) -> str:
    """Return a gif URL for an action command, using the nekos.best API when
    available for that action, otherwise a static fallback list."""
    import aiohttp

    endpoint = config.NEKOSBEST_MAP.get(action)
    if endpoint:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(config.NEKOSBEST_API.format(endpoint=endpoint), timeout=5) as resp:
                    if resp.status == 200:
                        payload = await resp.json()
                        results = payload.get("results")
                        if results:
                            return results[0]["url"]
        except Exception:
            pass  # fall through to the static fallback below

    fallback = config.FALLBACK_GIFS.get(action)
    if fallback:
        return random.choice(fallback)
    return None
