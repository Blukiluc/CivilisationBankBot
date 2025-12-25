import interactions
from interactions import (
    Button, ButtonStyle, ActionRow, modal_callback, Modal, ShortText
)
from dotenv import load_dotenv
import os
import aiosqlite
import asyncio
import aiohttp

# ============================================================
#                        CONFIG / INIT
# ============================================================

load_dotenv()
TOKEN = os.getenv("TOKEN")

# Initialize bot
bot = interactions.Client(
    token=TOKEN,
    sync_commands=True,
    default_scope=int(os.getenv("GUILD_ID")),
    intents=interactions.Intents.ALL
)

CATEGORY_NAME = "Banks"   # Category where bank channels are created


# ============================================================
#                        DATABASE SETUP
# ============================================================

async def init_db():
    """Create SQLite tables if they don't exist."""
    async with aiosqlite.connect("bank.db") as db:

        # Users table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discord_id INTEGER UNIQUE,
            discord_username TEXT NOT NULL UNIQUE,
            minecraft_username TEXT NOT NULL UNIQUE,
            minecraft_uuid TEXT NOT NULL UNIQUE,
            money INTEGER default 0,
            has_bank INTEGER default 0,
            bank_channel_id INTEGER default NULL UNIQUE,
            joined DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Transactions table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_discord_id INTEGER NOT NULL,
            receiver_discord_id INTEGER NOT NULL,
            amount INTEGER NOT NULL,
            date DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        await db.commit()

    print("Database initialized.")


# ============================================================
#                       DATABASE FUNCTIONS
# ============================================================

async def register_user_db(discord_id: int, discord_username: str, minecraft_username: str, minecraft_uuid: str):
    async with aiosqlite.connect("bank.db") as db:
        await db.execute(
            "INSERT INTO users (discord_id, discord_username, minecraft_username, minecraft_uuid) VALUES (?, ?, ?, ?)",
            (discord_id, discord_username, minecraft_username, minecraft_uuid)
        )
        await db.commit()


async def get_user(discord_id: int):
    async with aiosqlite.connect("bank.db") as db:
        cursor = await db.execute("SELECT * FROM users WHERE discord_id = ?", (discord_id,))
        return await cursor.fetchone()


async def update_user_bank(discord_id: int, bank_channel_id: int):
    async with aiosqlite.connect("bank.db") as db:
        await db.execute(
            "UPDATE users SET has_bank = 1, bank_channel_id = ? WHERE discord_id = ?",
            (bank_channel_id, discord_id)
        )
        await db.commit()


async def update_user_balance(discord_id: int, balance: int):
    async with aiosqlite.connect("bank.db") as db:
        await db.execute(
            "UPDATE users SET money = ? WHERE discord_id = ?",
            (balance, discord_id)
        )
        await db.commit()


async def get_minecraft_username(minecraft_username: str):
    async with aiosqlite.connect("bank.db") as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE minecraft_username = ?",
            (minecraft_username,)
        )
        return await cursor.fetchone()


async def get_minecraft_uuid(minecraft_uuid: str):
    async with aiosqlite.connect("bank.db") as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE minecraft_uuid = ?",
            (minecraft_uuid,)
        )
        return await cursor.fetchone()


async def log_transaction(sender_discord_id: int, receiver_discord_id: int, amount: int):
    async with aiosqlite.connect("bank.db") as db:
        await db.execute(
            "INSERT INTO transactions (sender_discord_id, receiver_discord_id, amount) VALUES (?, ?, ?)",
            (sender_discord_id, receiver_discord_id, amount)
        )
        await db.commit()


# ============================================================
#                     MOJANG API CHECK
# ============================================================

async def get_minecraft_profile(username: str):
    """Check Mojang API for username → UUID."""
    url = f"https://api.mojang.com/users/profiles/minecraft/{username}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:

            if response.status == 200:
                data = await response.json()
                return {
                    "exists": True,
                    "uuid": data["id"],
                    "username": data["name"]
                }

            elif response.status in (204, 404):
                return {"exists": False, "uuid": None, "username": None}

            return {
                "exists": False,
                "uuid": None,
                "username": None,
                "error": f"Mojang API error {response.status}"
            }


# ============================================================
#                           EVENTS
# ============================================================

@bot.event()
async def on_ready():
    print("Bot online!")
    await bot.synchronise_interactions()


# ============================================================
#                        /LINK COMMAND
# ============================================================

@interactions.slash_command(name="link", description="Link your Minecraft account.")
async def link(ctx: interactions.SlashContext):
    """Opens a modal to link Minecraft account."""
    modal = Modal(
        ShortText(custom_id="minecraft_username", label="Minecraft Username", required=True),
        ShortText(custom_id="minecraft_uuid", label="Minecraft UUID (no dashes)", required=True),
        title="Link your Minecraft account",
        custom_id="link_modal",
    )
    await ctx.send_modal(modal)


@modal_callback("link_modal")
async def handle_modal(ctx: interactions.ModalContext):
    """Handles Minecraft ↔ Discord linking."""
    minecraft_username = ctx.responses["minecraft_username"].lower()
    minecraft_uuid = ctx.responses["minecraft_uuid"].lower()
    discord_user = ctx.author.username
    discord_id = ctx.author.id

    # Check profile validity
    profile = await get_minecraft_profile(minecraft_username)

    # Error cases
    if await get_user(discord_id) is not None:
        return await ctx.send("❌ You already linked an account.", ephemeral=True)

    if not profile["exists"]:
        return await ctx.send("❌ Minecraft username does not exist.", ephemeral=True)

    if profile["uuid"].lower() != minecraft_uuid:
        return await ctx.send("❌ UUID does not match username.", ephemeral=True)

    if await get_minecraft_username(minecraft_username):
        return await ctx.send("❌ Username already linked to someone.", ephemeral=True)

    if await get_minecraft_uuid(minecraft_uuid):
        return await ctx.send("❌ UUID already linked to someone.", ephemeral=True)

    # Success
    await register_user_db(discord_id, discord_user, minecraft_username, minecraft_uuid)
    await ctx.send("✅ Minecraft account linked successfully!", ephemeral=True)


# ============================================================
#                  CREATE BANK ACCOUNT (BUTTON)
# ============================================================

@interactions.component_callback("create_bank_button")
async def create_bank_button_clicked(ctx: interactions.ComponentContext):
    """Creates a private bank channel for the user."""
    server = ctx.guild
    user = ctx.user

    # Check if category exists
    category = interactions.utils.get(server.channels, name=CATEGORY_NAME, type=interactions.ChannelType.GUILD_CATEGORY)
    if category is None:
        return await ctx.send("Category not found.", ephemeral=True)

    user_db = await get_user(user.id)

    if user_db is None:
        return await ctx.send("Link your account first using /link.", ephemeral=True)

    if user_db[6] == 1:
        return await ctx.send(f"You already have a bank: <#{user_db[7]}>", ephemeral=True)

    # Create private bank channel
    channel = await server.create_text_channel(name=f"{user.username}-bank", category=category)
    await update_user_bank(user.id, channel.id)

    await ctx.send(f"Bank created! <#{channel.id}>", ephemeral=True)

    # Buttons in bank channel
    balance_btn = Button(style=ButtonStyle.GREEN, label="Check balance", custom_id="bank_balance")
    send_btn = Button(style=ButtonStyle.RED, label="Send money", custom_id="bank_send_money")
    logs_btn = Button(style=ButtonStyle.GRAY, label="View logs", custom_id="bank_logs")

    await channel.send(
        f"Welcome <@{user.id}>! Your bank account is now active.",
        components=ActionRow(balance_btn, send_btn, logs_btn)
    )


# ============================================================
#                         CHECK BALANCE
# ============================================================

@interactions.component_callback("bank_balance")
async def bank_balance_clicked(ctx: interactions.ComponentContext):
    user_db = await get_user(ctx.user.id)
    if user_db is None:
        return await ctx.send("Error: Contact admin.", ephemeral=True)

    await ctx.send(f"💰 Balance: **{user_db[5]}** social credits.", ephemeral=True)


# ============================================================
#                        SEND MONEY SYSTEM
# ============================================================

@interactions.component_callback("bank_send_money")
async def bank_send_money(ctx: interactions.SlashContext):
    """Shows a modal to send money."""
    modal = Modal(
        ShortText(custom_id="username_recipient", label="Minecraft Username", required=True),
        ShortText(custom_id="amount", label="Amount", required=True),
        title="Send money",
        custom_id="send_money_modal",
    )
    await ctx.send_modal(modal)


@modal_callback("send_money_modal")
async def handle_send_money_modal(ctx: interactions.ModalContext):
    """Handles money transfer logic."""
    minecraft_username = ctx.responses["username_recipient"].lower()
    amount = int(ctx.responses["amount"])

    sender_db = await get_user(ctx.author.id)
    recipient_db = await get_minecraft_username(minecraft_username)

    # Error cases
    if recipient_db is None:
        return await ctx.send("❌ Unknown Minecraft username.", ephemeral=True)

    if amount <= 0:
        return await ctx.send("❌ Invalid amount.", ephemeral=True)

    if sender_db[5] < amount:
        return await ctx.send("❌ Insufficient balance.", ephemeral=True)

    if recipient_db[1] == ctx.author.id:
        return await ctx.send("❌ You cannot send money to yourself.", ephemeral=True)

    if recipient_db[7] is None:
        return await ctx.send("❌ Recipient has no bank account.", ephemeral=True)

    # Transfer money
    await update_user_balance(ctx.author.id, sender_db[5] - amount)
    await update_user_balance(recipient_db[1], recipient_db[5] + amount)
    await log_transaction(ctx.author.id, recipient_db[1], amount)

    # Notify sender
    await ctx.send(f"✅ Sent {amount} credits to <@{recipient_db[1]}>.", ephemeral=True)

    # Notify recipient
    recipient_channel = bot.get_channel(recipient_db[7])
    await recipient_channel.send(
        f"💸 You received **{amount}** social credits from <@{ctx.author.id}>."
    )


# ============================================================
#                     MINECRAFT ↔ DISCORD LOOKUP
# ============================================================

@interactions.slash_command(name="minecraftname", description="Get Minecraft username from Discord user.")
@interactions.slash_option(
    name="user",
    description="Target user",
    opt_type=interactions.OptionType.USER,
    required=True
)
async def minecraft_name(ctx: interactions.SlashContext, user: interactions.User):
    user_db = await get_user(user.id)
    if user_db is None:
        return await ctx.send("User not found.", ephemeral=True)

    profile = await get_minecraft_profile(user_db[3])
    await ctx.send(f"Minecraft username: **{profile['username']}**", ephemeral=True)


@interactions.slash_command(name="discordname", description="Get Discord user from Minecraft username.")
@interactions.slash_option(
    name="minecraft_username",
    description="Minecraft username",
    opt_type=interactions.OptionType.STRING,
    required=True
)
async def discord_name(ctx: interactions.SlashContext, minecraft_username: str):
    user_db = await get_minecraft_username(minecraft_username.lower())
    if user_db is None:
        return await ctx.send("User not found.", ephemeral=True)

    await ctx.send(f"Discord user: <@{user_db[1]}>", ephemeral=True)


# ============================================================
#                        ADMIN COMMANDS
# ============================================================

@interactions.slash_command(name="admin", description="Admin controls")
async def admin(ctx: interactions.SlashContext):
    """Shows admin buttons."""
    btn_link = Button(style=ButtonStyle.GREEN, label="Link admin", custom_id="link_admin_button")
    btn_set = Button(style=ButtonStyle.RED, label="Set money", custom_id="set_money_button")
    btn_create = Button(style=ButtonStyle.PRIMARY, label="Create Bank button", custom_id="create_bank_button_admin")
    btn_config = Button(style=ButtonStyle.GRAY, label="Config", custom_id="config_button_admin")

    await ctx.send(
        "Admin commands:",
        components=ActionRow(btn_link, btn_set, btn_create, btn_config),
        ephemeral=True
    )


@interactions.component_callback("create_bank_button_admin")
async def create_bank_button_admin(ctx: interactions.ComponentContext):
    """Posts the 'Create account' button."""
    await ctx.defer(ephemeral=True)

    button = Button(
        style=ButtonStyle.PRIMARY,
        label="Create an account",
        custom_id="create_bank_button"
    )

    await ctx.channel.send(
        "🏦 Click the button to create your bank account:",
        components=ActionRow(button)
    )


@interactions.component_callback("link_admin_button")
async def link_admin(ctx: interactions.ComponentContext):
    """Links an admin account without Mojang check."""
    if await get_user(ctx.author.id):
        return await ctx.send("❌ Already linked.", ephemeral=True)

    await register_user_db(ctx.author.id, ctx.author.username, ctx.author.username, ctx.author.id)
    await ctx.send("✅ Linked as admin.", ephemeral=True)


# ============================================================
#                        SET MONEY SYSTEM
# ============================================================

user_waiting_reply = {}   # {discord_id: [waiting_bool, channel_id]}


@interactions.component_callback("set_money_button")
async def set_money(ctx: interactions.ComponentContext):
    """Admin begins manual input process."""
    user_waiting_reply[ctx.author.id] = [True, ctx.channel.id]
    await ctx.channel.send(
        "Send: `<DiscordID> <Amount>`\nType `Cancel` to stop.",
        ephemeral=True
    )


@interactions.listen()
async def on_message_create(event: interactions.events.MessageCreate):
    """Handles admin manual money input."""
    msg = event.message
    global user_waiting_reply

    if msg.author.bot:
        return

    # If the user is not in the waiting list → ignore
    if not user_waiting_reply.get(msg.author.id, [False])[0]:
        return

    # Check correct channel
    if msg.channel.id != user_waiting_reply[msg.author.id][1]:
        return

    # Cancel operation
    if msg.content.lower() == "cancel":
        user_waiting_reply[msg.author.id] = [False, None]
        return await msg.channel.send("Operation cancelled.", ephemeral=True)

    # Validate format
    parts = msg.content.split(" ")
    if len(parts) != 2 or not parts[0].isdigit() or not parts[1].isdigit():
        user_waiting_reply[msg.author.id] = [False, None]
        return await msg.channel.send("Invalid format. Cancelled.", ephemeral=True)

    target_id = int(parts[0])
    amount = int(parts[1])

    target_db = await get_user(target_id)

    if target_db is None:
        user_waiting_reply[msg.author.id] = [False, None]
        return await msg.channel.send("User not found.", ephemeral=True)

    await update_user_balance(target_id, amount)
    await msg.channel.send(f"Balance updated: **{amount}** for **{target_db[2]}**.", ephemeral=True)

    user_waiting_reply[msg.author.id] = [False, None]


# ============================================================
#                           START BOT
# ============================================================

asyncio.run(init_db())
bot.start()
