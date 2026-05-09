import threading
import uuid
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks
import pytz
from dateutil import parser

from whispfirebase import *
from wisp_tz import tzinfos


class Schedule(commands.Cog):
    lfg = app_commands.Group(name="lfg", description="LFG event management")

    def __init__(self, client: commands.AutoShardedBot):
        self.client = client
        self.callback_done = threading.Event()

    async def cog_load(self):
        self.event_watcher.start()

    async def cog_unload(self):
        self.event_watcher.cancel()

    @commands.Cog.listener()
    async def on_ready(self):
        print("Schedule cog up")

    @tasks.loop(seconds=30)
    async def event_watcher(self):
        print("Checking events")
        now = datetime.now(pytz.UTC)
        #I can't make a compounded query work even with a composite index, so we just check for the notification_sent in the for loop
        event_docs = events_ref.where("timestamp", ">=", int(now.timestamp())).where("timestamp", "<=", int(now.timestamp()) + (60*30)).stream()
        for event_doc in event_docs:
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

    @lfg.command(name="set_channel", description="Set the channel for lfg")
    @app_commands.describe(channel="Which channel to send LFG messages in")
    async def set_channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_doc_ref = guilds_ref.document(str(interaction.guild_id))
        guild_doc = guild_doc_ref.get()
        if guild_doc.exists:
            guild_doc_ref.update({'lfg_channel': channel.id})
        else:
            guild_doc_ref.set({'lfg_channel': channel.id})
        await interaction.response.send_message(f"Set {channel} as lfg channel")

    @lfg.command(name="create", description="Create an lfg")
    @app_commands.describe(
        activity='What event is being planned, ie "Master VoG" or "Gambit grinding"',
        time="Date and time for lfg, ie 7:30pm CT 05/22",
        description='Any additional information, such as "Doing challenges"',
    )
    async def add_lfg(
        self,
        interaction: discord.Interaction,
        activity: str,
        time: str = "now",
        description: str = "",
    ):
        if len(time.split(':')[0]) == 1:
            time = f"0{time}"
        dt_obj = parser.parse(f"{time}", tzinfos=tzinfos)
        dt_obj = dt_obj.astimezone(pytz.UTC)

        event_id = uuid.uuid4().hex
        event = events_ref.document(event_id)
        event_doc = event.get()
        event_dict = {
            "timestamp": int(dt_obj.timestamp()),
            "activity": activity,
            "description": description,
            "notification_sent": False,
            "guild": interaction.guild_id,
        }
        if event_doc.exists:
            event.update(event_dict)
        else:
            event.set(event_dict)

        embed = discord.Embed()
        embed.add_field(name="Activity:", value=activity)
        embed.add_field(name="Start Time:", value=time)
        embed.set_footer(text=f"creator | {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)
        msg = await interaction.original_response()
        await msg.delete(delay=5)
