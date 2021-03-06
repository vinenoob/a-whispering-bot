from re import M
import discord
from discord import User
from discord.ext import commands, tasks
from discord.ext.commands.core import command
from discord_slash import cog_ext, SlashContext
from discord_slash.model import SlashCommandOptionType
from discord_slash.utils.manage_commands import create_option
from discord.utils import get

from whispfirebase import *

user_cache = {}

def get_D2_name_from_member(member: discord.Member) -> str:
    if member.id not in user_cache:
        user_cache[member.id] = {}
        userDoc = users_ref.document(str(member.id)).get()
        if userDoc.exists: #if they aren't in the database, then just use their discord name for now
            user_cache[member.id]["name"] = userDoc.to_dict()['d2name']
        else:
            user_cache[member.id]["name"] = member.name
    return user_cache[member.id]["name"]

def get_D2_name_with_prefix_from_member(member: discord.Member):
    if member.id in user_cache and "pronoun name" in user_cache[member.id]:
        return user_cache[member.id]["pronoun name"]
    guild_doc = guilds_ref.document(str(member.guild.id)).get()
    d2_username = get_D2_name_from_member(member)
    memberRolesSet = {str(role.id) for role in member.roles}
    rolesToWatchSet = set(guild_doc.to_dict()['pronouns_watch'])
    if rolesToWatchSet & memberRolesSet:
        stringRoles = rolesToWatchSet.intersection(memberRolesSet)
        roles = [member.guild.get_role(int(stringRole)) for stringRole in stringRoles]
        role = max(roles, key= lambda k: k.position)
        role_string = str(role).split('/')[0]
        user_cache[member.id]["pronoun name"] = f"({role_string}) {d2_username}"[:32]
    else:
        print(f"No roles found for {member}")
        user_cache[member.id]["pronoun name"] = d2_username
    return user_cache[member.id]["pronoun name"]
    

async def enforce_name(member: discord.Member):
    name: str
    if member.voice is None:
        name = get_D2_name_from_member(member)
    else:
        name = get_D2_name_with_prefix_from_member(member)
    if member.display_name != name:
        try:
            await member.edit(nick=name)
        except discord.errors.Forbidden:
            print(f"Can't edit {member}")

# async def enforce_name2(member: discord.Member):
#     # sourcery skip: merge-else-if-into-elif
#     name: str
#     if member.voice is None:
#         if member.id in user_cache:
#             name = user_cache[member.id]['name']
#         else:
#             name = get_D2_name_from_member(member)
#             user_cache[member.id] = {'name': name}
#     else:
#         if member.id in user_cache and 'pronoun name' in user_cache[member.id]:
#             name = user_cache[member.id]['pronoun name']
#         else:
#             if member.id not in user_cache:
#                 user_cache[member.id] = {}
#             name = get_D2_name_with_prefix_from_member(member)
#             user_cache[member.id]['pronoun name'] = name
#     if member.display_name != name:
#         try:
#             await member.edit(nick=name)
#         except discord.errors.Forbidden:
#             print(f"Can't edit {member}")

class Name(commands.Cog):
    PRONOUN_BASE = "Pronoun"
    # slash_guilds = [842812244965326869, 366792929865498634, 160907545018499072]
    slash_guilds = [366792929865498634]
    def __init__(self, client):
        self.client = client
        self.have_skipped_boot = False
        self.callback_done = threading.Event()
        self.ids_to_update = []

    
    def on_snapshot(self, doc_snapshot, changes, read_time):
        if self.have_skipped_boot:
            for change in changes:
                if int(change.document.id) in user_cache:
                    del user_cache[int(change.document.id)]
                member = discord.utils.get(self.client.get_all_members(), id=int(change.document.id))
                self.ids_to_update.append(int(member.id))
                # if change.type.name == 'ADDED':
                #     print(f'New member: {change.document.id}')
                #     # user = client.fetch_user(int(change.document.id))
                #     member = discord.utils.get(self.client.get_all_members(), id=int(change.document.id))
                #     self.new_people_ids.append(int(member.id))
                #     print(member)
                # elif change.type.name == 'MODIFIED':
                #     print(f'Modified member: {change.document.id}')
                # elif change.type.name == 'REMOVED':
                #     print(f'Removed member: {change.document.id}')
                #     # delete_done.set()
        else:
            self.have_skipped_boot = True
        self.callback_done.set()

    @tasks.loop(seconds=5)
    async def fbi_watchlist(self):
        for discord_id in self.ids_to_update:
            user: discord.User = get(self.client.get_all_members(), id=discord_id)
            mutual_guilds = user.mutual_guilds
            guild: discord.Guild
            for guild in mutual_guilds:
                member: discord.Member = guild.get_member(user.id)
                await enforce_name(member)
        self.ids_to_update = []

    @commands.Cog.listener()
    async def on_ready(self):
        print("Name cog up")
        doc_watch = users_ref.on_snapshot(self.on_snapshot)
        self.fbi_watchlist.start()
        member: discord.Member
        for member in self.client.get_all_members():
            await enforce_name(member)

    roleOptions = [
        create_option(
            name="role",
            description="A role to add to the watchlist",
            option_type=SlashCommandOptionType.ROLE,
            required=True,
        )
    ]

    @cog_ext.cog_subcommand(base=PRONOUN_BASE, name="add", description="Add a pronoun role to the watchlist", options=roleOptions, guild_ids=slash_guilds)
    async def add_role(self, ctx: SlashContext, role):
        if ctx.author.guild_permissions.administrator:
            guild_id = str(ctx.guild_id)
            role_id = str(role.id)
            guild_doc_ref = guilds_ref.document(guild_id)
            guild_doc = guild_doc_ref.get()
            if guild_doc.exists:
                guild_doc_ref.update({'pronouns_watch': firestore.firestore.ArrayUnion([role_id])})
            else:
                guild_doc_ref.set({'pronouns_watch': [role_id]})
            await ctx.send(f"Added {role} from pronoun watchlist")
            return
        else:
            await ctx.send("You don't have permissions")
    
    @cog_ext.cog_subcommand(base=PRONOUN_BASE, name="remove", description="Remove a pronoun role to the watchlist", options=roleOptions, guild_ids=slash_guilds)
    async def remove_role(self, ctx: SlashContext, role):
        if ctx.author.guild_permissions.administrator:
            role_id = str(role.id)
            guild_id = str(ctx.guild_id)
            guild_doc_ref = guilds_ref.document(guild_id)
            guild_doc = guild_doc_ref.get()
            if guild_doc.exists:
                guild_doc_ref.update({'pronouns_watch': firestore.firestore.ArrayRemove([role_id])})
                await ctx.send(f"Removed {role} from pronoun watchlist")
            else:
                await ctx.send("You don't have any roles set up!")
                return
        else:
            await ctx.send("You don't have permissions")

    @cog_ext.cog_subcommand(base=PRONOUN_BASE, name="list", description="List watched pronouns", guild_ids=slash_guilds)
    async def send_pronouns(self, ctx: SlashContext):
        '''does this appear?'''
        guild_id = str(ctx.guild_id)
        guild_doc_ref = guilds_ref.document(guild_id)
        guild_doc = guild_doc_ref.get()
        role_ids = guild_doc.to_dict()['pronouns_watch']
        pronouns = [ctx.guild.get_role(int(str_pronoun_id)) for str_pronoun_id in role_ids]
        out = "Watched pronouns are: "
        pronoun: discord.Role
        for pronoun in pronouns:
            out += f"{pronoun.mention} "
        await ctx.send(out)
    
    @cog_ext.cog_subcommand(base=PRONOUN_BASE, name="help", description="Get some help with the pronoun commands", options=roleOptions, guild_ids=slash_guilds)
    async def help(self, ctx: SlashContext):
        await ctx.send('''
    The purpose of this bot is to watch for a user entering a voice channel and adding their pronoun to the start of their name. Use the "pronoun_add" slash command to add a role to the watch list
    ''')

    #TODO: consider just moving this to the on_member_update function
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is None or after.channel is None:
            await enforce_name(member)
        print(f"{str(member)} update on voice state:\n\tbefore: {before.channel.name if before.channel != None else 'None'}\n\tafter: {after.channel.name if after.channel != None else 'None'}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        #NAME CHANGE START
        if before.display_name != after.display_name:
            await enforce_name(after)
            return
        #NAME CHANGE END

        #ROLES CHANGE START
        #This is supposed to catch the scenario someone adds to their roles while in voice chat
        if len(before.roles) != len(after.roles):
            if after.id in user_cache:
                del user_cache[after.id]
            await enforce_name(after)
            return
        #ROLES CHANGE END

    @commands.Cog.listener()
    async def on_member_join(self, member:discord.Member):
        await enforce_name(member)