import os
import json
import asyncio
from datetime import datetime
from dotenv import load_dotenv
import aiosqlite
import aiohttp
import interactions
from interactions import (
    Button,
    ButtonStyle,
    ActionRow,
    modal_callback,
    Modal,
    ShortText
)

# ============================================================
#                        CONFIG / INIT
# ============================================================

load_dotenv()
TOKEN = os.getenv("TOKEN")
BOT_ID = 1450840919615078440

bot = interactions.Client(
    token=TOKEN,
    sync_commands=True,
    default_scope=int(os.getenv("GUILD_ID")),
    intents=interactions.Intents.ALL
)


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
            is_task_reward INTEGER DEFAULT 0,
            is_job_reward INTEGER DEFAULT 0,
            amount INTEGER NOT NULL,
            date DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Task table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            reward INTEGER NOT NULL,
            author_discord_id INTEGER NOT NULL,
            claimed_by_discord_ids TEXT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Job table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            message_id INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            description TEXT NOT NULL,
            reward INTEGER NOT NULL,
            author_discord_id INTEGER NOT NULL,
            claimed_by_discord_ids TEXT DEFAULT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        """)

        # Config table
        await db.execute("""
        CREATE TABLE IF NOT EXISTS config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category_id INTEGERs,
            task_channel_id INTEGER,
            task_admin_channel_id INTEGER,
            job_channel_id INTEGER,
            job_admin_channel_id INTEGER
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


async def get_user(discord_id: int = None, discord_username: str = None, minecraft_username: str = None, minecraft_uuid: str = None, bank_channel_id: int = None):
    async with aiosqlite.connect("bank.db") as db:
        if discord_id is not None:
            cursor = await db.execute("SELECT * FROM users WHERE discord_id = ?",
            (discord_id,))
        elif discord_username is not None:
            cursor = await db.execute("SELECT * FROM users WHERE discord_username = ?",
            (discord_username,))
        elif minecraft_username is not None:
            cursor = await db.execute("SELECT * FROM users WHERE minecraft_username = ?",
            (minecraft_username,))
        elif minecraft_uuid is not None:
            cursor = await db.execute("SELECT * FROM users WHERE minecraft_uuid = ?",
            (minecraft_uuid,))
        elif bank_channel_id is not None:
            cursor = await db.execute("SELECT * FROM users WHERE bank_channel_id = ?",
            (bank_channel_id,))
        else:
            return None
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


async def log_transaction(sender_discord_id: int, receiver_discord_id: int, is_task_reward: int = 0, is_job_reward: int = 0, amount: int = 0):
    async with aiosqlite.connect("bank.db") as db:
        await db.execute(
            "INSERT INTO transactions (sender_discord_id, receiver_discord_id, is_task_reward, is_job_reward, amount) VALUES (?, ?, ?, ?, ?)",
            (sender_discord_id, receiver_discord_id, is_task_reward, is_job_reward, amount)
        )
        await db.commit()


async def create_task(message_id: int, name: str, description: str, reward: int, author_discord_id: int):
    async with aiosqlite.connect("bank.db") as db:
        await db.execute(
            "INSERT INTO tasks (message_id, name, description, reward, author_discord_id) VALUES (?, ?, ?, ?, ?)",
            (message_id, name, description, reward, author_discord_id)
        )
        await db.commit()


async def get_task(message_id: int):
    async with aiosqlite.connect("bank.db") as db:
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE message_id = ?",
            (message_id,)
        )
        return await cursor.fetchone()


async def get_task_from_name(name: str):
    async with aiosqlite.connect("bank.db") as db:
        cursor = await db.execute(
            "SELECT * FROM tasks WHERE name = ?",
            (name,)
        )
        return await cursor.fetchone()


async def change_task_claimed_by(message_id: int, claimed_by_discord_ids: str):
    async with aiosqlite.connect("bank.db") as db:
        await db.execute(
            "UPDATE tasks SET claimed_by_discord_ids = ? WHERE message_id = ?",
            (claimed_by_discord_ids, message_id)
        )
        await db.commit()


async def create_job(message_id: int, name: str, description: str, reward: int, author_discord_id: int):
    async with aiosqlite.connect("bank.db") as db:
        await db.execute(
            "INSERT INTO jobs (message_id, name, description, reward, author_discord_id) VALUES (?, ?, ?, ?, ?)",
            (message_id, name, description, reward, author_discord_id)
        )
        await db.commit()


async def get_job(message_id: int):
    async with aiosqlite.connect("bank.db") as db:
        cursor = await db.execute(
            "SELECT * FROM jobs WHERE message_id = ?",
            (message_id,)
        )
        return await cursor.fetchone()


async def get_job_from_name(name: str):
    async with aiosqlite.connect("bank.db") as db:
        cursor = await db.execute(
            "SELECT * FROM jobs WHERE name = ?",
            (name,)
        )
        return await cursor.fetchone()


async def change_job_claimed_by(message_id: int, claimed_by_discord_ids: str):
    async with aiosqlite.connect("bank.db") as db:
        await db.execute(
            "UPDATE jobs SET claimed_by_discord_ids = ? WHERE message_id = ?",
            (claimed_by_discord_ids, message_id)
        )
        await db.commit()


async def change_config(category_id: int = None, task_channel_id: int = None, task_admin_channel_id: int = None, job_channel_id: int = None, job_admin_channel_id: int = None):
    async with aiosqlite.connect("bank.db") as db:
        if category_id is not None:
            await db.execute(
                "UPDATE config SET category_id = ? WHERE id = 1",
                (category_id,)
            )
        if task_channel_id is not None:
            await db.execute(
                "UPDATE config SET task_channel_id = ? WHERE id = 1",
                (task_channel_id,)
            )
        if task_admin_channel_id is not None:
            await db.execute(
                "UPDATE config SET task_admin_channel_id = ? WHERE id = 1",
                (task_admin_channel_id,)
            )
        if job_channel_id is not None:
            await db.execute(
                "UPDATE config SET job_channel_id = ? WHERE id = 1",
                (job_channel_id,)
            )
        if job_admin_channel_id is not None:
            await db.execute(
                "UPDATE config SET job_admin_channel_id = ? WHERE id = 1",
                (job_admin_channel_id,)
            )
        await db.commit()


async def get_config():
    async with aiosqlite.connect("bank.db") as db:
        cursor = await db.execute(
            "SELECT * FROM config WHERE id = 1"
        )
        return await cursor.fetchone()


# ============================================================
#                        CONSTANTS
# ============================================================

config = asyncio.run(get_config()) if asyncio.run(get_config()) is not None else (1, 0, 0, 0, 0, 0)

CATEGORY_ID = config[1]
TASK_CHANNEL_ID = config[2]
TASK_ADMIN_CHHANNEL_ID = config[3]
JOB_CHANNEL_ID = config[4]
JOB_ADMIN_CHANNEL_ID = config[5]


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

@interactions.slash_command(
        name="link",
        description="Link your Minecraft account."
)
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
    if await get_user(discord_id=discord_id) is not None:
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
    category = interactions.utils.get(server.channels, id=CATEGORY_ID, type=interactions.ChannelType.GUILD_CATEGORY)
    if category is None:
        return await ctx.send("Category not found.", ephemeral=True)

    user_db = await get_user(discord_id=user.id)

    if user_db is None:
        return await ctx.send("Link your account first using /link.", ephemeral=True)

    if user_db[6] == 1:
        return await ctx.send(f"You already have a bank: <#{user_db[7]}>", ephemeral=True)

    # Create private bank channel
    channel = await server.create_text_channel(
        name=f"{user.username}-bank",
        category=category,
        permission_overwrites=[
            interactions.PermissionOverwrite(
                id=server.default_role.id,
                type=interactions.OverwriteType.ROLE,
                deny=interactions.Permissions.VIEW_CHANNEL,
            ),
            interactions.PermissionOverwrite(
                id=user.id,
                type=interactions.OverwriteType.MEMBER,
                allow=(
                    interactions.Permissions.VIEW_CHANNEL
                    | interactions.Permissions.SEND_MESSAGES
                    | interactions.Permissions.READ_MESSAGE_HISTORY
                ),
            ),
            interactions.PermissionOverwrite(
                id=BOT_ID,
                type=interactions.OverwriteType.MEMBER,
                allow=(
                    interactions.Permissions.VIEW_CHANNEL
                    | interactions.Permissions.SEND_MESSAGES
                    | interactions.Permissions.READ_MESSAGE_HISTORY
                ),
            ),
        ],
    )
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
    user_db = await get_user(discord_id=ctx.user.id)
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

    sender_db = await get_user(discord_id=ctx.author.id)
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
    await log_transaction(ctx.author.id, recipient_db[1], 0, 0, amount)

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

@interactions.slash_command(
        name="minecraftname",
        description="Get Minecraft username from Discord user."
)
@interactions.slash_option(
    name="user",
    description="Target user",
    opt_type=interactions.OptionType.USER,
    required=True
)
async def minecraft_name(ctx: interactions.SlashContext, user: interactions.User):
    user_db = await get_user(discord_id=user.id)
    if user_db is None:
        return await ctx.send("User not found.", ephemeral=True)

    profile = await get_minecraft_profile(user_db[3])
    await ctx.send(f"Minecraft username: **{profile['username']}**", ephemeral=True)


@interactions.slash_command(
        name="discordname",
        description="Get Discord user from Minecraft username."
)
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


# ===========================================================
#                         TASK SYSTEM
# ===========================================================

@interactions.slash_command(
    name="task",
    description="Task system",
    default_member_permissions=interactions.Permissions.ADMINISTRATOR
)
async def task(ctx: interactions.SlashContext):
    """Base command placeholder"""
    pass

@task.subcommand(
    sub_cmd_name="create",
    sub_cmd_description="Create a new task"
)
@interactions.slash_option(
    name="name",
    description="Task name",
    opt_type=interactions.OptionType.STRING,
    required=True
)
@interactions.slash_option(
    name="description",
    description="Task description",
    opt_type=interactions.OptionType.STRING,
    required=True
)
@interactions.slash_option(
    name="reward",
    description="Reward in Social Credits",
    opt_type=interactions.OptionType.INTEGER,
    required=True
)
async def task_create(ctx: interactions.SlashContext, name: str, description: str, reward: int):
    """"Creates a new task and posts it in the task channel."""

    embed = interactions.Embed(
        title=name,
        description=(
            f"## {description}\n"
            f"### 💰 **Reward:** {reward} Social Credits"
        ),
        color=0xFF5500
    )
    
    button = interactions.Button(
        style=interactions.ButtonStyle.PRIMARY,
        label="Claim task",
        custom_id="claim_task_button"
    )

    channel = await ctx.client.fetch_channel(TASK_CHANNEL_ID)
    message = await channel.send(
        embeds=embed,
        components=button
    )

    await create_task(message.id, name, description, reward, ctx.author.id)
    await ctx.send("Task created successfully.", ephemeral=True)

@interactions.component_callback("claim_task_button")
async def claim_task_callback(ctx: interactions.ComponentContext):
    """Triggered when someone claims the task."""

    author_db = await get_user(discord_id=ctx.author.id)
    if author_db is None:
        return await ctx.send("❌ Link your account first using /link.", ephemeral=True)
    if author_db[6] == 0:
        return await ctx.send("❌ You need a bank account to claim tasks.", ephemeral=True)
    
    task_db = await get_task(ctx.message.id)
    if task_db is None:
        return await ctx.send("❌ Task not found.", ephemeral=True)

    raw_claimed_by = task_db[6]
    if raw_claimed_by:
        claimed_by = json.loads(raw_claimed_by)
    else:
        claimed_by = {}
    if str(ctx.author.id) in claimed_by:
            return await ctx.send("❌ You have already claimed this task.", ephemeral=True)

    claimed_by[str(ctx.author.id)] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await change_task_claimed_by(ctx.message.id, json.dumps(claimed_by))

    minecraft_username = (await get_minecraft_profile(author_db[3]))['username']
    await bot.get_channel(TASK_ADMIN_CHHANNEL_ID).send(f"📝 The task **{task_db[2]}** has been claimed by {ctx.author.mention} ({minecraft_username})")

    await ctx.send("✅ You claimed the task!", ephemeral=True)

@task.subcommand(
    sub_cmd_name="accept",
    sub_cmd_description="Accept a claimed job"
)
@interactions.slash_option(
    name="task",
    description="Task name",
    opt_type=interactions.OptionType.STRING,
    required=True
)
@interactions.slash_option(
    name="claimer",
    description="Minecraft username who claimed the task",
    opt_type=interactions.OptionType.STRING,
    required=True
)
async def job_accept(ctx: interactions.SlashContext, task: str, claimer: str):
    """Accepts a claimed task."""
    
    task_db = await get_task_from_name(task)
    if task_db is None:
        return await ctx.send("❌ Task not found.", ephemeral=True)
    
    claimer_db = await get_user(minecraft_username=claimer.lower())
    if claimer_db is None:
        return await ctx.send("❌ Claimer not found.", ephemeral=True)
    if claimer_db[6] == 0:
        return await ctx.send("❌ Claimer has no bank account.", ephemeral=True)
    
    raw_claimed_by = task_db[6]
    if raw_claimed_by:
        claimed_by = json.loads(raw_claimed_by)
    else:
        claimed_by = {}
    if str(claimer_db[1]) not in claimed_by:
        return await ctx.send("❌ This task was not claimed by that user.", ephemeral=True)

    reward = task_db[4]
    claimer_balance = claimer_db[5]
    await update_user_balance(claimer_db[1], claimer_balance + reward)
    await log_transaction(0, claimer_db[1], 0, 1, reward)
    await ctx.send(f"✅ Task accepted. {reward} credits sent to {claimer_db[2]}.", ephemeral=True)

    
# ============================================================
#                          JOB SYSTEM
# ============================================================

@interactions.slash_command(
    name="job",
    description="Job system",
    default_member_permissions=interactions.Permissions.ADMINISTRATOR
)
async def job(ctx: interactions.SlashContext):
    """Job system placeholder."""
    pass

@job.subcommand(
    sub_cmd_name="create",
    sub_cmd_description="Create a new job"
)
@interactions.slash_option(
    name="name",
    description="Job name",
    opt_type=interactions.OptionType.STRING,
    required=True
)
@interactions.slash_option(
    name="description",
    description="Job description",
    opt_type=interactions.OptionType.STRING,
    required=True
)
@interactions.slash_option(
    name="reward",
    description="Reward in Social Credits",
    opt_type=interactions.OptionType.INTEGER,
    required=True
)
async def job_create(ctx: interactions.SlashContext, name: str, description: str, reward: int):
    """Creates a new job (functionality to be implemented)."""

    embed = interactions.Embed(
        title=name,
        description=(
            f"## {description}\n"
            f"### 💰 **Reward:** {reward} Social Credits"
        ),
        color=0xFF5500
    )

    button = interactions.Button(
        style=interactions.ButtonStyle.PRIMARY,
        label="Claim job",
        custom_id="claim_job_button"
    )

    channel = await ctx.client.fetch_channel(JOB_CHANNEL_ID)
    message = await channel.send(
        embeds=embed,
        components=button
    )

    await create_job(message.id, name, description, reward, ctx.author.id)
    await ctx.send("Job created successfully.", ephemeral=True)

@interactions.component_callback("claim_job_button")
async def claim_job_callback(ctx: interactions.ComponentContext):
    """Triggered when someone claims the job."""

    author_db = await get_user(discord_id=ctx.author.id)
    if author_db is None:
        return await ctx.send("❌ Link your account first using /link.", ephemeral=True)
    if author_db[6] == 0:
        return await ctx.send("❌ You need a bank account to claim jobs.", ephemeral=True)
    
    job_db = await get_job(ctx.message.id)
    if job_db is None:
        return await ctx.send("❌ Job not found.", ephemeral=True)

    raw_claimed_by = job_db[6]
    if raw_claimed_by:
        claimed_by = json.loads(raw_claimed_by)
    else:
        claimed_by = {}
    if str(ctx.author.id) in claimed_by:
            return await ctx.send("❌ You have already claimed this job.", ephemeral=True)

    claimed_by[str(ctx.author.id)] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    await change_job_claimed_by(ctx.message.id, json.dumps(claimed_by))

    minecraft_username = (await get_minecraft_profile(author_db[3]))['username']
    await bot.get_channel(JOB_ADMIN_CHANNEL_ID).send(f"📝 The job **{job_db[2]}** has been claimed by {ctx.author.mention} ({minecraft_username})")

    await ctx.send("✅ You claimed the job!", ephemeral=True)

@job.subcommand(
    sub_cmd_name="accept",
    sub_cmd_description="Accept a claimed job"
)
@interactions.slash_option(
    name="job",
    description="Job name",
    opt_type=interactions.OptionType.STRING,
    required=True
)
@interactions.slash_option(
    name="claimer",
    description="Minecraft username who claimed the job",
    opt_type=interactions.OptionType.STRING,
    required=True
)
async def job_accept(ctx: interactions.SlashContext, job: str, claimer: str):
    """Accepts a claimed job."""
    
    job_db = await get_job_from_name(job)
    if job_db is None:
        return await ctx.send("❌ Job not found.", ephemeral=True)
    
    claimer_db = await get_user(minecraft_username=claimer.lower())
    if claimer_db is None:
        return await ctx.send("❌ Claimer not found.", ephemeral=True)
    if claimer_db[6] == 0:
        return await ctx.send("❌ Claimer has no bank account.", ephemeral=True)
    
    raw_claimed_by = job_db[6]
    if raw_claimed_by:
        claimed_by = json.loads(raw_claimed_by)
    else:
        claimed_by = {}
    if str(claimer_db[1]) not in claimed_by:
        return await ctx.send("❌ This job was not claimed by that user.", ephemeral=True)
    
    reward = job_db[4]
    claimer_balance = claimer_db[5]
    await update_user_balance(claimer_db[1], claimer_balance + reward)
    await log_transaction(0, claimer_db[1], 0, 1, reward)
    await ctx.send(f"✅ Job accepted. {reward} credits sent to {claimer_db[2]}.", ephemeral=True)


# ============================================================
#                        ADMIN COMMANDS
# ============================================================

@interactions.slash_command(
    name="admin",
    description="Admin controls",
    default_member_permissions=interactions.Permissions.ADMINISTRATOR
)
async def admin(ctx: interactions.SlashContext):
    """Shows admin buttons."""
    btn_link = Button(style=ButtonStyle.GREEN, label="Link admin", custom_id="link_admin_button")
    btn_set = Button(style=ButtonStyle.RED, label="Set money", custom_id="set_money_button")
    btn_create = Button(style=ButtonStyle.PRIMARY, label="Create Bank button", custom_id="create_bank_button_admin")
    # btn_config = Button(style=ButtonStyle.GRAY, label="Config", custom_id="config_button_admin")

    await ctx.send(
        "Admin commands:",
        # components=ActionRow(btn_link, btn_set, btn_create, btn_config),
        components=ActionRow(btn_link, btn_set, btn_create),
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
    if await get_user(discord_id=ctx.author.id):
        return await ctx.send("❌ Already linked.", ephemeral=True)

    await register_user_db(ctx.author.id, ctx.author.username, ctx.author.username, ctx.author.id)
    await ctx.send("✅ Linked as admin.", ephemeral=True)


# ============================================================
#                 SET MONEY SYSTEM (ADMIN)
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

    target_db = await get_user(discord_id=target_id)

    if target_db is None:
        user_waiting_reply[msg.author.id] = [False, None]
        return await msg.channel.send("User not found.", ephemeral=True)

    await update_user_balance(target_id, amount)
    await msg.channel.send(f"Balance updated: **{amount}** for **{target_db[2]}**.", ephemeral=True)

    user_waiting_reply[msg.author.id] = [False, None]


# ============================================================
#                            CONFIG
# ============================================================

@interactions.slash_command(
    name="config",
    description="Bot configuration",
    default_member_permissions=interactions.Permissions.ADMINISTRATOR
)
async def config(ctx: interactions.SlashContext):
    """Job system placeholder."""
    pass

@config.subcommand(
    sub_cmd_name="set-bank-category",
    sub_cmd_description="Set the bank category ID"
)
@interactions.slash_option(
    name="category_id",
    description="Bank category ID",
    opt_type=interactions.OptionType.INTEGER,
    required=True
)
async def set_bank_category(ctx: interactions.SlashContext, category_id: int):
    """Set the bank category ID."""
    await change_config(bank_category_id=category_id)
    await ctx.send("Bank category set.", ephemeral=True)

@config.subcommand(
    sub_cmd_name="set-task-channel",
    sub_cmd_description="Set the task channel ID"
)
@interactions.slash_option(
    name="channel_id",
    description="Task channel ID",
    opt_type=interactions.OptionType.INTEGER,
    required=True
)
async def set_task_channel(ctx: interactions.SlashContext, channel_id: int):
    """Set the task channel ID."""
    await change_config(task_channel_id=channel_id)
    await ctx.send("Task channel set.", ephemeral=True)

@config.subcommand(
    sub_cmd_name="set-task-admin-channel",
    sub_cmd_description="Set the task admin channel ID"
)
@interactions.slash_option(
    name="channel_id",
    description="Task admin channel ID",
    opt_type=interactions.OptionType.INTEGER,
    required=True
)
async def set_task_admin_channel(ctx: interactions.SlashContext, channel_id: int):
    """Set the task admin channel ID."""
    await change_config(task_admin_channel_id=channel_id)
    await ctx.send("Task admin channel set.", ephemeral=True)

@config.subcommand(
    sub_cmd_name="set-job-channel",
    sub_cmd_description="Set the job channel ID"
)
@interactions.slash_option(
    name="channel_id",
    description="Job channel ID",
    opt_type=interactions.OptionType.INTEGER,
    required=True
)
async def set_job_channel(ctx: interactions.SlashContext, channel_id: int):
    """Set the job channel ID."""
    await change_config(job_channel_id=channel_id)
    await ctx.send("Job channel set.", ephemeral=True)

@config.subcommand(
    sub_cmd_name="set-job-admin-channel",
    sub_cmd_description="Set the job admin channel ID"
)
@interactions.slash_option(
    name="channel_id",
    description="Job admin channel ID",
    opt_type=interactions.OptionType.INTEGER,
    required=True
)
async def set_job_admin_channel(ctx: interactions.SlashContext, channel_id: int):
    """Set the job admin channel ID."""
    await change_config(job_admin_channel_id=channel_id)
    await ctx.send("Job admin channel set.", ephemeral=True)


# ============================================================
#                           START BOT
# ============================================================

asyncio.run(init_db())
bot.start()