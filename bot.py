"""
bot.py
Main entry point for Poko Bot.

Run with:  python bot.py
Prefix:    "poko " / "Poko " (case variants) for text commands.
           Every command also works as a native "/" slash command.
"""

import asyncio
import logging

import discord
from discord.ext import commands

import config

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
log = logging.getLogger("poko")


def get_prefix(bot: commands.Bot, message: discord.Message):
    return commands.when_mentioned_or(*config.PREFIXES)(bot, message)


intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(
    command_prefix=get_prefix,
    intents=intents,
    help_command=None,
    case_insensitive=True,
    description="Poko Bot - moderation, economy, fun and support commands.",
)

EXTENSIONS = [
    "cogs.moderation",
    "cogs.economy",
    "cogs.fun",
    "cogs.support",
]


@bot.event
async def on_ready():
    log.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    try:
        synced = await bot.tree.sync()
        log.info("Synced %d slash command(s).", len(synced))
    except Exception as e:
        log.exception("Failed to sync slash commands: %s", e)
    await bot.change_presence(activity=discord.Game(name="poko help | /help"))


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    # Cog-level cog_command_error handlers deal with most errors already;
    # this is the fallback for errors from commands outside any cog.
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        return await ctx.send(f"❌ Missing argument: `{error.param.name}`. Check `poko help`.")
    if isinstance(error, commands.BadArgument):
        return await ctx.send(f"❌ {error}")
    log.exception("Unhandled command error", exc_info=error)
    await ctx.send("❌ Something went wrong running that command.")


async def main():
    async with bot:
        for extension in EXTENSIONS:
            await bot.load_extension(extension)
            log.info("Loaded extension: %s", extension)
        await bot.start(config.BOT_TOKEN)


if __name__ == "__main__":
    if not config.BOT_TOKEN or config.BOT_TOKEN == "PASTE_YOUR_TOKEN_HERE":
        raise SystemExit(
            "No bot token found. Set the POKO_BOT_TOKEN environment variable "
            "(or edit config.py) before running the bot."
        )
    asyncio.run(main())
