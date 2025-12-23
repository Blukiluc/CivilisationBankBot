import interactions
from interactions import Button, ButtonStyle, ActionRow
from dotenv import load_dotenv
import os

load_dotenv()
TOKEN = os.getenv("TOKEN")
bot = interactions.Client(token=TOKEN)

@bot.event()
async def on_ready():
    print("Bot online!")

CATEGORY_NAME = "Banks"

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
        "🏦 Click the button to create your bank account:",
        components=interactions.ActionRow(button),
    )
    
@interactions.component_callback("primary")
async def primary_clicked(ctx: interactions.ComponentContext):
    # Create new channel
    server = ctx.guild
    user = ctx.user
    category=interactions.utils.get(server.channels, name=CATEGORY_NAME, type=interactions.ChannelType.GUILD_CATEGORY)
    if category is None:
        await ctx.send("Category not found. Please contact an admin.", ephemeral=True)
        return
    channel = await server.create_text_channel(name=f"{user.username}-bank", category=category)
    await ctx.send(f"Bank created! <#{channel.id}>", ephemeral=True)

    # Default message
    buttonDeposit = interactions.Button(
        style=interactions.ButtonStyle.GREEN,
        label="Deposit",
        custom_id="bank_deposit"
    )
    buttonWithdraw = interactions.Button(
        style=interactions.ButtonStyle.RED,
        label="Withdraw",
        custom_id="bank_withdraw"
    )
    buttonLoan = interactions.Button(
        style=interactions.ButtonStyle.GREY,
        label="Manage loans",
        custom_id="bank_loan"
    )
    await channel.send(
        f"Welcome <@{user.id}>! Your bank account has been created.",
        components=interactions.ActionRow(buttonDeposit, buttonWithdraw, buttonLoan)
    )

bot.start()