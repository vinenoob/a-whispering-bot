import uuid
from datetime import datetime
import discord
from discord.ext import commands, tasks
from discord.ext.commands.core import command
from discord_slash import cog_ext, SlashContext
from discord_slash.model import SlashCommandOptionType
from discord_slash.utils.manage_commands import create_option
from discord.utils import get
import pytz
from dateutil import parser
from whispfirebase import *
from wisp_tz import tzinfos

class Schedule(commands.Cog):
    LFG_BASE = "LFG"
    slash_guilds = [366792929865498634]
    def __init__(self, client: commands.AutoShardedBot):
        self.client = client
        self.callback_done = threading.Event()

    @commands.Cog.listener()
    async def on_ready(self):
        print("Schedule cog up")
        self.event_watcher.start()

    @tasks.loop(seconds=30)
    async def event_watcher(self):
        print("Checking events")
        now = datetime.now(pytz.UTC)
        #I can't make a compounded query work even with a composite index, so we just check for the notification_sent in the for loop
        event_docs = events_ref.where("timestamp", ">=", int(now.timestamp())).where("timestamp", "<=", int(now.timestamp()) + (60*30)).stream()#.where("notification_sent", "!=", True).stream()
        for event_doc in event_docs:
            #the below is temporary while my index builds
            event = event_doc.to_dict()
            if event["notification_sent"]:
                continue
            guild_doc = guilds_ref.document(str(event['guild'])).get()
            guild_info = guild_doc.to_dict()
            channel: discord.TextChannel = self.client.get_channel(guild_info['lfg_channel'])
            await channel.send(f"event {event} is now")
            event['notification_sent'] = True
            event_doc.reference.update(event)
            print(f'{event_doc.id} => {event_doc.to_dict()}')
        self.callback_done.set()


    lfg_set_channel_options = [
        create_option(
            name="channel",
            option_type=SlashCommandOptionType.CHANNEL,
            description="Which channel to send LFG messages in",
            required=True
        )
    ]
    @cog_ext.cog_subcommand(base=LFG_BASE, name="set_channel", description="set the channel for lfg", options=lfg_set_channel_options, guild_ids=slash_guilds)
    async def set_channel(self, ctx: SlashContext, channel: discord.TextChannel):
        if (type(channel) != discord.TextChannel):
            await ctx.send(f"{channel} is not a text channel")
            return
        guild_doc_ref = guilds_ref.document(str(ctx.guild_id))
        guild_doc = guild_doc_ref.get()
        if guild_doc.exists:
            guild_doc_ref.update({'lfg_channel': channel.id})
        else:
            guild_doc_ref.set({'lfg_channel': channel.id})
        await ctx.send(f"Set {channel} as lfg channel")


    lfg_options = [
        create_option(
            name="activity",
            description='''What event is being planned, ie "Master VoG" or "Gambit grinding"''',
            option_type=SlashCommandOptionType.STRING,
            # choices = ['Now'],
            required=True,
        ),
        create_option(
            name="time",
            description='''Date and time for lfg, ie 7:30pm CT 05/22''', #. Leave date empty to start today, and nothing for now
            option_type=SlashCommandOptionType.STRING,
            # choices = ['Now'],
            required=True,
        ),
        create_option(
            name="description",
            description='''Any additional information, such as "Doing challenges"''',
            option_type=SlashCommandOptionType.STRING,
            # choices = ['Now'],
            required=False,
        ),
    ]
    @cog_ext.cog_subcommand(base=LFG_BASE, name="create", description="Create an lfg", options=lfg_options, guild_ids=slash_guilds)
    async def add_lfg(self, ctx: SlashContext, activity, time='now', description=""):
        if len(time.split(':')[0]) == 1:
            time = f"0{time}"
        dt_obj = parser.parse(f"{time}", tzinfos=tzinfos)
        dt_obj = dt_obj.astimezone(pytz.UTC)


        # date_str = dt_obj.strftime("%m-%d-%y")
        event_id = uuid.uuid4().hex
        event = events_ref.document(event_id)
        event_doc = event.get()
        event_dict = {
            "timestamp": int(dt_obj.timestamp()),
            "activity": activity,
            "description": description,
            "notification_sent": False,
            "guild": ctx.guild_id
        }
        if event_doc.exists:
            event.update(event_dict)
        else:
            event.set(event_dict)
            # event.set({str(event_id): {"time": f"{time_input}"}})
        embed = discord.Embed(
                # title=activity,
                # description=description,
            )
        
        embed.add_field(name="Activity:", value=activity)
        embed.add_field(name="Start Time:", value=time)
        embed.set_footer(text=f"creator | {ctx.author.display_name}")
        msg = await ctx.send(embed=embed)
        await msg.delete(delay=5)
