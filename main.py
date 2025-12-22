import interactions
from interactions import Button, ButtonStyle, ActionRow
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("TOKEN")
bot = interactions.Client(token=TOKEN)

@bot.event()
async def on_ready():
    print("ready")

CATEGORY_NAME = "BANK"

@interactions.slash_command(
    name="create",
    description="Create your bank account"
)
async def create(ctx: interactions.SlashContext):
    button = interactions.Button(
        style=interactions.ButtonStyle.PRIMARY,
        label="Create an account",
        custom_id="primary"
    )
    await ctx.send(
        "Click the button to create your bank account 🏦",
        components=interactions.ActionRow(button),
    )
@interactions.component_callback("primary")
async def primary_clicked(ctx: interactions.ComponentContext):
    await ctx.send("working fine")

bot.start()