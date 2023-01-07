import discord
import pytz
from discord.ext import commands
from discord_slash import cog_ext, SlashContext
from datetime import date, datetime, tzinfo
import re
from dateutil import parser
from dateutil.tz import gettz
from wisp_tz import tzinfos

class TimeConvert(commands.Cog):
    def __init__(self, client: commands.AutoShardedBot):
        self.client = client
        
    @commands.Cog.listener()
    async def on_ready(self):
        print("Time convert booted up!")

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if reaction.emoji != '⏲️':
            return
        message_content: str = reaction.message.content
        match = re.search("([01]?[0-9]|2[0-3]):[0-5][0-9](:[0-5][0-9])?(am|pm) ?[A-z][A-z]?[Tt]", message_content)
        if not match:
            return
        time_embed = discord.Embed()
        string_match = match[0]
        if len(string_match.split(':')[0]) == 1:
            string_match = f"0{string_match}"
        string_match_split = string_match.split(' ')
        # as_timezone: str
        # for timezone in timezone_to_utc:
        #     if string_match_split[-1] == timezone:
        #         as_timezone = timezone_to_utc[timezone]
        #         string_match_split.pop()
        #         string_match = ' '.join(string_match_split)
        dt_obj = parser.parse(f"{string_match}".upper(), tzinfos=tzinfos)
        dt_obj = dt_obj.astimezone(pytz.UTC)
        # dt_obj = datetime.strptime(string_match, "%H:%M%p %Z")
        time_embed.add_field(name="Time", value=f"<t:{int(datetime.timestamp(dt_obj))}:t>")
        # time_embed.add_field(name="match", value=string_match)

        await reaction.message.reply(embed=time_embed)