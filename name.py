import discord
from discord import app_commands
from discord.ext import commands
from firebase_admin import firestore

from whispfirebase import *


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

    @commands.Cog.listener()
    async def on_ready(self):
        print("Name cog up")

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
            await enforce_name(after)
            return

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        await enforce_name(member)
