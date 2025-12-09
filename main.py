import discord
from discord.ext import commands
import asyncio
from database.db_manager import DatabaseManager
from spotify.spotify_client import SpotifyClient
import config

# Configuration du bot
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

class SpotifyTrackerBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )
        
        # Initialiser les managers
        self.db_manager = DatabaseManager()
        self.spotify_client = SpotifyClient()
    
    async def setup_hook(self):
        """Charge les cogs au démarrage"""
        await self.load_extension('cogs.commands')
        await self.load_extension('cogs.tasks')
        
        # Synchroniser les commandes slash
        await self.tree.sync()
        print("Commandes synchronisées !")
    
    async def on_ready(self):
        """Appelé quand le bot est prêt"""
        print(f'✅ Bot connecté en tant que {self.user}')
        print(f'ID: {self.user.id}')
        print('------')
        
        # Afficher les guildes
        print(f'Connecté à {len(self.guilds)} serveur(s):')
        for guild in self.guilds:
            print(f'  - {guild.name} (id: {guild.id})')
        
        print('------')
        print('Bot prêt ! 🎵')
    
    async def on_command_error(self, ctx, error):
        """Gestion des erreurs"""
        if isinstance(error, commands.CommandNotFound):
            return
        
        print(f'Erreur: {error}')
        
        embed = discord.Embed(
            title="❌ Erreur",
            description=f"Une erreur est survenue : {error}",
            color=0xFF0000
        )
        await ctx.send(embed=embed, ephemeral=True)

async def main():
    """Point d'entrée principal"""
    bot = SpotifyTrackerBot()
    
    try:
        await bot.start(config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        await bot.close()
    except Exception as e:
        print(f"Erreur fatale: {e}")
        await bot.close()

if __name__ == "__main__":
    print("🚀 Démarrage du bot Spotify Tracker...")
    print("------")
    
    # Vérifier la configuration
    if not config.DISCORD_TOKEN:
        print("❌ ERREUR: DISCORD_TOKEN non configuré dans le fichier .env")
        exit(1)
    
    if not config.SPOTIFY_CLIENT_ID or not config.SPOTIFY_CLIENT_SECRET:
        print("❌ ERREUR: Configuration Spotify manquante dans le fichier .env")
        exit(1)
    
    if not config.MYSQL_CONFIG['password']:
        print("❌ ERREUR: Mot de passe MySQL non configuré dans le fichier .env")
        exit(1)
    
    print("✅ Configuration OK")
    print("------")
    
    # Lancer le bot
    asyncio.run(main())