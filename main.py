# main.py
import discord
from discord.ext import commands
import os

# Import des helpers et cogs
from keep_alive import keep_alive # pour Replit
from helpers.database import setup_database
from cogs.music_tracker_cog import MusicTracker
# from cogs.stats_cog import Stats
# from cogs.admin_cog import Admin

# --- Initialisation ---

# 1. Mise en place de la base de données
setup_database()

# 2. Configuration du bot (Intents et Préfixe)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # Nécessaire pour les commandes admin

bot = commands.Bot(command_prefix='/', intents=intents, help_command=None)

# 3. Charger les Cogs
bot.add_cog(MusicTracker(bot))
# bot.add_cog(Stats(bot)) # À décommenter une fois codé
# bot.add_cog(Admin(bot)) # À décommenter une fois codé

# --- Commandes de Base ---

@bot.event
async def on_ready():
    print('----------------------------------')
    print(f'Bot démarré. Nom: {bot.user}')
    print(f'ID: {bot.user.id}')
    print('----------------------------------')
    await bot.change_presence(activity=discord.Game(name="/help | Suivi Spotify"))

@bot.command(name='help')
async def help_command(ctx):
    """Commande /help (À compléter dans Admin/Base Cog)."""
    embed = discord.Embed(
        title="🤖 Aide du Bot Spotify Tracker",
        description="Voici la liste des commandes principales. Utilisez `/setchannel musique` pour démarrer le suivi !",
        color=0x9B59B6
    )
    embed.add_field(name="🎶 Suivi Musique", value="`/song`, `/setchannel musique`", inline=False)
    embed.add_field(name="📊 Statistiques (WIP)", value="`/stats`, `/wrapped`, `/graph`, `/search`", inline=False)
    embed.add_field(name="⭐ Artistes Suivis (WIP)", value="`/follow`, `/listfollow`, `/unfollow`", inline=False)
    embed.add_field(name="⚙️ Administration", value="`/setchannel`, `/theme`", inline=False)
    await ctx.send(embed=embed)


# --- Démarrage ---

if __name__ == '__main__':
    # Lance le serveur web pour garder le bot actif sur Replit
    keep_alive() 
    
    TOKEN = os.getenv('DISCORD_TOKEN')
    if not TOKEN:
        print("ERREUR: Le token Discord n'est pas trouvé. Vérifiez les Secrets Replit.")
    else:
        try:
            bot.run(TOKEN)
        except discord.errors.LoginFailure:
            print("ERREUR: Token Discord invalide.")