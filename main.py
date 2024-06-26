import os
from dotenv import load_dotenv

import interactions
from interactions import slash_command, SlashContext, OptionType, slash_option, listen, ModalContext, User, \
    SlashCommandChoice
from interactions import message_context_menu, ContextMenuContext, Message, Modal, ShortText
from interactions.api.events import MessageCreate

from SQLManager import SQLManager

load_dotenv()

bot = interactions.Client(intents=interactions.Intents.ALL)

# === GLOBALS ===
# One day I'll integrate this into a place that uses less memory. Today is not that day, and neither is tomorrow
database = SQLManager()  # Database connection
# categories = ["Worst Idea", "Best Idea", "Biggest Lie", "Worst Bit", "Best Bit", "Least Funny Recurring Joke",
#               "Craziest Working Gaslight", "Funniest Recurring Joke", "Dumbest Discussion"]
_VERSION = "3.2.9"

categories = database.get_categories()
categories = [c[0] for c in categories]
print("Found categories: ", categories)

# Options for the nominations command
choices_nominations = []
for categoryName in categories:
    choices_nominations.append(SlashCommandChoice(name=categoryName, value=categoryName))


# === EVENTS ===


@listen()
async def on_startup():
    print(f"Bot Version {_VERSION}, Interactions Library version {interactions.__version__}")
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
    await ctx.send(f"Created by Connor Midgley.\n"
                   "Source code available at https://github.com/GameMagma/NewNakamoto \n"
                   f"Version {_VERSION}\n\n"
                   
                   "New features for 3.2.x:\n"
                   "- You can now nominate messages for The Orwell Awards\n"
                   "- You can now view the nominations for The Orwell Awards\n"
                   "- Buh\n"
                   "- Statuses Added\n"
                   "- Added complaint management system\n",
                   ephemeral=True)


@slash_command(
    name="dbtest",
    description="Tests the database connection.",
    scopes=[os.getenv("TEST_GUILD_ID")]
)
async def dbtest(ctx: SlashContext):
    await ctx.send(database.get_wallet(ctx.author.id)[1])


@slash_command(
    name="nominations",
    description="View the current nominations"
)
@slash_option(
    name="nominator",
    description="The user that nominated the message",
    required=False,
    opt_type=OptionType.USER,
)
@slash_option(
    name="category",
    description="The category to view nominations for",
    required=False,
    opt_type=OptionType.STRING,
    choices=choices_nominations
)
async def get_nominations(ctx: SlashContext, nominator: User = None, category: str = None):
    result = database.get_nomination(nominator, category)

    if result is None:
        await ctx.send("No nominations found.")
    else:
        # Send result and make it look nice.
        # Format: [(NominationID, GuildID, ChannelID, MessageID, AuthorID, Category, message), ...]
        msg = "Nominations:\n"

        print("Formatting")

        for nomination in result:
            # "get_user"/channel/guild only grabs from the cache. "fetch" actually polls the API for it (if
            # it's not in the cache)
            author: str
            guild: str
            channel: str

            try:
                authorRoutine = await bot.fetch_user(nomination[4])
                author = f"<@{authorRoutine.id}>"  # Convert to mention
            except AttributeError as user_not_found:
                print(f"Error: An user wasn't found when trying to display nominations. "
                      f"Full error: {user_not_found}")
                author = nomination[4]

            try:
                guildRoutine = await bot.fetch_guild(nomination[1])
                guild = guildRoutine.name
            except AttributeError as guild_not_found:
                print(f"Error: A guild wasn't found when trying to display nominations. "
                      f"Full error: {guild_not_found}")
                guild = nomination[1]

            try:
                channelRoutine = await bot.fetch_channel(nomination[2])
                channel = channelRoutine.name
            except AttributeError as channel_not_found:
                print(f"Error: A channel wasn't found when trying to display nominations. "
                      f"Full error: {channel_not_found}")
                channel = nomination[2]

            msg += f"Message (up to 255 characters): {nomination[6]}\n" \
                   f"Category: {nomination[5]}\n" \
                   f"Author: {author}\n" \
                   f"Guild: {guild}\n" \
                   f"Channel: {channel}\n\n"

            await ctx.send(msg)


@listen(MessageCreate)
async def on_message_create(event: MessageCreate):
    if event.message.channel.id == int(os.getenv("HR_CHANNEL_ID")):
        await event.message.author.send("Thank you for the complaint, it has been filed and will be addressed in a "
                                        "timely manner. Your input means very much to us. You can see the list of "
                                        "complaints [here](https://docs.google.com/document/d"
                                        "/1wjBOPLrslvETZ3WA2r3dwANrnwkd8oWlAthVFlhQ6cg/edit?usp=sharing)"
                                        " (updates automatically).")
        print("Complaint received")
        await event.message.delete()



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


# A global all the way down here? Isn't that bad practice? Yes. Yes it is.
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


# === Admin ===
@slash_command(
    name="admin",
    description="Commands for the bot administrator",
    scopes=[os.getenv("TEST_GUILD_ID")],
    sub_cmd_name="close_connection",
    sub_cmd_description="Closes connection to the database"
)
async def admin_close_connection(ctx: SlashContext):
    database.close()
    await ctx.send("Connection to the database closed.")


# Command to restart the connection to the database. Check if it's closed already. If so, close it. Finally,
# open a new connection.
@slash_command(
    name="admin",
    description="Commands for the bot administrator",
    scopes=[os.getenv("TEST_GUILD_ID")],
    sub_cmd_name="restart_connection",
    sub_cmd_description="Restarts the connection to the database"
)
async def admin_restart_connection(ctx: SlashContext):
    if database.is_closed():
        database.close()

    globals()['database'] = SQLManager()  # Reset the database connection

    await ctx.send("Connection to the database restarted.")


@slash_command(
    name="admin",
    description="Commands for the bot administrator",
    sub_cmd_name="say",
    sub_cmd_description="Make the bot say something."
)
@slash_option(
    name="message",
    description="The message for the bot to say.",
    required=True,
    opt_type=OptionType.STRING
)
async def admin_say(ctx: SlashContext, message: str):
    if ctx.author_id == 456269883873951744:
        await ctx.send("Repeating:", ephemeral=True)
        await ctx.channel.send(message)
    else:
        await ctx.send("You do not have permission to use this command.", ephemeral=True)


@slash_command(
    name="status",
    description="Commands for status management",
    sub_cmd_name="set",
    sub_cmd_description="Set the bot status."
)
@slash_option(
    name="status",
    description="The status to set.",
    required=True,
    opt_type=OptionType.STRING,
    choices=[
        SlashCommandChoice(name="online", value="online"),
        SlashCommandChoice(name="idle", value="idle"),
        SlashCommandChoice(name="dnd", value="dnd"),
        SlashCommandChoice(name="invisible", value="invisible")
    ],
)
@slash_option(
    name="activity_type",
    description="The activity to set. Only used if status is online",
    required=False,
    opt_type=OptionType.STRING,
    choices=[
        SlashCommandChoice(name="playing", value="playing"),
        SlashCommandChoice(name="streaming", value="streaming"),
        SlashCommandChoice(name="listening", value="listening"),
        SlashCommandChoice(name="watching", value="watching"),
        SlashCommandChoice(name="competing", value="competing")
    ]
)
@slash_option(
    name="activity",
    description="The activity to set. If you set an activity type, you need to set this too.",
    required=False,
    opt_type=OptionType.STRING
)
async def status_set(ctx: SlashContext, status: str, activity_type: str = None, activity: str = None):
    if ctx.author_id == 456269883873951744:
        if status == "online":
            if activity_type is not None and activity is not None:
                # Convert activity type to the correct type
                match activity_type:
                    case "playing":
                        activity_type = interactions.ActivityType.PLAYING
                    case "streaming":
                        activity_type = interactions.ActivityType.STREAMING
                    case "listening":
                        activity_type = interactions.ActivityType.LISTENING
                    case "watching":
                        activity_type = interactions.ActivityType.WATCHING
                    case "competing":
                        activity_type = interactions.ActivityType.COMPETING
                    case _:
                        activity_type = interactions.ActivityType.PLAYING

                # Set the status
                await bot.change_presence(
                    status=status, activity=interactions.Activity(name=activity, type=activity_type))
            else:
                await bot.change_presence(status=status)
        else:
            await bot.change_presence(status=status)
        await ctx.send("Status set.")
    else:
        await ctx.send("You do not have permission to use this command.", ephemeral=True)


@slash_command(
    name="admin",
    description="Commands for the bot administrator",
    sub_cmd_name="shutdown",
    sub_cmd_description="Shuts down the bot."
)
async def shutdown(ctx: SlashContext):
    if ctx.author_id == 456269883873951744:
        print("Asked to shut down. Goodbye.")
        await ctx.send("Shutting down.")
        if not database.is_closed():
            database.close()
        await bot.stop()
    else:
        await ctx.send("You do not have permission to use this command.", ephemeral=True)


bot.start(os.getenv("DISCORD_TOKEN"))
