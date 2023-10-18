import os
from dotenv import load_dotenv

import interactions
from interactions import slash_command, SlashContext, OptionType, slash_option, listen

bot = interactions.Client(intents=interactions.Intents.ALL)


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
                   "Version 2.0.2")


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


load_dotenv()
bot.start(os.getenv("DISCORD_TOKEN"))
