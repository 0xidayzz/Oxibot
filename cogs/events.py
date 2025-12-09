"""
Gestion des événements Discord
"""

import discord
from discord.ext import commands
from datetime import datetime
import config

class Events(commands.Cog):
    def __init__(self, bot, db_manager, spotify_client):
        self.bot = bot
        self.db = db_manager
        self.spotify = spotify_client
    
    @commands.Cog.listener()
    async def on_ready(self):
        """Événement déclenché quand le bot est prêt"""
        print(f'✅ Événements chargés - Bot actif sur {len(self.bot.guilds)} serveur(s)')
    
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        """Événement déclenché quand le bot rejoint un serveur"""
        print(f'📥 Bot ajouté au serveur: {guild.name} (ID: {guild.id})')
        
        # Créer la configuration pour ce serveur
        conn = self.db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT IGNORE INTO config (guild_id)
            VALUES (%s)
        """, (guild.id,))
        conn.commit()
        cursor.close()
        conn.close()
        
        # Envoyer un message de bienvenue dans le premier channel texte disponible
        for channel in guild.text_channels:
            if channel.permissions_for(guild.me).send_messages:
                embed = discord.Embed(
                    title="🎵 Merci de m'avoir ajouté !",
                    description=(
                        "Je suis ton assistant de suivi Spotify personnel !\n\n"
                        "**Premières étapes :**\n"
                        "1️⃣ Utilise `/setchannel` pour configurer les salons\n"
                        "2️⃣ Lance de la musique sur Spotify\n"
                        "3️⃣ Je commencerai automatiquement à suivre tes écoutes !\n\n"
                        "**Commandes utiles :**\n"
                        "• `/wrapped` - Ton récapitulatif d'écoute\n"
                        "• `/graph` - Visualise tes statistiques\n"
                        "• `/song` - Titre en cours\n"
                        "• `/top` - Tes tops titres/artistes\n"
                        "• `/info` - Infos sur un titre/artiste\n\n"
                        "**Fonctionnalités automatiques :**\n"
                        "🎧 Détection des titres en temps réel\n"
                        "✨ Notifications de nouvelles sorties\n"
                        "🏆 Paliers et achievements\n"
                        "📊 Wrapped hebdomadaires automatiques\n\n"
                        "Commence à écouter et profite ! 🎶"
                    ),
                    color=config.DEFAULT_THEME['color']
                )
                embed.set_footer(text="Utilise /help pour plus d'informations")
                
                try:
                    await channel.send(embed=embed)
                    break
                except:
                    continue
    
    @commands.Cog.listener()
    async def on_guild_remove(self, guild):
        """Événement déclenché quand le bot quitte un serveur"""
        print(f'📤 Bot retiré du serveur: {guild.name} (ID: {guild.id})')
        
        # Optionnel : Supprimer la configuration du serveur
        # conn = self.db.get_connection()
        # cursor = conn.cursor()
        # cursor.execute("DELETE FROM config WHERE guild_id = %s", (guild.id,))
        # conn.commit()
        # cursor.close()
        # conn.close()
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Gestion globale des erreurs de commandes"""
        if isinstance(error, commands.CommandNotFound):
            return
        
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permissions insuffisantes",
                description="Tu n'as pas les permissions nécessaires pour cette commande.",
                color=0xFF0000
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        if isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                title="❌ Permissions bot insuffisantes",
                description="Je n'ai pas les permissions nécessaires pour effectuer cette action.",
                color=0xFF0000
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ Cooldown actif",
                description=f"Cette commande est en cooldown. Réessaye dans {error.retry_after:.1f}s",
                color=0xFFA500
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        # Erreur non gérée
        print(f'❌ Erreur non gérée: {error}')
        embed = discord.Embed(
            title="❌ Erreur",
            description=f"Une erreur inattendue s'est produite : `{error}`",
            color=0xFF0000
        )
        embed.set_footer(text="Si l'erreur persiste, contacte le développeur")
        
        try:
            await ctx.send(embed=embed, ephemeral=True)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_app_command_error(self, interaction: discord.Interaction, error):
        """Gestion des erreurs pour les commandes slash"""
        if isinstance(error, discord.app_commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ Cooldown actif",
                description=f"Cette commande est en cooldown. Réessaye dans {error.retry_after:.1f}s",
                color=0xFFA500
            )
            
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if isinstance(error, discord.app_commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Permissions insuffisantes",
                description="Tu n'as pas les permissions nécessaires pour cette commande.",
                color=0xFF0000
            )
            
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Erreur non gérée
        print(f'❌ Erreur commande slash: {error}')
        embed = discord.Embed(
            title="❌ Erreur",
            description=f"Une erreur s'est produite : `{error}`",
            color=0xFF0000
        )
        
        try:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, ephemeral=True)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Événement déclenché à chaque message"""
        # Ignorer les messages du bot
        if message.author.bot:
            return
        
        # Traiter les commandes normalement
        await self.bot.process_commands(message)
    
    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Événement déclenché quand un membre rejoint le serveur"""
        # Cette fonction peut être utilisée pour envoyer un message de bienvenue
        # ou initialiser des données spécifiques à l'utilisateur
        pass
    
    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Événement déclenché quand un membre quitte le serveur"""
        # Cette fonction peut être utilisée pour nettoyer les données
        pass

async def setup(bot):
    db_manager = bot.db_manager
    spotify_client = bot.spotify_client
    await bot.add_cog(Events(bot, db_manager, spotify_client))