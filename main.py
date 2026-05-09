import discord
from discord import app_commands
from discord.ext import commands

from name import Name
from schedule import Schedule
from time_convert import TimeConvert

NAMING_GUILDS = [discord.Object(id=842812244965326869), discord.Object(id=366792929865498634), discord.Object(id=897201844256931891)]
LFG_GUILDS = [discord.Object(id=842812244965326869)]
GUILD_IDS = {842812244965326869, 366792929865498634, 897201844256931891}

intents = discord.Intents.default()
intents.members = True
intents.reactions = True


class WhisperingBot(commands.AutoShardedBot):
    async def setup_hook(self):
        await self.add_cog(Name(self), guilds=NAMING_GUILDS)
        # await self.add_cog(Schedule(self), guilds=LFG_GUILDS)
        await self.add_cog(TimeConvert(self))
        for gid in GUILD_IDS:
            try:
                synced = await self.tree.sync(guild=discord.Object(id=gid))
                print(f"Synced {len(synced)} command(s) to guild {gid}: {[c.name for c in synced]}")
            except discord.Forbidden:
                print(f"Skipping sync for guild {gid}: missing access (bot not in guild or lacks applications.commands scope)")


bot = WhisperingBot(commands.when_mentioned_or('?'), intents=intents)


@bot.event
async def on_ready():
    print('bot booted up!')
    print(f"Connected to {len(bot.guilds)} guild(s):")
    for g in bot.guilds:
        print(f"  - {g.name} ({g.id})")


@bot.tree.command(name="register", description="Register for the Whispering Mandrake bot!")
@app_commands.guilds(842812244965326869, 366792929865498634, 897201844256931891)
async def register(interaction: discord.Interaction):
    await interaction.response.send_message(
        "Go to https://d2firebase.web.app/ to register! Yes it does look sketchy but I promise it is safe"
    )


def main():
    with open("key.txt", "r") as keyfile:
        key = keyfile.read().strip()
    bot.run(key)


if __name__ == '__main__':
    main()
