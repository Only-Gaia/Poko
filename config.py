"""
config.py
Central configuration for Poko Bot.
Edit the values below (or use environment variables) before running the bot.
"""

import os

# ------------------------------------------------------------------
# The only user allowed to use: message add / message remove,
# economy add / economy remove, and serverlist.
# ------------------------------------------------------------------
SPECIAL_USER_ID = 1520803701692829806

# Text prefixes the bot answers to (in addition to native "/" slash commands,
# which work automatically because every command below is a "hybrid" command).
PREFIXES = ["poko ", "Poko ", "POKO "]

# Discord bot token - set the POKO_BOT_TOKEN environment variable,
# or paste your token directly below (NOT recommended for GitHub).
BOT_TOKEN = os.getenv("POKO_BOT_TOKEN", "PASTE_YOUR_TOKEN_HERE")

# Path to the JSON "database" file used for persistence.
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DATA_DIR, "db.json")

# Embed colors
COLOR_SUCCESS = 0x57F287
COLOR_ERROR = 0xED4245
COLOR_INFO = 0x5865F2
COLOR_ECONOMY = 0xFEE75C
COLOR_POKO = 0x8E7CFF

# Currency
CURRENCY_NAME = "pokash"
CURRENCY_EMOJI = "💶"

# Mines game (fixed per spec: 3x3 grid -> 9 cells, 2 mines, 7 gems)
MINES_GRID_SIZE = 9
MINES_COUNT = 2

# Luck system
MAX_LUCK = 1000          # max luck points a user can hold
MAX_LUCK_WIN_BONUS = 50  # luck points cap the win-chance bonus at +50%
LUCKY_COOLDOWN_SECONDS = 5 * 60

# Leveling (message based XP -> level -> pokash reward)
XP_PER_MESSAGE = 15
XP_MESSAGE_COOLDOWN_SECONDS = 60
POKASH_PER_LEVEL = 10000


def xp_needed_for_level(level: int) -> int:
    """XP required to reach the given level (simple increasing curve)."""
    return 100 * (level + 1) * (level + 1)


# ------------------------------------------------------------------
# GIFs used by the fun "action" commands (kill, slap, kiss, hug, clap,
# marry, divorce). We use the free, keyless nekos.best API for the
# reactions it supports, and a small static fallback list for the
# ones it doesn't have (kill, clap, marry, divorce) - feel free to
# replace the fallback URLs with your own.
# ------------------------------------------------------------------
NEKOSBEST_API = "https://nekos.best/api/v2/{endpoint}"

# action name -> nekos.best endpoint name
NEKOSBEST_MAP = {
    "hug": "hug",
    "kiss": "kiss",
    "slap": "slap",
}

# action name -> list of fallback gif urls (used when there is no
# matching nekos.best endpoint, or if the API call fails)
FALLBACK_GIFS = {
    "kill": [
        "https://media.tenor.com/y7WV2TYlx9AAAAAC/anime-fight.gif",
        "https://media.tenor.com/x4bLDBjMSPYAAAAC/anime-attack.gif",
    ],
    "clap": [
        "https://media.tenor.com/pyeuHt1EK9wAAAAC/anime-clap.gif",
        "https://media.tenor.com/Xc4pnXwlOG0AAAAC/clapping-anime.gif",
    ],
    "marry": [
        "https://media.tenor.com/vjLZW3rf1w0AAAAC/anime-wedding.gif",
    ],
    "divorce": [
        "https://media.tenor.com/G5UUqM9EPzMAAAAC/anime-sad.gif",
    ],
    "hug": [
        "https://media.tenor.com/2roX2vLrRXwAAAAC/anime-hug.gif",
    ],
    "kiss": [
        "https://media.tenor.com/2roX2vLrRXwAAAAC/anime-kiss.gif",
    ],
    "slap": [
        "https://media.tenor.com/2roX2vLrRXwAAAAC/anime-slap.gif",
    ],
}

# Emotes for the coinflip win / lose messages.
# Replace these with your own custom server emojis if you want to use
# the chibi crown/crying character images, e.g. "<:pokowin:123456789012345678>"
COINFLIP_LOSE_EMOTE = "😢"
COINFLIP_WIN_EMOTE = "👑"
