import threading

import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.utils import get
from firebase_admin import firestore

from whispfirebase import *

user_cache = {}


def get_D2_name_from_member(member: discord.Member) -> str:
    # sourcery skip: merge-else-if-into-elif
    if member.id not in user_cache:
        user_cache[member.id] = {}
        user = get_user_doc(member.id)
        if user.exists:
            user_cache[member.id]["name"] = user.to_dict()['d2name']
        else:
            if member.nick is None:
                user_cache[member.id]["name"] = member.name
            else:
                user_cache[member.id]["name"] = member.nick
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
        roles.sort(key=lambda role: role.position, reverse=True)
        role_string = "".join(str(role).split('/')[0] + "/" for role in roles)
        role_string = role_string[:-1]
        user_cache[member.id]["pronoun name"] = f"({role_string}) {d2_username}"[:32]
    else:
        print(f"No roles found for {member}")
        user_cache[member.id]["pronoun name"] = d2_username
    return user_cache[member.id]["pronoun name"]


def _strip_pronoun_prefix(nick: str) -> str:
    if nick.startswith("(") and ")" in nick:
        return nick[nick.find(")") + 1:].lstrip()
    return nick


def _build_pronoun_prefix(member: discord.Member) -> str:
    guild_doc = guilds_ref.document(str(member.guild.id)).get()
    if not guild_doc.exists:
        return ""
    member_role_ids = {str(role.id) for role in member.roles}
    watched = set(guild_doc.to_dict().get('pronouns_watch', []))
    matched_ids = watched & member_role_ids
    if not matched_ids:
        return ""
    roles = [member.guild.get_role(int(rid)) for rid in matched_ids]
    roles = [r for r in roles if r is not None]
    roles.sort(key=lambda role: role.position, reverse=True)
    return "/".join(str(role).split('/')[0] for role in roles)


async def enforce_name(member: discord.Member):
    fallback = member.global_name or member.name
    base = _strip_pronoun_prefix(member.nick) if member.nick else fallback

    if member.voice is None:
        if member.nick is None:
            return
        target = None if base == fallback else base
    else:
        prefix = _build_pronoun_prefix(member)
        if prefix:
            target = f"({prefix}) {base}"[:32]
        elif member.nick is None:
            return
        else:
            target = None if base == fallback else base

    if member.nick != target:
        try:
            await member.edit(nick=target)
        except discord.errors.Forbidden:
            print(f"Can't edit {member}")


class Name(commands.Cog):
    naming = app_commands.Group(name="naming", description="Pronoun and name management")

    def __init__(self, client):
        self.client: commands.AutoShardedBot = client
        self.have_skipped_boot = False
        self.callback_done = threading.Event()
        self.ids_to_update = []
        self.doc_watch: firestore.firestore.Watch = None

    async def cog_load(self):
        self.doc_watch = users_ref.on_snapshot(self.on_snapshot)
        self.fbi_watchlist.start()

    async def cog_unload(self):
        self.fbi_watchlist.cancel()
        if self.doc_watch is not None:
            self.doc_watch.unsubscribe()

    def on_snapshot(self, doc_snapshot, changes, read_time):
        if self.have_skipped_boot:
            for change in changes:
                if int(change.document.id) in user_cache:
                    del user_cache[int(change.document.id)]
                member = discord.utils.get(self.client.get_all_members(), id=int(change.document.id))
                self.ids_to_update.append(int(member.id))
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
        if not self.doc_watch.is_active:
            self.have_skipped_boot = False
            self.doc_watch = users_ref.on_snapshot(self.on_snapshot)

    @commands.Cog.listener()
    async def on_ready(self):
        print("Name cog up")

    @naming.command(name="force_register", description="Backfill registered names from existing nicknames")
    async def force_register(self, interaction: discord.Interaction):
        if interaction.user.id != 160907412205862913:
            await interaction.response.send_message("You don't have permissions", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        members = self.client.get_all_members()
        member: discord.Member
        for member in members:
            if member.bot or member.guild.id != 842812244965326869:
                continue
            member_id = str(member.id)
            nick: str = member.nick
            if nick is None:
                continue
            find = nick.find(')')
            if find != -1:
                nick = nick[find + 2:]
            print(f"name would be {nick} id is {member_id}")
            users_doc_ref = users_ref.document(member_id)
            user_doc = users_doc_ref.get()
            if not user_doc.exists:
                user_json = {"d2name": nick}
                users_doc_ref.set(user_json)
        await interaction.followup.send("Done", ephemeral=True)

    @naming.command(name="pronoun_add", description="Add a pronoun role to the watchlist")
    @app_commands.describe(role="A role to add to the watchlist")
    async def pronoun_add(self, interaction: discord.Interaction, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You don't have permissions", ephemeral=True)
            return
        guild_id = str(interaction.guild_id)
        role_id = str(role.id)
        guild_doc_ref = guilds_ref.document(guild_id)
        guild_doc = guild_doc_ref.get()
        if guild_doc.exists:
            guild_doc_ref.update({'pronouns_watch': firestore.firestore.ArrayUnion([role_id])})
        else:
            guild_doc_ref.set({'pronouns_watch': [role_id]})
        await interaction.response.send_message(f"Added {role} from pronoun watchlist")

    @naming.command(name="pronoun_remove", description="Remove a pronoun role from the watchlist")
    @app_commands.describe(role="A role to remove from the watchlist")
    async def pronoun_remove(self, interaction: discord.Interaction, role: discord.Role):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You don't have permissions", ephemeral=True)
            return
        role_id = str(role.id)
        guild_id = str(interaction.guild_id)
        guild_doc_ref = guilds_ref.document(guild_id)
        guild_doc = guild_doc_ref.get()
        if guild_doc.exists:
            guild_doc_ref.update({'pronouns_watch': firestore.firestore.ArrayRemove([role_id])})
            await interaction.response.send_message(f"Removed {role} from pronoun watchlist")
        else:
            await interaction.response.send_message("You don't have any roles set up!")

    @naming.command(name="pronoun_list", description="List watched pronouns")
    async def pronoun_list(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        guild_doc_ref = guilds_ref.document(guild_id)
        guild_doc = guild_doc_ref.get()
        role_ids = guild_doc.to_dict()['pronouns_watch']
        pronouns = [interaction.guild.get_role(int(str_pronoun_id)) for str_pronoun_id in role_ids]
        out = "Watched pronouns are: "
        pronoun: discord.Role
        for pronoun in pronouns:
            out += f"{pronoun.mention} "
        await interaction.response.send_message(out)

    @naming.command(name="name_set", description="Set a user's registered name")
    @app_commands.describe(user="The user to edit", name="The new name for the user")
    async def name_set(self, interaction: discord.Interaction, user: discord.Member, name: str):
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You no have permission for this", ephemeral=True)
            return
        member_id = str(user.id)
        users_doc_ref = users_ref.document(member_id)
        user_doc = users_doc_ref.get()
        if not user_doc.exists:
            user_json = {"d2name": name}
            users_doc_ref.set(user_json)
        else:
            user_json = user_doc.to_dict()
            user_json["d2name"] = name
            users_doc_ref.update(user_json)
        await interaction.response.send_message(f"Updating {user} nick to {name}")

    @naming.command(name="help", description="Get some help with the pronoun commands")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            'The purpose of this bot is to watch for a user entering a voice channel and adding their pronoun to the start of their name. Use the "pronoun_add" slash command to add a role to the watch list'
        )

    #TODO: consider just moving this to the on_member_update function
    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if before.channel is None or after.channel is None:
            await enforce_name(member)
        print(f"{str(member)} update on voice state:\n\tbefore: {before.channel.name if before.channel != None else 'None'}\n\tafter: {after.channel.name if after.channel != None else 'None'}")

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.display_name != after.display_name:
            await enforce_name(after)
            return

        if len(before.roles) != len(after.roles):
            if after.id in user_cache:
                del user_cache[after.id]
            await enforce_name(after)
            return

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await enforce_name(member)
