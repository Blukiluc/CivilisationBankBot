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
    default_scope=int(os.getenv("GUILD_ID"))
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

async def check_minecraft_username(minecraft_username: str):
    async with aiosqlite.connect("bank.db") as db:
        cursor = await db.execute("SELECT * FROM users WHERE minecraft_username = ?", (minecraft_username,))
        user = await cursor.fetchone()
        return user

async def check_minecraft_uuid(minecraft_uuid: str):
    async with aiosqlite.connect("bank.db") as db:
        cursor = await db.execute("SELECT * FROM users WHERE minecraft_uuid = ?", (minecraft_uuid,))
        user = await cursor.fetchone()
        return user

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



# send create button command
@interactions.slash_command(
    name="create",
    description="Send \"Create Button\" message (admins only)."
)
async def create(ctx: interactions.SlashContext):
    button = interactions.Button(
        style=interactions.ButtonStyle.PRIMARY,
        label="Create an account",
        custom_id="primary"
    )
    await ctx.send(
        "🏦 Click the button to create your bank account:",
        components=interactions.ActionRow(button),
    )
    

# create channel
@interactions.component_callback("primary")
async def primary_clicked(ctx: interactions.ComponentContext):
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

    

# link
@interactions.slash_command(    
    name="link",
    description="Link your Minecraft account."
    )
async def link(ctx: interactions.SlashContext):
    linkModal = Modal(

        ShortText(
            custom_id="minecraft_username",
            label="Minecraft Username",
            required=True,
        ),
        ShortText(
            custom_id="minecraft_uuid",
            label="Minecraft UUID",
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
    elif await check_minecraft_username(minecraft_username) is not None:
        await ctx.send("❌ This Minecraft username is already linked to another Discord account.", ephemeral=True)
    elif await check_minecraft_uuid(minecraft_uuid) is not None:
        await ctx.send("❌ This Minecraft UUID is already linked to another Discord account.", ephemeral=True)
    else:
        await register_user_db(discord_id, discord_user, minecraft_username, minecraft_uuid)
        await ctx.send("✅ Your Minecraft account has been linked successfully.", ephemeral=True)

# link admin
@interactions.slash_command(name="linkadmin", description="link admin")
async def create(ctx: interactions.SlashContext):
    await register_user_db(ctx.author.id, ctx.author.username, ctx.author.username, ctx.author.id)
    await ctx.send("logged in", ephemeral=True)













asyncio.run(init_db())
bot.start()