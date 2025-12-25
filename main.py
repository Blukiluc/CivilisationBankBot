import interactions
from interactions import Button, ButtonStyle, ActionRow, modal_callback, Modal, ShortText
from dotenv import load_dotenv
import os
import aiosqlite
import asyncio
import aiohttp


load_dotenv()
TOKEN = os.getenv("TOKEN")
bot = interactions.Client(
    token=TOKEN,
    sync_commands=True,
    default_scope=int(os.getenv("GUILD_ID")),
    intents=interactions.Intents.ALL
)


# init db
async def init_db():
    async with aiosqlite.connect("bank.db") as db:
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


# fonctions db 
async def register_user_db(discord_id: int, discord_username: str, minecraft_username: str, minecraft_uuid: str):
    async with aiosqlite.connect("bank.db") as db:
        await db.execute("INSERT INTO users (discord_id, discord_username, minecraft_username, minecraft_uuid) VALUES (?, ?, ?, ?)", (discord_id, discord_username, minecraft_username, minecraft_uuid))
        await db.commit()

async def get_user(discord_id: int):
    async with aiosqlite.connect("bank.db") as db:
        cursor = await db.execute("SELECT * FROM users WHERE discord_id = ?", (discord_id,))
        user = await cursor.fetchone()
        return user
    
async def update_user_bank(discord_id: int, bank_channel_id: int):
    async with aiosqlite.connect("bank.db") as db:
        await db.execute("UPDATE users SET has_bank = 1, bank_channel_id = ? WHERE discord_id = ?", (bank_channel_id, discord_id))
        await db.commit()

async def update_user_balance(discord_id: int, balance: int):
    async with aiosqlite.connect("bank.db") as db:
        await db.execute("UPDATE users SET money = ? WHERE discord_id = ?", (balance, discord_id))
        await db.commit()

async def get_minecraft_username(minecraft_username: str):
    async with aiosqlite.connect("bank.db") as db:
        cursor = await db.execute("SELECT * FROM users WHERE minecraft_username = ?", (minecraft_username,))
        user = await cursor.fetchone()
        return user

async def get_minecraft_uuid(minecraft_uuid: str):
    async with aiosqlite.connect("bank.db") as db:
        cursor = await db.execute("SELECT * FROM users WHERE minecraft_uuid = ?", (minecraft_uuid,))
        user = await cursor.fetchone()
        return user

async def log_transaction(sender_discord_id: int, receiver_discord_id: int, amount: int):
    async with aiosqlite.connect("bank.db") as db:
        await db.execute("INSERT INTO transactions (sender_discord_id, receiver_discord_id, amount) VALUES (?, ?, ?)", (sender_discord_id, receiver_discord_id, amount))
        await db.commit()

# check minecraft profile
async def get_minecraft_profile(username: str):
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
                return {
                    "exists": False,
                    "uuid": None,
                    "username": None
                }
            else:
                return {
                    "exists": False,
                    "uuid": None,
                    "username": None,
                    "error": f"Erreur API Mojang: {response.status}"
                }



@bot.event()
async def on_ready():
    print("Bot online!")
    await bot.synchronise_interactions()



CATEGORY_NAME = "Banks"



# link
@interactions.slash_command(name="link", description="Link your Minecraft account.")
async def link(ctx: interactions.SlashContext):
    linkModal = Modal(
        ShortText(
            custom_id="minecraft_username",
            label="Minecraft Username",
            required=True,
        ),
        ShortText(
            custom_id="minecraft_uuid",
            label="Minecraft UUID (Without dashes)",
            required=True,
        ),
        title="Link your Minecraft account",
        custom_id="link_modal",
    )
    await ctx.send_modal(linkModal)
@modal_callback("link_modal")
async def handle_modal(ctx: interactions.ModalContext):
    minecraft_username = ctx.responses["minecraft_username"].lower()
    minecraft_uuid = ctx.responses["minecraft_uuid"].lower()
    discord_user = ctx.author.username
    discord_id = ctx.author.id
    profile = await get_minecraft_profile(minecraft_username)
    if await get_user(discord_id) is not None:
        await ctx.send("❌ Your Discord account is already linked to a Minecraft account.", ephemeral=True)
    elif profile["exists"] is False:
        await ctx.send("❌ The provided Minecraft username does not exist.", ephemeral=True)
    elif profile["uuid"].lower() != minecraft_uuid:
        await ctx.send("❌ The provided Minecraft UUID does not match the username.", ephemeral=True)
    elif await get_minecraft_username(minecraft_username) is not None:
        await ctx.send("❌ This Minecraft username is already linked to another Discord account.", ephemeral=True)
    elif await get_minecraft_uuid(minecraft_uuid) is not None:
        await ctx.send("❌ This Minecraft UUID is already linked to another Discord account.", ephemeral=True)
    else:
        await register_user_db(discord_id, discord_user, minecraft_username, minecraft_uuid)
        print("User registered:", discord_id, discord_user, minecraft_username, minecraft_uuid)
        await ctx.send("✅ Your Minecraft account has been linked successfully.", ephemeral=True)


# create channel
@interactions.component_callback("create_bank_button")
async def create_bank_button_clicked(ctx: interactions.ComponentContext):
    # Create new channel
    server = ctx.guild
    user = ctx.user
    category=interactions.utils.get(server.channels, name=CATEGORY_NAME, type=interactions.ChannelType.GUILD_CATEGORY)
    if category is None:
        await ctx.send("Category not found. Please contact an admin.", ephemeral=True)
        return
    user_db = await get_user(user.id)
    if user_db is None:
        await ctx.send("You need to link your Minecraft account first using /link command.", ephemeral=True)
        return
    if user_db[6] == 1:
        await ctx.send("You already have a bank account: <#{}>".format(user_db[7]), ephemeral=True)
        return
    channel = await server.create_text_channel(name=f"{user.username}-bank", category=category)
    await update_user_bank(user.id, channel.id)
    await ctx.send(f"Bank created! <#{channel.id}>", ephemeral=True)

    # Default message
    buttonBalance = interactions.Button(
        style=interactions.ButtonStyle.GREEN,
        label="Check balance",
        custom_id="bank_balance"
    )
    buttonSendMoney = interactions.Button(
        style=interactions.ButtonStyle.RED,
        label="Send money",
        custom_id="bank_send_money"
    )
    buttonLogs = interactions.Button(
        style=interactions.ButtonStyle.GRAY,
        label="View logs",
        custom_id="bank_logs"
    )
    await channel.send(
        f"Welcome <@{user.id}>! Your bank account has been created.",
        components=interactions.ActionRow(buttonBalance, buttonSendMoney, buttonLogs)
    )


# check balance
@interactions.component_callback("bank_balance")
async def bank_balance_clicked(ctx: interactions.ComponentContext):
    user_db = await get_user(ctx.user.id)
    if user_db is None:
        await ctx.send("Error: Please contact an admin.", ephemeral=True)
        return
    balance = user_db[5]
    await ctx.send(f"💰 Your current balance is: {balance} social credits.", ephemeral=True)


# send money
@interactions.component_callback("bank_send_money")
async def bank_send_money(ctx: interactions.SlashContext):
    sendMoneyModal = Modal(
        ShortText(
            custom_id="username_recipient",
            label="Minecraft Username",
            required=True,
        ),
        ShortText(
            custom_id="amount",
            label="Amount",
            required=True,
        ),
        title="Send money",
        custom_id="send_money_modal",
    )
    await ctx.send_modal(sendMoneyModal)
@modal_callback("send_money_modal")
async def handle_send_money_modal(ctx: interactions.ModalContext):
    minecraft_username = ctx.responses["username_recipient"].lower()
    amount = int(ctx.responses["amount"])
    sender_db = await get_user(ctx.author.id)
    recipient_db = await get_minecraft_username(minecraft_username)
    if recipient_db is None:
        await ctx.send("❌ The recipient Minecraft username is not linked to any Discord account.", ephemeral=True)
        return
    if amount <= 0:
        await ctx.send("❌ Invalid amount.", ephemeral=True)
        return
    if sender_db[5] < amount:
        await ctx.send("❌ You do not have enough balance to complete this transaction.", ephemeral=True)
        return
    if recipient_db[1] == ctx.author.id:
        await ctx.send("❌ You cannot send money to yourself.", ephemeral=True)
        return
    if recipient_db[7] is None:
        await ctx.send("❌ The recipient does not have a bank account.", ephemeral=True)
        return
    # Update balances
    new_sender_balance = sender_db[5] - amount
    new_recipient_balance = recipient_db[5] + amount
    await update_user_balance(ctx.author.id, new_sender_balance)
    await update_user_balance(recipient_db[1], new_recipient_balance)
    await log_transaction(ctx.author.id, recipient_db[1], amount)
    await ctx.send(f"✅ Successfully sent {amount} social credits to <@{recipient_db[1]}>.", ephemeral=True)
    recipient_channel = bot.get_channel(recipient_db[7])
    await recipient_channel.send(f"💸 You have received {amount} social credits from <@{ctx.author.id}>.")


# get names
@interactions.slash_command(name="minecraftname", description="Get the Minecraft username of a Discord user")
@interactions.slash_option(
    name="user",
    description="Discord username",
    opt_type=interactions.OptionType.USER,
    required=True
)
async def minecraft_name(ctx: interactions.SlashContext, user: interactions.User):
    user_db = await get_user(user.id)
    if user_db is None:
        await ctx.send("User not found.", ephemeral=True)
        return
    minecraft_username = user_db[3]
    profile = await get_minecraft_profile(minecraft_username)
    await ctx.send(f"The Minecraft username of <@{user.id}> is: {profile['username']}", ephemeral=True)

@interactions.slash_command(name="discordname", description="Get the Discord username of a Minecraft account")
@interactions.slash_option(
    name="minecraft_username",
    description="Minecraft username",
    opt_type=interactions.OptionType.STRING,
    required=True
)
async def discord_name(ctx: interactions.SlashContext, minecraft_username: str):
    user_db = await get_minecraft_username(minecraft_username.lower())
    if user_db is None:
        await ctx.send("User not found.", ephemeral=True)
        return
    discord_id = user_db[1]
    await ctx.send(f"The Discord username of Minecraft user '{minecraft_username}' is: <@{discord_id}>", ephemeral=True)


# admin cmds
@interactions.slash_command(name="admin", description="Admin commands")
async def admin(ctx: interactions.SlashContext):
    linkAdminButton = interactions.Button(
        style=interactions.ButtonStyle.GREEN,
        label="Link admin",
        custom_id="link_admin_button"
    )
    setMoneyButton = interactions.Button(
        style=interactions.ButtonStyle.RED,
        label="Set money",
        custom_id="set_money_button"
    )
    createBankButtonAdmin = interactions.Button(
        style=interactions.ButtonStyle.PRIMARY,
        label="Create Bank button",
        custom_id="create_bank_button_admin"
    )
    configButton = interactions.Button(
        style=interactions.ButtonStyle.GRAY,
        label="Config",
        custom_id="config_button_admin"
    )
    await ctx.send(
        "Admin commands:",
        components=interactions.ActionRow(linkAdminButton, setMoneyButton, createBankButtonAdmin, configButton),
        ephemeral=True
    )

@interactions.component_callback("create_bank_button_admin")
async def create(ctx: interactions.ComponentContext):
    await ctx.defer(ephemeral=True)
    button = interactions.Button(
        style=interactions.ButtonStyle.PRIMARY,
        label="Create an account",
        custom_id="create_bank_button"
    )
    await ctx.channel.send(
        "🏦 Click the button to create your bank account:",
        components=interactions.ActionRow(button),
    )

@interactions.component_callback("link_admin_button")
async def link_admin(ctx: interactions.ComponentContext):
    user_db = await get_user(ctx.author.id)
    if user_db is not None:
        await ctx.send("❌ Your Discord account is already linked to a Minecraft account.", ephemeral=True)
        return
    await register_user_db(ctx.author.id, ctx.author.username, ctx.author.username, ctx.author.id)
    await ctx.send("✅ Your Discord account has been linked as admin.", ephemeral=True)

user_waiting_reply = {}
@interactions.component_callback("set_money_button")
async def set_money(ctx: interactions.ComponentContext):
    global user_waiting_reply
    user_waiting_reply[ctx.author.id] = [True, ctx.channel.id]
    await ctx.channel.send("Discord user id and amount separated by a space: \nWrite \"Cancel\" to cancel.", ephemeral=True)
    return
@interactions.listen()
async def on_message_create(event: interactions.events.MessageCreate):
    global user_waiting_reply
    msg = event.message

    if msg.author.bot:
        return
    
    if not user_waiting_reply.get(msg.author.id, [False])[0]:
        return
    
    if msg.author.id not in user_waiting_reply:
        return

    if msg.channel.id != user_waiting_reply.get(msg.author.id, [None, None])[1]:
        return

    if not msg.content:
        return

    if msg.content.lower().startswith("!ping"):
        await msg.channel.send("pong")

    if msg.content.lower() == "cancel":
        user_waiting_reply[msg.author.id] = [False, None]
        await msg.channel.send("Operation cancelled.", ephemeral=True)
        return
    
    if len(msg.content) >= 19:
        amount_str = msg.content.split(" ")[1]
        target_str = msg.content.split(" ")[0]
        if len(msg.content.split(" ")) != 2 or not amount_str.isdigit() or not target_str.isdigit():
            await msg.channel.send("Invalid format. Operation cancelled.", ephemeral=True)
            user_waiting_reply[msg.author.id] = [False, None]
            return
        print("setting money")
        amount = int(amount_str)
        target_id = int(target_str)
        target_db = await get_user(target_id)
        if target_db is None:
            await msg.channel.send("User not found. Operation cancelled.", ephemeral=True)
            user_waiting_reply[msg.author.id] = [False, None]
            return
        print("updating balance")
        await update_user_balance(target_id, amount)
        await msg.channel.send(f"Set {amount} social credits to {target_db[2]}.", ephemeral=True)
        user_waiting_reply[msg.author.id] = [False, None]




asyncio.run(init_db())
bot.start()