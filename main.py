import json
import discord
from discord.ext import commands
from discord_slash import SlashCommand, SlashContext
from discord_slash.model import SlashCommandOptionType
from discord_slash.utils.manage_commands import create_option
from os.path import exists

database_file_name = "roleData.json"
roles_watch = {}
def save_roles_watch_to_database():
    """save the current value of roles_watch to file"""
    with open('roleData.json', "w+") as role_data_file:
        json.dump(roles_watch, role_data_file)

client = commands.Bot(commands.when_mentioned_or('?'))
slash = SlashCommand(client, override_type=True, sync_commands=True)

slash_guilds = [366792929865498634, 160907545018499072]

@client.event
async def on_ready():
    print('bot booted up!')

roleOptions = [
    create_option(
        name="role",
        description="A role to add to the watchlist",
        option_type=SlashCommandOptionType.ROLE,
        required=True,
    )
]

#WHOAH
@slash.slash(name="Pronoun_add", options=roleOptions, description="Add a pronoun role to the watchlist", guild_ids=slash_guilds)
async def add_role(ctx: SlashContext, role):
    if ctx.author.guild_permissions.administrator:
        guildId = str(ctx.guild_id)
        roleId = str(role.id)
        if guildId not in roles_watch['guilds']:
            roles_watch['guilds'][guildId] = []
        if roleId in roles_watch['guilds'][guildId]:
            await ctx.send(f"{role.mention} already in pronoun watch list")
            return
        else:
            roles_watch['guilds'][guildId].append(roleId)
            save_roles_watch_to_database()
        await ctx.send(f"Added {role.mention} to pronoun watch list")
    else:
        await ctx.send("You don't have permissions")

@slash.slash(name="pronoun_remove", options=roleOptions, description="Remove a pronoun role to the watchlist", guild_ids=slash_guilds)
async def remove_role(ctx: SlashContext, role):
    if ctx.author.guild_permissions.administrator:
        roleId = str(role.id)
        guildId = str(ctx.guild_id)
        if roleId in roles_watch['guilds'][guildId]:
            roles_watch['guilds'][guildId].remove(roleId)
            save_roles_watch_to_database()
            await ctx.send(f"Removed {role.mention} from pronoun watch list")
        else:
            await ctx.send(f"Role {role.mention} not in watchlist")
    else:
        await ctx.send("You don't have permissions")

@slash.slash(name="Pronouns", description="See what roles you have set as pronouns", guild_ids=slash_guilds)
async def send_pronouns(ctx: SlashContext):
    '''does this appear?'''
    guildId = str(ctx.guild_id)
    pronouns = [ctx.guild.get_role(int(str_pronoun_id)) for str_pronoun_id in roles_watch['guilds'][guildId]]
    out = "Watched pronouns are: "
    pronoun: discord.Role
    for pronoun in pronouns:
        out += f"{pronoun.mention} "
    await ctx.send(out)

@slash.slash(name="Pronouns_help", description="Get a description of the bot and how it works", guild_ids=slash_guilds)
async def help(ctx: SlashContext):
    await ctx.send('''
The purpose of this bot is to watch for a user entering a voice channel and adding their pronoun to the start of their name. Use the "pronoun_add" slash command to add a role to the watch list
''')

name_tracker = {} #could maybe benefit from permanent storage in case of bot restart/off/issuses

@client.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if before.channel is None:
        #They are entering a voice channel
        guildId = str(member.guild.id)
        memberRolesSet = {str(role.id) for role in member.roles}
        rolesToWatchSet = set(roles_watch["guilds"][guildId])
        if rolesToWatchSet & memberRolesSet:
            stringRoles = rolesToWatchSet.intersection(memberRolesSet)
            roles = [member.guild.get_role(int(stringRole)) for stringRole in stringRoles]
            role = max(roles, key= lambda k: k.position)
            role_string = str(role).split('/')[0]
            if member.display_name[:len(role_string)] == role_string:
                return
            name_tracker[member.id] = member.display_name
            await member.edit(nick=f"({role_string}) {member.display_name}"[:32])
        return
    if after.channel is None:
        #They are leaving a voice channel
        if member.id in name_tracker:
            await member.edit(nick=name_tracker[member.id])
            del name_tracker[member.id]
        return
    print(f"{str(member)} update on voice state:\n\tbefore: {str(before)}\n\tafter: {str(after)}")

def main():
    global roles_watch
    if not exists(database_file_name):
        with open(database_file_name, "w+") as database_file:
            database_file.write(json.dumps({"guilds": {}}))
    with open(database_file_name, "r") as database:
        roles_watch = json.load(database)

    key = ""
    with open("key.txt", "r") as keyfile:
        key = keyfile.read()

    client.run(key)

if __name__ == '__main__':
    main()