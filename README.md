# Poko
# Poko Bot

A Discord bot written in Python (discord.py 2.x) with **moderation**, **economy**,
**fun**, and **support/verification** commands. Every command is a *hybrid*
command: it works both as a text command (`poko ban @user`, `Poko ban @user`)
and as a native Discord `/` slash command (`/ban`).

## 📁 Files

```
pokobot/
├── bot.py                 # entry point - run this
├── config.py               # all editable settings (token, prefixes, colors...)
├── database.py              # tiny JSON-file persistence layer
├── utils.py                 # shared helpers (embeds, permission checks, luck math)
├── requirements.txt
├── .env.example
├── .gitignore
├── data/                     # created automatically, holds db.json
└── cogs/
    ├── moderation.py         # ban, unban, kick, mute, unmute, warn, leavewarn,
    │                         # warnshow, purge, lock, unlock, message,
    │                         # msgmanage add/remove, pex, depex
    ├── economy.py             # cash, add, remove, tris, mine, coinflip/cf, give,
    │                          # blackjack, lucky, hunt, fish, inventory, questlist
    ├── fun.py                  # 8ball, gay, aura, kill/slap/kiss/hug/clap,
    │                           # marry, divorce, marriagestatus, roll, ship, say
    └── support.py               # setwelcome, setgoodbye, invitebot, userinfo,
                                  # serverinfo, verifica, roleverified,
                                  # roleunverified, level, leaderboard,
                                  # serverlist, membercount, help
```

## 🚀 Setup

1. Create an application + bot at https://discord.com/developers/applications
   - Enable the **Server Members Intent** and **Message Content Intent** under
     Bot > Privileged Gateway Intents (the bot needs both).
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` (or just set the environment variable) and
   put your bot token in `POKO_BOT_TOKEN`.
4. `python bot.py`
5. Invite the bot with the `applications.commands` and `bot` scopes (the
   `invitebot` command will generate this link for you once it's running).

## 🔐 Restricted commands

Only the Discord user with ID **1520803701692829806** can use:
- `message add` / `message remove` (`msgmanage add` / `msgmanage remove`)
- `add` / `remove` (economy)
- `serverlist`

Change `SPECIAL_USER_ID` in `config.py` if you ever need to update this.

## ⚙️ How some game rules were implemented (documented assumptions)

- **tris**: 3x3 tic-tac-toe against the bot. Win = your bet is doubled and
  credited. Draw = your bet is refunded. Loss = you simply lose the bet
  (already deducted when the game starts).
- **mine**: fixed 3x3 grid, always 2 mines / 7 gems (as requested). Each gem
  found raises your cash-out value by exactly your bet amount (`bet × (1 +
  gems_found)`), matching "bet 10 → 20 → 30 → 40...". Hitting a mine loses
  the bet; Cash Out credits the current value.
- **coinflip/cf**: doubles the bet on a win (the announced "won" amount is
  the profit, i.e. equal to the bet), loses the bet otherwise. Uses a short
  text "spin" animation before revealing the result.
- **blackjack**: standard Hit/Stand blackjack, dealer stands on 17. Win
  doubles the bet, push refunds it, loss keeps the deducted bet.
- **lucky**: +1 luck point per use (5 minute cooldown), capped at 1000
  points. Every luck point is worth up to `50 / 1000 = 0.05%` extra win
  chance, capped at **+50%** total, applied mainly to `coinflip` and as a
  small "luck save" in `blackjack`/`tris` (a chance a loss becomes a
  push/mistake). Feel free to wire `utils.win_chance_bonus()` into more
  games.
- **level**: message-based XP (15 XP per message, 60s cooldown to avoid
  spam-leveling). Every level-up grants **10,000 pokash**, per your spec.
  The XP curve is defined in `config.xp_needed_for_level()` if you want to
  tune the pacing.
- **leaderboard**: aggregates every guild's data and shows the global top 10
  by level (best guild-entry per user, since the bot may be in many
  servers).
- **questlist**: no quest content was specified, so a small placeholder
  quest list is included in `cogs/economy.py` — replace `quests = [...]`
  with your real quest data/logic whenever you're ready.
- **kill / clap / marry / divorce gifs**: `hug`, `kiss`, and `slap` fetch a
  real gif from the free, keyless [nekos.best](https://nekos.best) API.
  There's no standard public API for "kill/clap/marry/divorce" reaction
  gifs, so those use a small static fallback list in `config.FALLBACK_GIFS`
  — swap in your own URLs (or your own hosted gifs) whenever you like.
- **coinflip win/lose "emotes"**: `config.COINFLIP_WIN_EMOTE` /
  `COINFLIP_LOSE_EMOTE` default to 👑 / 😢. If you want to use the chibi
  character images you shared, upload them as **custom server emojis**
  first, then set these two config values to the emoji strings Discord
  gives you (e.g. `<:pokosad:123456789012345678>`).
- **pex / depex**: grants/revokes a per-guild "bot staff" flag
  (`utils.is_staff()`), usable to gate future commands beyond Discord's
  native permission system. Currently `pex`/`depex` themselves require
  Discord Administrator to run.
- **verifica**: posts an embed styled after your screenshot, translated to
  English and rebranded "Poko Security". On join, the configured
  unverified role is auto-assigned; pressing **Verify now** assigns the
  configured verified role (and removes the unverified one) and runs a
  lightweight, non-blocking account check (account age, missing avatar) -
  if something looks off it just notifies staff in the configured log
  channel, it never blocks or auto-bans.

## 📝 Notes

- Data is stored in `data/db.json` (auto-created). For larger servers,
  swap `database.py`'s internals for SQLite/PostgreSQL — the `DB` class
  interface can stay the same.
- `say` requires `Manage Messages` permission to reduce abuse potential
  (not explicitly requested, but recommended).
- Remember to run `git init`, add a remote, and push this folder to GitHub
  — don't commit your real token or `data/db.json` (both are already in
  `.gitignore`).
