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
from whispfirebase import *

timezone_abbrv_to_gmt = {
    
}

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
        tz = pytz.timezone('Europe/London')
        now = datetime.now(tz)
        date = f"{now.month if len(str(now.month)) > 1 else f'0{now.month}'}-{now.day if len(str(now.day)) > 1 else f'0{now.day}'}"
        events_doc_ref = events_ref.document(date)
        events_doc = events_doc_ref.get()
        events = events_doc.to_dict()
        for key in events:
            event = events[key]
            #TODO: replace True below with time check
            if (event['time'] == "now" or True) and not event['notification-sent']:
                guild_doc = guilds_ref.document(str(event['guild'])).get()
                guild_info = guild_doc.to_dict()
                channel: discord.TextChannel = self.client.get_channel(guild_info['lfg_channel'])
                await channel.send(f"event {events} is now")
        self.callback_done.set()


        #TODO: Look at the events collection for todays date. If there is something,
        #  check the time to see if it needs to be warned about and then mark it as
        #  checked.
        #TODO: ALTERNATE: b6uild a similar caching system as the user cache in name
        #TODO: on update, check to see if it was today. check if the day has changed
        print("Watching for events...")

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
            description='''Date and time for lfg, ie 7:30pm CT 05/22. Leave date empty to start today, and nothing for now''',
            option_type=SlashCommandOptionType.STRING,
            # choices = ['Now'],
            required=False,
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
        tz = pytz.timezone('Etc/GMT-0')
        tz2 = pytz.timezone('Etc/GMT-2')
        now = datetime.now(tz)
        now2 = datetime.now(tz2)

        # try:
        #     time_input_split = time.split(' ')
        #     activity_time = time_input_split[0]
        #     if activity_time != 'now':
        #         time_zone = time_input_split[1]
        #         try:
        #             date = time_input_split[2]
        #             date = date.replace('/', '-')
        #         except Exception:
        #             date = f"{now.day}-{now.month}"
        #     else:
        #         time_zone = "N/A"
        #         date = f"{now.day}-{now.month}"
        # except Exception:
        #     msg = await ctx.reply('Bad time input, try again')
        #     await msg.delete(delay=5)
        #     return
        # https://docs.python.org/3/library/datetime.html#strftime-and-strptime-behavior
        # date = f"{now.month if len(str(now.month)) > 1 else f'0{now.month}'}-{now.day if len(str(now.day)) > 1 else f'0{now.day}'}"
        dt_obj = datetime.strptime(f"{time} {time_zone}", "%m-%d  %Z")
        dt_obj = dt_obj.replace(year=now.year)
        x = dt_obj.astimezone(tz)
        if time is None:
            time = f"{now.hour}:{now.minute}"
        event = events_ref.document(date)
        event_doc = event.get()
        event_id = uuid.uuid4().hex
        event_dict = {
            str(event_id):{
                "time": activity_time,
                "date": dt_obj.timestamp(),
                "time_zone": time_zone,
                "activity": activity,
                "description": description,
                "notification-sent": False,
                "guild": ctx.guild_id
            }
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
        # await msg.delete(delay=5)
