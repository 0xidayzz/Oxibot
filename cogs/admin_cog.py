# SQUELETTE pour cogs/admin_cog.py
# ... imports ...
from helpers.database import get_db_connection

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='setchannel')
    @commands.has_permissions(administrator=True)
    async def set_channel_command(self, ctx, type_name, channel: discord.TextChannel = None):
        """Définit le salon pour les différents types d'annonces."""
        
        # Le salon est soit celui mentionné, soit le salon actuel
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
        
        # Upsert: Insérer si non existant, mettre à jour sinon
        conn.execute(f"""
            INSERT OR REPLACE INTO server_settings (guild_id, {db_column})
            VALUES (?, COALESCE((SELECT {db_column} FROM server_settings WHERE guild_id = ?), ?))
        """, (ctx.guild.id, ctx.guild.id, target_channel.id))
        
        conn.commit()
        conn.close()
        
        await ctx.send(f"✅ Le salon pour les **{type_name.upper()}** a été défini sur {target_channel.mention}.")

# ... suite des commandes admin (ex: /theme)