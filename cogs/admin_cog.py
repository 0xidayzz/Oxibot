# cogs/admin_cog.py
import discord
from discord.ext import commands
from helpers.database import get_db_connection

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='setchannel')
    @commands.has_permissions(administrator=True)
    async def set_channel_command(self, ctx, type_name, channel: discord.TextChannel = None):
        """Définit le salon pour les différents types d'annonces (musique, annonce, wrapped, follow)."""
        
        target_channel = channel or ctx.channel 
        
        type_map = {
            'musique': 'music_channel_id',
            'annonce': 'announcement_channel_id',
            'wrapped': 'wrapped_channel_id',
            'follow': 'follow_channel_id'
        }
        
        if type_name.lower() not in type_map:
            return await ctx.send("Type de salon invalide. Utilisez : `musique`, `annonce`, `wrapped`, ou `follow`.")

        db_column = type_map[type_name.lower()]
        conn = get_db_connection()
        
        # Met à jour ou Insère le channel ID
        conn.execute(f"""
            INSERT INTO server_settings (guild_id, {db_column})
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET {db_column}=excluded.{db_column}
        """, (ctx.guild.id, target_channel.id))
        
        conn.commit()
        conn.close()
        
        await ctx.send(f"✅ Le salon pour les **{type_name.upper()}** a été défini sur {target_channel.mention}.")

    @commands.command(name='theme')
    @commands.has_permissions(administrator=True)
    async def theme_command(self, ctx, new_theme: str = 'default'):
        """Permet de changer le thème d'affichage (actuellement 'default' = Violet)."""
        # Logique simplifiée. La gestion des thèmes serait implémentée dans MusicTracker.send_music_update
        
        conn = get_db_connection()
        conn.execute(
            "INSERT OR REPLACE INTO server_settings (guild_id, theme) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET theme=excluded.theme",
            (ctx.guild.id, new_theme.lower())
        )
        conn.commit()
        conn.close()
        
        await ctx.send(f"🎨 Thème mis à jour à **{new_theme.lower()}**. Le bot utilisera ce style pour les prochains embeds.")

def setup(bot):
    bot.add_cog(Admin(bot))