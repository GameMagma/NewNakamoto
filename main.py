import os
from dotenv import load_dotenv

import interactions
from interactions import slash_command, SlashContext, OptionType, slash_option

load_dotenv()
bot = interactions.Client(intents=interactions.Intents.ALL)

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


@slash_command(
    name="ping",
    description="Ping the bot to see if it's alive."
)
async def ping(ctx: SlashContext):
    await ctx.send("Pong!")


# TODO: Make these a group command
@slash_command(
    name="start_encounter",
    description="Indicate the start of an encounter. This will scrap any old rolls and get ready for new rolls."
)
async def start_encounter(ctx: SlashContext):
    globals().get("roll_list").clear()
    await ctx.send("New encounter started")


@slash_command(
    name="roll",
    description="Submit a roll for the current encounter."
)
@slash_option(
    name="roll_result",
    description="The number you rolled.",
    required=True,
    opt_type=OptionType.INTEGER
)
async def roll(ctx: SlashContext, roll_result: int):
    # Add roll to the roll list
    set_roll(ctx.author.id, roll_result)
    await ctx.send(f"Roll of {roll_result} added.")


@slash_command(
    name="npc_roll",
    description="Submit an NPC's roll for the current encounter."
)
@slash_option(
    name="roll_result",
    description="The number you rolled.",
    required=True,
    opt_type=OptionType.INTEGER
)
@slash_option(
    name="npc_name",
    description="The name of the NPC.",
    required=True,
    opt_type=OptionType.STRING
)
async def npc_roll(ctx: SlashContext, roll_result: int, npc_name: str):
    # Add roll to the roll list
    set_roll(npc_name, roll_result)
    await ctx.send(f"Roll of {roll_result} added for {npc_name}.")


@slash_command(
    name="get_init_order",
    description="Displays the roll order for the current encounter."
)
async def get_init_order(ctx: SlashContext):
    rolls = get_roll_list()
    if len(rolls) == 0:
        await ctx.send("No rolls have been submitted yet.")
    else:
        msg = "Initiative order:\n"
        for i, (key, value) in enumerate(rolls):
            msg += f"{i + 1}. {key} ({value})\n"
        await ctx.send(msg)


bot.start(os.getenv("DISCORD_TOKEN"))