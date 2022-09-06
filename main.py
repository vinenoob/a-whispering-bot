import json
from pydoc import cli
from re import A
import threading
from unicodedata import name
import discord
from discord.utils import get
from discord.ext import commands, tasks
from discord_slash import SlashCommand, SlashContext
from discord_slash.model import SlashCommandOptionType
from discord_slash.utils.manage_commands import create_option
from os.path import exists

# from whispfirebase import *
from name import Name
from schedule import Schedule
from time_convert import TimeConvert

intents = discord.Intents.default()
intents.members = True
intents.reactions = True
client = commands.AutoShardedBot(commands.when_mentioned_or('?'), intents = intents)
slash = SlashCommand(client, override_type=True, sync_commands=True, debug_guild=366792929865498634)
client.add_cog(Name(client))
# client.add_cog(Schedule(client))
client.add_cog(TimeConvert(client))
# slash_guilds = [842812244965326869, 366792929865498634, 160907545018499072]
slash_guilds = [842812244965326869]

@client.event
async def on_ready():
    print('bot booted up!')

@slash.slash(name="register", description="Register for the Whipering Mandrake bot!", guild_ids=slash_guilds)
async def register(ctx: SlashContext):
    await ctx.send("Go to https://d2firebase.web.app/ to register! Yes it does look sketchy but I promise it is safe")

def main():
    key = ""
    with open("key2.txt", "r") as keyfile:
        key = keyfile.read()

    client.run(key)

if __name__ == '__main__':
    main()