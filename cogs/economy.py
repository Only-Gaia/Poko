"""
cogs/economy.py
Economy commands: cash, add/remove, tris, mine, coinflip/cf, give,
blackjack, lucky, hunt, fish, inventory, questlist.
"""

import asyncio
import random

import discord
from discord import app_commands
from discord.ext import commands

import config
import database as db
import utils


# ----------------------------------------------------------------------
# Loot tables for hunt / fish
# ----------------------------------------------------------------------
HUNT_LOOT = [
    ("Rabbit", 0.35, 5),
    ("Fox", 0.25, 15),
    ("Deer", 0.20, 30),
    ("Wolf", 0.12, 60),
    ("Bear", 0.06, 150),
    ("Mythical Stag", 0.02, 500),
]

FISH_LOOT = [
    ("Common Fish", 0.35, 5),
    ("Trout", 0.25, 15),
    ("Salmon", 0.20, 30),
    ("Shark", 0.12, 60),
    ("Golden Fish", 0.06, 150),
    ("Mythical Kraken Scale", 0.02, 500),
]


def _weighted_choice(table):
    roll = random.random()
    cumulative = 0.0
    for name, weight, value in table:
        cumulative += weight
        if roll <= cumulative:
            return name, value
    return table[-1][0], table[-1][2]


# ----------------------------------------------------------------------
# Tris (Tic-Tac-Toe) view
# ----------------------------------------------------------------------
class TrisButton(discord.ui.Button):
    def __init__(self, index: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=index // 3)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        await self.view.handle_move(interaction, self.index)


class TrisView(discord.ui.View):
    def __init__(self, player: discord.Member, bet: int, guild_id: int):
        super().__init__(timeout=120)
        self.player = player
        self.bet = bet
        self.guild_id = guild_id
        self.board = [None] * 9  # "X" (player) / "O" (bot) / None
        self.buttons = [TrisButton(i) for i in range(9)]
        for b in self.buttons:
            self.add_item(b)
        self.finished = False

    def _winner(self):
        lines = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
        for a, b, c in lines:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        if all(self.board):
            return "draw"
        return None

    def _render_button(self, i):
        val = self.board[i]
        btn = self.buttons[i]
        if val == "X":
            btn.label = "❌"
            btn.style = discord.ButtonStyle.danger
            btn.disabled = True
        elif val == "O":
            btn.label = "⭕"
            btn.style = discord.ButtonStyle.primary
            btn.disabled = True

    async def handle_move(self, interaction: discord.Interaction, index: int):
        if interaction.user.id != self.player.id:
            return await interaction.response.send_message("This isn't your game!", ephemeral=True)
        if self.finished or self.board[index] is not None:
            return await interaction.response.defer()

        self.board[index] = "X"
        self._render_button(index)

        result = self._winner()
        if result is None:
            # bot's turn - occasionally "blunders" based on the player's luck
            luck = db.DB.user(self.guild_id, self.player.id)["luck"]
            bonus = utils.win_chance_bonus(luck)
            empties = [i for i, v in enumerate(self.board) if v is None]
            move = self._pick_bot_move(bonus, empties)
            self.board[move] = "O"
            self._render_button(move)
            result = self._winner()

        if result is not None:
            await self._end_game(interaction, result)
        else:
            await interaction.response.edit_message(view=self)

    def _pick_bot_move(self, mistake_bonus: float, empties):
        # try to win, else try to block, else random - unless "mistake" triggers
        if random.random() < mistake_bonus:
            return random.choice(empties)
        for mark in ("O", "X"):
            for i in empties:
                trial = self.board.copy()
                trial[i] = mark
                lines = [(0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)]
                for a, b, c in lines:
                    if trial[a] and trial[a] == trial[b] == trial[c]:
                        return i
        return random.choice(empties)

    async def _end_game(self, interaction: discord.Interaction, result: str):
        self.finished = True
        for b in self.buttons:
            b.disabled = True
        if result == "X":
            winnings = self.bet * 2
            db.DB.add_pokash(self.guild_id, self.player.id, winnings)
            text = f"🎉 **{self.player.display_name}** wins and receives **{utils.format_pokash(winnings)}**!"
            color = config.COLOR_SUCCESS
        elif result == "O":
            text = f"💀 The bot wins! **{self.player.display_name}** loses **{utils.format_pokash(self.bet)}**."
            color = config.COLOR_ERROR
        else:
            db.DB.add_pokash(self.guild_id, self.player.id, self.bet)  # refund on draw
            text = f"🤝 It's a draw! **{self.player.display_name}**'s bet has been refunded."
            color = config.COLOR_INFO
        self.stop()
        await interaction.response.edit_message(
            embed=utils.make_embed(title="Tris", description=text, color=color), view=self
        )

    async def on_timeout(self):
        for b in self.buttons:
            b.disabled = True
        db.DB.add_pokash(self.guild_id, self.player.id, self.bet)  # refund if abandoned


# ----------------------------------------------------------------------
# Mine game view
# ----------------------------------------------------------------------
class MineButton(discord.ui.Button):
    def __init__(self, index: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="❔", row=index // 3)
        self.index = index

    async def callback(self, interaction: discord.Interaction):
        await self.view.handle_click(interaction, self.index)


class MineView(discord.ui.View):
    def __init__(self, player: discord.Member, bet: int, guild_id: int):
        super().__init__(timeout=120)
        self.player = player
        self.bet = bet
        self.guild_id = guild_id
        self.mines = set(random.sample(range(config.MINES_GRID_SIZE), config.MINES_COUNT))
        self.gems_found = 0
        self.finished = False
        self.buttons = [MineButton(i) for i in range(config.MINES_GRID_SIZE)]
        for b in self.buttons:
            self.add_item(b)
        self.cashout_btn = discord.ui.Button(style=discord.ButtonStyle.success, label="💰 Cash Out", row=3)
        self.cashout_btn.callback = self.cash_out
        self.add_item(self.cashout_btn)

    @property
    def current_win(self):
        return self.bet * (1 + self.gems_found)

    async def handle_click(self, interaction: discord.Interaction, index: int):
        if interaction.user.id != self.player.id:
            return await interaction.response.send_message("This isn't your game!", ephemeral=True)
        if self.finished:
            return await interaction.response.defer()

        btn = self.buttons[index]
        if btn.disabled:
            return await interaction.response.defer()

        if index in self.mines:
            btn.label = "💥"
            btn.style = discord.ButtonStyle.danger
            btn.disabled = True
            await self._end_game(interaction, hit_mine=True)
            return

        self.gems_found += 1
        btn.label = "💎"
        btn.style = discord.ButtonStyle.success
        btn.disabled = True

        if self.gems_found >= (config.MINES_GRID_SIZE - config.MINES_COUNT):
            await self._end_game(interaction, hit_mine=False, all_found=True)
            return

        embed = utils.make_embed(
            title="⛏️ Mine",
            description=(
                f"Bet: **{self.bet}**\n"
                f"Gems found: **{self.gems_found}**\n"
                f"Current cash-out value: **{utils.format_pokash(self.current_win)}**"
            ),
            color=config.COLOR_ECONOMY,
        )
        await interaction.response.edit_message(embed=embed, view=self)

    async def cash_out(self, interaction: discord.Interaction):
        if interaction.user.id != self.player.id:
            return await interaction.response.send_message("This isn't your game!", ephemeral=True)
        if self.finished:
            return await interaction.response.defer()
        if self.gems_found == 0:
            return await interaction.response.send_message("Find at least one gem before cashing out!", ephemeral=True)
        await self._end_game(interaction, hit_mine=False)

    async def _end_game(self, interaction: discord.Interaction, hit_mine: bool, all_found: bool = False):
        self.finished = True
        for b in self.buttons:
            b.disabled = True
        self.cashout_btn.disabled = True

        for i in self.mines:
            if self.buttons[i].label == "❔":
                self.buttons[i].label = "💣"

        if hit_mine:
            text = f"💥 **{self.player.display_name}** hit a mine and lost **{utils.format_pokash(self.bet)}**!"
            color = config.COLOR_ERROR
        else:
            win = self.current_win
            db.DB.add_pokash(self.guild_id, self.player.id, win)
            extra = " (all 7 gems found!)" if all_found else ""
            text = f"💰 **{self.player.display_name}** cashed out **{utils.format_pokash(win)}**{extra}!"
            color = config.COLOR_SUCCESS

        self.stop()
        await interaction.response.edit_message(
            embed=utils.make_embed(title="⛏️ Mine — Game Over", description=text, color=color), view=self
        )

    async def on_timeout(self):
        for b in self.buttons:
            b.disabled = True
        self.cashout_btn.disabled = True
        if not self.finished and self.gems_found > 0:
            db.DB.add_pokash(self.guild_id, self.player.id, self.current_win)


# ----------------------------------------------------------------------
# Blackjack helpers
# ----------------------------------------------------------------------
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def _draw_card():
    return random.choice(RANKS), random.choice(SUITS)


def _hand_value(hand):
    value = 0
    aces = 0
    for rank, _ in hand:
        if rank == "A":
            value += 11
            aces += 1
        elif rank in ("J", "Q", "K"):
            value += 10
        else:
            value += int(rank)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value


def _hand_str(hand):
    return " ".join(f"{r}{s}" for r, s in hand)


class BlackjackView(discord.ui.View):
    def __init__(self, player: discord.Member, bet: int, guild_id: int):
        super().__init__(timeout=90)
        self.player = player
        self.bet = bet
        self.guild_id = guild_id
        self.player_hand = [_draw_card(), _draw_card()]
        self.dealer_hand = [_draw_card(), _draw_card()]
        self.finished = False

    def embed(self, reveal_dealer=False):
        dealer_display = _hand_str(self.dealer_hand) if reveal_dealer else f"{self.dealer_hand[0][0]}{self.dealer_hand[0][1]} ❔"
        e = utils.make_embed(title="🃏 Blackjack", color=config.COLOR_ECONOMY)
        e.add_field(name=f"Your hand ({_hand_value(self.player_hand)})", value=_hand_str(self.player_hand), inline=False)
        e.add_field(name="Dealer's hand" + (f" ({_hand_value(self.dealer_hand)})" if reveal_dealer else ""), value=dealer_display, inline=False)
        e.set_footer(text=f"Bet: {self.bet} {config.CURRENCY_EMOJI}")
        return e

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.id:
            return await interaction.response.send_message("This isn't your game!", ephemeral=True)
        if self.finished:
            return await interaction.response.defer()
        self.player_hand.append(_draw_card())
        if _hand_value(self.player_hand) > 21:
            await self._end_game(interaction, "bust")
        else:
            await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.player.id:
            return await interaction.response.send_message("This isn't your game!", ephemeral=True)
        if self.finished:
            return await interaction.response.defer()
        while _hand_value(self.dealer_hand) < 17:
            self.dealer_hand.append(_draw_card())
        player_val = _hand_value(self.player_hand)
        dealer_val = _hand_value(self.dealer_hand)
        if dealer_val > 21 or player_val > dealer_val:
            outcome = "win"
        elif player_val == dealer_val:
            outcome = "push"
        else:
            outcome = "lose"
        await self._end_game(interaction, outcome)

    async def _end_game(self, interaction: discord.Interaction, outcome: str):
        self.finished = True
        for child in self.children:
            child.disabled = True

        luck = db.DB.user(self.guild_id, self.player.id)["luck"]
        if outcome == "lose" and random.random() < utils.win_chance_bonus(luck):
            outcome = "push"  # a little luck save

        if outcome == "win":
            winnings = self.bet * 2
            db.DB.add_pokash(self.guild_id, self.player.id, winnings)
            desc = f"🎉 **{self.player.display_name}** wins **{utils.format_pokash(winnings)}**!"
            color = config.COLOR_SUCCESS
        elif outcome == "push":
            db.DB.add_pokash(self.guild_id, self.player.id, self.bet)
            desc = f"🤝 Push! **{self.player.display_name}**'s bet has been refunded."
            color = config.COLOR_INFO
        else:
            desc = f"💀 **{self.player.display_name}** loses **{utils.format_pokash(self.bet)}**."
            color = config.COLOR_ERROR

        self.stop()
        embed = self.embed(reveal_dealer=True)
        embed.add_field(name="Result", value=desc, inline=False)
        embed.color = color
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if not self.finished:
            db.DB.add_pokash(self.guild_id, self.player.id, self.bet)  # refund abandoned game


# ----------------------------------------------------------------------
class Economy(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_bet(self, ctx, bet: int, user_id: int):
        user = db.DB.user(ctx.guild.id, user_id)
        if bet <= 0:
            return None, "You must bet a positive amount."
        if user["pokash"] < bet:
            return None, f"You don't have enough {config.CURRENCY_NAME}! You only have {user['pokash']}."
        return bet, None

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="cash", description="Check your pokash balance.")
    async def cash(self, ctx: commands.Context):
        user = db.DB.user(ctx.guild.id, ctx.author.id)
        await ctx.send(f"{ctx.author.mention} you have {user['pokash']} {config.CURRENCY_NAME}! {config.CURRENCY_EMOJI}")

    @commands.hybrid_command(name="add", description="Add pokash to a member's balance. (restricted)")
    @app_commands.describe(member="Member to give pokash to", amount="Amount to add")
    @utils.is_special_user()
    async def add(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send(embed=utils.error_embed("Amount must be positive."))
        total = db.DB.add_pokash(ctx.guild.id, member.id, amount)
        await ctx.send(f"**{ctx.author.display_name}** has added **{amount}** {config.CURRENCY_NAME} to {member.mention}! Their total is now **{total}** {config.CURRENCY_EMOJI}")

    @commands.hybrid_command(name="remove", description="Remove pokash from a member's balance. (restricted)")
    @app_commands.describe(member="Member to remove pokash from", amount="Amount to remove")
    @utils.is_special_user()
    async def remove(self, ctx: commands.Context, member: discord.Member, amount: int):
        if amount <= 0:
            return await ctx.send(embed=utils.error_embed("Amount must be positive."))
        total = db.DB.add_pokash(ctx.guild.id, member.id, -amount)
        await ctx.send(f"**{ctx.author.display_name}** has removed **{amount}** {config.CURRENCY_NAME} from {member.mention}! Their total is now **{total}** {config.CURRENCY_EMOJI}")

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="give", description="Give some of your pokash to another member.")
    @app_commands.describe(member="Member to give pokash to", amount="Amount to give")
    async def give(self, ctx: commands.Context, member: discord.Member, amount: int):
        if member.id == ctx.author.id:
            return await ctx.send(embed=utils.error_embed("You can't give pokash to yourself!"))
        if member.bot:
            return await ctx.send(embed=utils.error_embed("You can't give pokash to a bot!"))
        bet, err = self._get_bet(ctx, amount, ctx.author.id)
        if err:
            return await ctx.send(embed=utils.error_embed(err))
        db.DB.add_pokash(ctx.guild.id, ctx.author.id, -amount)
        db.DB.add_pokash(ctx.guild.id, member.id, amount)
        await ctx.send(f"{ctx.author.mention} you are super Kind! You give {amount} {config.CURRENCY_NAME} to {member.mention}!")

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="tris", description="Play tic-tac-toe against the bot for pokash.")
    @app_commands.describe(bet="Amount of pokash to bet")
    async def tris(self, ctx: commands.Context, bet: int):
        amount, err = self._get_bet(ctx, bet, ctx.author.id)
        if err:
            return await ctx.send(embed=utils.error_embed(err))
        db.DB.add_pokash(ctx.guild.id, ctx.author.id, -amount)
        view = TrisView(ctx.author, amount, ctx.guild.id)
        embed = utils.make_embed(
            title="❌ Tris ⭕",
            description=f"{ctx.author.mention} vs Bot 🤖\nBet: **{amount}** {config.CURRENCY_EMOJI}\nYou are ❌ — you go first!",
            color=config.COLOR_ECONOMY,
        )
        await ctx.send(embed=embed, view=view)

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="mine", description="Play mines: find gems, avoid the 2 mines, cash out anytime.")
    @app_commands.describe(bet="Amount of pokash to bet")
    async def mine(self, ctx: commands.Context, bet: int):
        amount, err = self._get_bet(ctx, bet, ctx.author.id)
        if err:
            return await ctx.send(embed=utils.error_embed(err))
        db.DB.add_pokash(ctx.guild.id, ctx.author.id, -amount)
        view = MineView(ctx.author, amount, ctx.guild.id)
        embed = utils.make_embed(
            title="⛏️ Mine",
            description=f"Bet: **{amount}** {config.CURRENCY_EMOJI}\n2 mines, 7 gems. Each gem adds your bet to your winnings!",
            color=config.COLOR_ECONOMY,
        )
        await ctx.send(embed=embed, view=view)

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="coinflip", aliases=["cf"], description="Flip a coin and bet on heads or tails.")
    @app_commands.describe(side="Heads or tails", bet="Amount of pokash to bet")
    @app_commands.choices(side=[app_commands.Choice(name="Heads", value="heads"), app_commands.Choice(name="Tails", value="tails")])
    async def coinflip(self, ctx: commands.Context, side: str, bet: int):
        side = side.lower()
        if side not in ("head", "heads", "tail", "tails"):
            return await ctx.send(embed=utils.error_embed("Choose `heads` or `tails`."))
        side = "heads" if side.startswith("head") else "tails"

        amount, err = self._get_bet(ctx, bet, ctx.author.id)
        if err:
            return await ctx.send(embed=utils.error_embed(err))
        db.DB.add_pokash(ctx.guild.id, ctx.author.id, -amount)

        msg = await ctx.send(embed=utils.make_embed(title="🪙 Flipping the coin...", color=config.COLOR_ECONOMY))
        frames = ["🪙 . . .", "🪙 . . . .", "🪙 . . . . ."]
        for frame in frames:
            await asyncio.sleep(0.6)
            await msg.edit(embed=utils.make_embed(title=frame, color=config.COLOR_ECONOMY))

        luck = db.DB.user(ctx.guild.id, ctx.author.id)["luck"]
        win_probability = 0.5 + utils.win_chance_bonus(luck)
        won = random.random() < win_probability
        result_side = side if won else ("tails" if side == "heads" else "heads")

        if won:
            winnings = amount
            db.DB.add_pokash(ctx.guild.id, ctx.author.id, amount * 2)
            embed = utils.make_embed(
                title=f"{config.COINFLIP_WIN_EMOTE} It landed on {result_side}!",
                description=f"congratulation {ctx.author.mention}! You won {winnings} pokacash! 🪙",
                color=config.COLOR_SUCCESS,
            )
        else:
            embed = utils.make_embed(
                title=f"{config.COINFLIP_LOSE_EMOTE} It landed on {result_side}!",
                description=f"oh no… {ctx.author.mention} you lost {amount} {config.CURRENCY_NAME}",
                color=config.COLOR_ERROR,
            )
        await msg.edit(embed=embed)

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="blackjack", description="Play blackjack against the dealer for pokash.")
    @app_commands.describe(bet="Amount of pokash to bet")
    async def blackjack(self, ctx: commands.Context, bet: int):
        amount, err = self._get_bet(ctx, bet, ctx.author.id)
        if err:
            return await ctx.send(embed=utils.error_embed(err))
        db.DB.add_pokash(ctx.guild.id, ctx.author.id, -amount)
        view = BlackjackView(ctx.author, amount, ctx.guild.id)
        await ctx.send(embed=view.embed(), view=view)

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="lucky", description="Increase your luck by 1 point (max 1000).")
    @commands.cooldown(1, config.LUCKY_COOLDOWN_SECONDS, commands.BucketType.user)
    async def lucky(self, ctx: commands.Context):
        new_luck = db.DB.add_luck(ctx.guild.id, ctx.author.id, 1)
        await ctx.send(f"{ctx.author.mention} you now have {new_luck} 🍀")

    @lucky.error
    async def lucky_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=utils.error_embed(f"You can use this again in {error.retry_after:.0f}s."))
        else:
            raise error

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="hunt", description="Go hunting for animals!")
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def hunt(self, ctx: commands.Context):
        name, value = _weighted_choice(HUNT_LOOT)
        db.DB.add_inventory_item(ctx.guild.id, ctx.author.id, name, 1)
        await ctx.send(embed=utils.make_embed(
            title="🏹 Hunting",
            description=f"{ctx.author.mention} went hunting and caught a **{name}**! (worth ~{value} {config.CURRENCY_NAME} if sold)",
            color=config.COLOR_ECONOMY,
        ))

    @commands.hybrid_command(name="fish", description="Go fishing!")
    @commands.cooldown(1, 20, commands.BucketType.user)
    async def fish(self, ctx: commands.Context):
        name, value = _weighted_choice(FISH_LOOT)
        db.DB.add_inventory_item(ctx.guild.id, ctx.author.id, name, 1)
        await ctx.send(embed=utils.make_embed(
            title="🎣 Fishing",
            description=f"{ctx.author.mention} went fishing and caught a **{name}**! (worth ~{value} {config.CURRENCY_NAME} if sold)",
            color=config.COLOR_ECONOMY,
        ))

    @hunt.error
    @fish.error
    async def hunt_fish_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=utils.error_embed(f"You're tired, try again in {error.retry_after:.0f}s."))
        else:
            raise error

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="inventory", description="See a member's inventory.")
    @app_commands.describe(member="Member to check (default: yourself)")
    async def inventory(self, ctx: commands.Context, member: discord.Member = None):
        member = member or ctx.author
        user = db.DB.user(ctx.guild.id, member.id)
        if not user["inventory"]:
            return await ctx.send(embed=utils.make_embed(description=f"**{member.display_name}**'s inventory is empty.", color=config.COLOR_INFO))
        lines = "\n".join(f"• **{item}** x{qty}" for item, qty in user["inventory"].items())
        await ctx.send(embed=utils.make_embed(title=f"🎒 {member.display_name}'s Inventory", description=lines, color=config.COLOR_INFO))

    # ------------------------------------------------------------------
    @commands.hybrid_command(name="questlist", description="See the current available quests.")
    async def questlist(self, ctx: commands.Context):
        quests = [
            ("🏹 Hunter's Path", "Use `poko hunt` 5 times."),
            ("🎣 Fisherman's Path", "Use `poko fish` 5 times."),
            ("🍀 Feeling Lucky", "Reach 50 luck points with `poko lucky`."),
            ("💰 High Roller", "Win 3 games of `poko mine`."),
        ]
        embed = utils.make_embed(title="📜 Quest List", color=config.COLOR_INFO)
        for name, desc in quests:
            embed.add_field(name=name, value=desc, inline=False)
        await ctx.send(embed=embed)

    # ------------------------------------------------------------------
    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(embed=utils.error_embed(str(error) or "You can't use this command."))
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send(embed=utils.error_embed("I couldn't find that member."))
        elif isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=utils.error_embed(f"Try again in {error.retry_after:.0f}s."))
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Economy(bot))
