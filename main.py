import os
from dotenv import load_dotenv

import interactions
from interactions import slash_command, SlashContext, OptionType, slash_option, listen, ModalContext
from interactions import message_context_menu, ContextMenuContext, Message, Modal, ShortText

from SQLManager import SQLManager

load_dotenv()

bot = interactions.Client(intents=interactions.Intents.ALL)

# === GLOBALS ===
# One day I'll integrate this into a place that uses less memory. Today is not that day, and neither is tomorrow
categories = ["Worst Idea", "Best Idea", "Biggest Lie", "Worst Bit", "Best Bit", "Least Funny Recurring Joke",
              "Craziest Working Gaslight", "Funniest Recurring Joke", "Dumbest Discussion"]
database = SQLManager()  # Database connection


# === EVENTS ===


@listen()
async def on_startup():
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")
    print("------\n")


# === COMMANDS ===


@slash_command(
    name="ping",
    description="Ping the bot to see if it's alive."
)
async def ping(ctx: SlashContext):
    await ctx.send("Pong!")


@slash_command(
    name="about",
    description="General information about the bot",
)
async def about(ctx: SlashContext):
    await ctx.send("Created by Connor Midgley.\n"
                   "Source code available at https://github.com/GameMagma/NewNakamoto \n"
                   "Version 3.0.0"
                   "New features:"
                   "- You can now nominate messages for The Orwell Awards")


@slash_command(
    name="dbtest",
    description="Tests the database connection.",
    scopes=[os.getenv("TEST_GUILD_ID")]
)
async def dbtest(ctx: SlashContext):
    await ctx.send(database.get_wallet(ctx.author.id)[1])


# === CONTEXT MENU COMMANDS ===
@message_context_menu(
    name="repeat",
    scopes=[os.getenv("TEST_GUILD_ID")]
)
async def repeat(ctx: ContextMenuContext):
    msg: Message = ctx.target
    await ctx.send(f"You said: {msg.content}")


@message_context_menu(
    name="Nominate",
)
async def nominate(ctx: ContextMenuContext):
    """
    Comes up with a selection of the current year's categories to nominate the selected message for.

    :param ctx: The message this command was called on
    """
    msg: Message = ctx.target
    category_selection = Modal(
        ShortText(
            label="Category",
            placeholder="Type the exact name of the category to nominate for",
            custom_id="category"),
        title="Nominate",
        custom_id="category_selection"
    )
    await ctx.send_modal(modal=category_selection)  # Send a modal that collects the category to nominate

    # Wait for modal response, then retrieve
    modal_ctx: ModalContext = await ctx.bot.wait_for_modal(category_selection)

    # Extract responses
    category = modal_ctx.responses["category"].title()

    # Check to make sure category exists
    if category.lower() not in [cat.lower() for cat in categories]:
        await modal_ctx.send(f"{category} is an invalid category. Please try again.", ephemeral=True)
        return

    # Send the category to the SQL database
    successful = database.add_nomination(ctx.author.id, ctx.guild.id, ctx.channel.id, category, msg.id, msg.content)
    # await modal_ctx.send(str(database.get_nomination()))  # Debugging

    if successful:
        await modal_ctx.send(f"Nomination for {category} added successfully.", reply_to=msg.id)
    else:
        await modal_ctx.send("The database had an error. Please let me know about this.", ephemeral=True)


# === INITIATIVE COMMANDS ===

@slash_command(
    name="initiative",
    description="Commands for the initiative tracker.",
    sub_cmd_name="clear",
    sub_cmd_description="Clear the initiative list"
)
async def initiative_clear(ctx: SlashContext):
    globals().get("roll_list").clear()
    await ctx.send("Roll list cleared.")


@slash_command(
    name="initiative",
    description="Commands for the initiative tracker.",
    sub_cmd_name="roll",
    sub_cmd_description="Submit a roll for the current encounter. If you don't set a name, it will use your name."
)
@slash_option(
    name="roll_result",
    description="The number you rolled.",
    required=True,
    opt_type=OptionType.INTEGER
)
@slash_option(
    name="name",
    description="The name of the character.",
    required=False,
    opt_type=OptionType.STRING
)
async def initiative_roll(ctx: SlashContext, roll_result: int, name: str = None):
    # Add roll to the roll list
    if name is None:
        set_roll(ctx.author.id, roll_result)
        await ctx.send(f"Roll of {roll_result} added.")
    else:  # If a name was specified, use that instead of the user's name
        set_roll(name, roll_result)
        await ctx.send(f"Roll of {roll_result} added for {name}.")


@slash_command(
    name="initiative",
    description="Commands for the initiative tracker.",
    sub_cmd_name="get_order",
    sub_cmd_description="Displays the roll order for the current encounter."
)
async def initiative_get_order(ctx: SlashContext):
    rolls = get_roll_list()
    if len(rolls) == 0:
        await ctx.send("No rolls have been submitted yet.")
    else:
        msg = "Initiative order:\n"
        for i, (key, value) in enumerate(rolls):
            msg += f"{i + 1}. {key} ({value})\n"
        await ctx.send(msg)


roll_list = {}  # List of rolls for the current encounter


def get_roll(userID: int):
    return roll_list.get(userID)


def get_roll_list():
    """
    :return: The full roll list, sorted. For players, their names will be converted into their native nicknames. For
    NPC's, their names will be returned as is.
    """
    # For each loop - for each key in the roll list, if it's a discord ID (18-digit int), convert it to a nickname.
    # If it's a string, leave it as is.
    sorted_rolls = sorted(roll_list.items(), key=lambda x: x[1], reverse=True)
    for i, (key, value) in enumerate(sorted_rolls):
        if isinstance(key, int):
            sorted_rolls[i] = (bot.get_user(key).display_name, value)
    return sorted_rolls


def set_roll(characterID: int | str, die_result: int) -> None:
    """
    Set the roll for the given user.
    :param characterID: 18-digit integer for the user's discord ID. If the roll is for an NPC, it will be a string.
    :param die_result: Number that was rolled
    """
    roll_list.update({characterID: die_result})


bot.start(os.getenv("DISCORD_TOKEN"))
