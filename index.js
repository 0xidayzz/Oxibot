// index.js - Bot Discord Premium Spotify Tracker - VERSION OPTIMISÉE
const { Client, GatewayIntentBits, EmbedBuilder, SlashCommandBuilder, REST, Routes, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const { Pool } = require('pg');
const axios = require('axios');

// Configuration
const config = {
  discordToken: process.env.DISCORD_TOKEN,
  spotifyClientId: process.env.SPOTIFY_CLIENT_ID,
  spotifyClientSecret: process.env.SPOTIFY_CLIENT_SECRET,
  spotifyRefreshToken: process.env.SPOTIFY_REFRESH_TOKEN,
  databaseUrl: process.env.DATABASE_URL || 'postgresql://postgres:password@helium/heliumdb?sslmode=disable'
};

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent]
});

// PostgreSQL Connection avec gestion d'erreurs
const pool = new Pool({
  connectionString: config.databaseUrl,
  ssl: config.databaseUrl.includes('sslmode=disable') ? false : { rejectUnauthorized: false }
});

// Gestion des erreurs de connexion
pool.on('error', (err) => {
  console.error('❌ Erreur PostgreSQL:', err);
});

// Initialisation de la base de données PostgreSQL
async function initDatabase() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS spotify_tracks (
        id SERIAL PRIMARY KEY,
        track_id TEXT UNIQUE NOT NULL,
        track_name TEXT NOT NULL,
        artist TEXT NOT NULL,
        album TEXT,
        album_cover TEXT,
        duration_ms INTEGER,
        listen_count INTEGER DEFAULT 1,
        total_listen_time INTEGER DEFAULT 0,
        skip_count INTEGER DEFAULT 0,
        completed_listens INTEGER DEFAULT 0,
        first_listened TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_listened TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        spotify_url TEXT,
        preview_url TEXT,
        popularity INTEGER
      )
    `);

    await pool.query(`
      CREATE TABLE IF NOT EXISTS spotify_listens (
        id SERIAL PRIMARY KEY,
        track_id TEXT NOT NULL,
        listened_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        duration_ms INTEGER,
        completed BOOLEAN DEFAULT FALSE,
        time_of_day TEXT,
        day_of_week TEXT
      )
    `);

    await pool.query(`
      CREATE TABLE IF NOT EXISTS spotify_artists (
        id SERIAL PRIMARY KEY,
        artist_name TEXT UNIQUE NOT NULL,
        listen_count INTEGER DEFAULT 0,
        total_time INTEGER DEFAULT 0,
        genres TEXT,
        image_url TEXT
      )
    `);

    await pool.query(`
      CREATE TABLE IF NOT EXISTS discord_config (
        id SERIAL PRIMARY KEY,
        guild_id TEXT UNIQUE NOT NULL,
        spotify_channel_id TEXT,
        announcements_channel_id TEXT,
        spotify_notifications BOOLEAN DEFAULT TRUE
      )
    `);

    await pool.query(`
      CREATE TABLE IF NOT EXISTS achievements (
        id SERIAL PRIMARY KEY,
        key TEXT UNIQUE NOT NULL,
        achieved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
      )
    `);

    await pool.query(`
      CREATE TABLE IF NOT EXISTS daily_stats (
        id SERIAL PRIMARY KEY,
        date DATE UNIQUE NOT NULL,
        spotify_time INTEGER DEFAULT 0,
        tracks_played INTEGER DEFAULT 0
      )
    `);

    console.log('✅ Base de données PostgreSQL initialisée');
  } catch (error) {
    console.error('❌ Erreur initialisation DB:', error);
  }
}

let spotifyAccessToken = '';
let lastSpotifyTrack = null;
let trackStartTime = null;

// Système de paliers/achievements
const achievements = {
  listening_time: [
    { hours: 1, emoji: '🎵', title: 'Première heure', desc: 'Tu as écouté 1h de musique !' },
    { hours: 10, emoji: '🎶', title: 'Mélomane', desc: 'Tu as écouté 10h de musique !' },
    { hours: 50, emoji: '🎸', title: 'Fan de musique', desc: 'Tu as écouté 50h de musique !' },
    { hours: 100, emoji: '🎤', title: 'Audiophile', desc: 'Tu as écouté 100h de musique !' },
    { hours: 500, emoji: '👑', title: 'Roi de Spotify', desc: 'Tu as écouté 500h de musique !' },
    { hours: 1000, emoji: '🏆', title: 'Légende', desc: 'Tu as écouté 1000h de musique !' }
  ],
  track_listens: [
    { count: 10, emoji: '⭐', title: 'Fan', desc: 'Tu as écouté une musique 10 fois !' },
    { count: 20, emoji: '🔥', title: 'Super Fan', desc: 'Tu as écouté une musique 20 fois !' },
    { count: 50, emoji: '💎', title: 'Obsédé', desc: 'Tu as écouté une musique 50 fois !' },
    { count: 100, emoji: '👑', title: 'Hymne personnel', desc: 'Tu as écouté une musique 100 fois !' },
    { count: 500, emoji: '🏆', title: 'Boucle infinie', desc: 'Tu as écouté une musique 500 fois !' }
  ],
  artist_listens: [
    { count: 10, emoji: '🎵', title: 'Découverte', desc: 'Tu as écouté un artiste 10 fois !' },
    { count: 50, emoji: '🎶', title: 'Fan', desc: 'Tu as écouté un artiste 50 fois !' },
    { count: 100, emoji: '⭐', title: 'Super Fan', desc: 'Tu as écouté un artiste 100 fois !' },
    { count: 500, emoji: '💎', title: 'Groupie', desc: 'Tu as écouté un artiste 500 fois !' },
    { count: 1000, emoji: '👑', title: 'Fan ultime', desc: 'Tu as écouté un artiste 1000 fois !' }
  ],
  unique_tracks: [
    { count: 100, emoji: '📀', title: 'Explorateur', desc: 'Tu as écouté 100 musiques différentes !' },
    { count: 500, emoji: '💿', title: 'Collectionneur', desc: 'Tu as écouté 500 musiques différentes !' },
    { count: 1000, emoji: '📻', title: 'Bibliothèque', desc: 'Tu as écouté 1000 musiques différentes !' },
    { count: 5000, emoji: '🎼', title: 'Encyclopédie', desc: 'Tu as écouté 5000 musiques différentes !' }
  ]
};

async function checkAchievements(type, value, name = '') {
  const list = achievements[type];
  if (!list) return;

  for (const achievement of list) {
    const key = `${type}_${achievement.count || achievement.hours}`;
    
    try {
      const result = await pool.query('SELECT * FROM achievements WHERE key = $1', [key]);
      
      if (result.rows.length === 0 && ((achievement.count && value >= achievement.count) || (achievement.hours && value >= achievement.hours))) {
        await pool.query('INSERT INTO achievements (key, achieved_at) VALUES ($1, CURRENT_TIMESTAMP)', [key]);
        await notifyAchievement(achievement, name);
      }
    } catch (error) {
      console.error('❌ Erreur check achievement:', error);
    }
  }
}

async function notifyAchievement(achievement, detail = '') {
  try {
    // Vérifier que le client est prêt
    if (!client.isReady()) {
      console.log('⚠️ Client Discord pas encore prêt pour achievement');
      return;
    }

    const result = await pool.query('SELECT announcements_channel_id FROM discord_config LIMIT 1');
    
    if (result.rows.length > 0 && result.rows[0].announcements_channel_id) {
      const channel = await client.channels.fetch(result.rows[0].announcements_channel_id);
      if (channel) {
        const embed = new EmbedBuilder()
          .setColor('#FFD700')
          .setTitle(`${achievement.emoji} PALIER ATTEINT !`)
          .setDescription(`**${achievement.title}**\n${achievement.desc}${detail ? `\n\n*${detail}*` : ''}`)
          .setThumbnail('https://i.imgur.com/9fz2gQX.png')
          .setTimestamp()
          .setFooter({ text: '🏆 Achievement Unlocked' });

        await channel.send({ embeds: [embed] });
      }
    }
  } catch (error) {
    console.error('❌ Erreur notification achievement:', error);
  }
}

// ==================== SPOTIFY ====================

async function refreshSpotifyToken() {
  try {
    if (!config.spotifyClientId || !config.spotifyClientSecret || !config.spotifyRefreshToken) {
      console.error('❌ Spotify: Credentials manquantes');
      return false;
    }

    const response = await axios.post('https://accounts.spotify.com/api/token', 
      new URLSearchParams({
        grant_type: 'refresh_token',
        refresh_token: config.spotifyRefreshToken
      }), {
        headers: {
          'Authorization': 'Basic ' + Buffer.from(config.spotifyClientId + ':' + config.spotifyClientSecret).toString('base64'),
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      }
    );
    
    spotifyAccessToken = response.data.access_token;
    console.log('✅ Spotify token refreshed');
    return true;
  } catch (error) {
    console.error('❌ Erreur refresh Spotify token:', error.message);
    return false;
  }
}

async function getCurrentSpotifyTrack() {
  try {
    if (!spotifyAccessToken) {
      console.log('⚠️ Pas de token Spotify, tentative de refresh...');
      await refreshSpotifyToken();
    }

    const response = await axios.get('https://api.spotify.com/v1/me/player/currently-playing', {
      headers: { 'Authorization': `Bearer ${spotifyAccessToken}` }
    });

    if (response.status === 204 || !response.data) {
      return null;
    }

    if (response.data && response.data.is_playing) {
      const track = response.data.item;
      return {
        id: track.id,
        name: track.name,
        artist: track.artists.map(a => a.name).join(', '),
        artists: track.artists,
        album: track.album.name,
        albumCover: track.album.images[0]?.url,
        duration: track.duration_ms,
        progress: response.data.progress_ms,
        url: track.external_urls.spotify,
        previewUrl: track.preview_url,
        popularity: track.popularity
      };
    }
    return null;
  } catch (error) {
    if (error.response?.status === 401) {
      console.log('⚠️ Token expiré, refresh...');
      await refreshSpotifyToken();
    }
    return null;
  }
}

async function saveSpotifyTrack(track, completed = false) {
  try {
    const now = new Date();
    const today = now.toISOString().split('T')[0];
    const timeOfDay = now.getHours() < 12 ? 'morning' : now.getHours() < 18 ? 'afternoon' : 'evening';
    const dayOfWeek = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'][now.getDay()];

    console.log(`💾 Sauvegarde: ${track.name} - ${track.artist} (completed: ${completed})`);

    // Upsert track
    await pool.query(`
      INSERT INTO spotify_tracks (
        track_id, track_name, artist, album, album_cover, duration_ms,
        listen_count, total_listen_time, completed_listens, last_listened,
        spotify_url, preview_url, popularity
      ) VALUES ($1, $2, $3, $4, $5, $6, 1, $7, $8, CURRENT_TIMESTAMP, $9, $10, $11)
      ON CONFLICT (track_id) DO UPDATE SET
        listen_count = spotify_tracks.listen_count + 1,
        total_listen_time = spotify_tracks.total_listen_time + $7,
        completed_listens = spotify_tracks.completed_listens + $8,
        last_listened = CURRENT_TIMESTAMP
    `, [
      track.id, track.name, track.artist, track.album, track.albumCover,
      track.duration, track.duration, completed ? 1 : 0, track.url,
      track.previewUrl, track.popularity
    ]);

    // Insert listen
    await pool.query(`
      INSERT INTO spotify_listens (track_id, duration_ms, completed, time_of_day, day_of_week)
      VALUES ($1, $2, $3, $4, $5)
    `, [track.id, track.duration, completed, timeOfDay, dayOfWeek]);

    // Upsert artists
    for (const artist of track.artists) {
      await pool.query(`
        INSERT INTO spotify_artists (artist_name, listen_count, total_time)
        VALUES ($1, 1, $2)
        ON CONFLICT (artist_name) DO UPDATE SET
          listen_count = spotify_artists.listen_count + 1,
          total_time = spotify_artists.total_time + $2
      `, [artist.name, track.duration]);
    }

    // Daily stats
    await pool.query(`
      INSERT INTO daily_stats (date, spotify_time, tracks_played)
      VALUES ($1, $2, 1)
      ON CONFLICT (date) DO UPDATE SET
        spotify_time = daily_stats.spotify_time + $2,
        tracks_played = daily_stats.tracks_played + 1
    `, [today, track.duration]);

    console.log('✅ Track sauvegardé en DB');

    // Vérifier les achievements
    const totalTimeResult = await pool.query('SELECT SUM(total_listen_time) as total FROM spotify_tracks');
    if (totalTimeResult.rows[0] && totalTimeResult.rows[0].total) {
      const hours = Math.floor(totalTimeResult.rows[0].total / 3600000);
      await checkAchievements('listening_time', hours);
    }

    const trackStatsResult = await pool.query('SELECT listen_count FROM spotify_tracks WHERE track_id = $1', [track.id]);
    if (trackStatsResult.rows[0]) {
      await checkAchievements('track_listens', trackStatsResult.rows[0].listen_count, track.name);
    }

    const artistStatsResult = await pool.query('SELECT listen_count FROM spotify_artists WHERE artist_name = $1', [track.artist]);
    if (artistStatsResult.rows[0]) {
      await checkAchievements('artist_listens', artistStatsResult.rows[0].listen_count, track.artist);
    }

    const uniqueTracksResult = await pool.query('SELECT COUNT(*) as count FROM spotify_tracks');
    if (uniqueTracksResult.rows[0]) {
      await checkAchievements('unique_tracks', parseInt(uniqueTracksResult.rows[0].count));
    }

  } catch (error) {
    console.error('❌ Erreur save track:', error);
  }
}

async function notifySpotifyTrack(track) {
  try {
    // Vérifier que le client est prêt
    if (!client.isReady()) {
      console.log('⚠️ Client Discord pas encore prêt');
      return;
    }

    const configResult = await pool.query('SELECT spotify_channel_id, spotify_notifications FROM discord_config LIMIT 1');
    
    if (configResult.rows.length === 0 || !configResult.rows[0].spotify_channel_id || !configResult.rows[0].spotify_notifications) {
      return;
    }

    const channel = await client.channels.fetch(configResult.rows[0].spotify_channel_id);
    if (!channel) return;

    const statsResult = await pool.query('SELECT listen_count, total_listen_time, completed_listens FROM spotify_tracks WHERE track_id = $1', [track.id]);
    const stats = statsResult.rows[0] || { listen_count: 0, total_listen_time: 0, completed_listens: 0 };

    const artistStatsResult = await pool.query('SELECT listen_count, total_time FROM spotify_artists WHERE artist_name = $1', [track.artist]);
    const artistStats = artistStatsResult.rows[0] || { listen_count: 0, total_time: 0 };

    const listenCount = stats.listen_count;
    const totalMinutes = Math.round(stats.total_listen_time / 60000);
    const completedListens = stats.completed_listens;
    const artistListens = artistStats.listen_count;
    const artistHours = Math.round(artistStats.total_time / 3600000);

    const duration = `${Math.floor(track.duration/60000)}:${String(Math.floor((track.duration%60000)/1000)).padStart(2, '0')}`;

    let statusEmoji = '🆕';
    if (listenCount >= 50) statusEmoji = '👑';
    else if (listenCount >= 20) statusEmoji = '💎';
    else if (listenCount >= 10) statusEmoji = '⭐';
    else if (listenCount >= 5) statusEmoji = '🔥';

    const embed = new EmbedBuilder()
      .setColor('#1DB954')
      .setAuthor({ name: `${statusEmoji} Actuellement en écoute`, iconURL: 'https://i.imgur.com/vFqjWF3.png' })
      .setTitle(track.name.length > 50 ? track.name.substring(0, 47) + '...' : track.name)
      .setDescription(`> **${track.artist}**\n> ${track.album}`)
      .setThumbnail(track.albumCover)
      .addFields(
        { name: '⏱️ Durée', value: `\`${duration}\``, inline: true },
        { name: '🔥 Popularité', value: `\`${track.popularity}/100\``, inline: true },
        { name: '📊 Écoutes', value: `\`${listenCount}x\``, inline: true },
        { name: '✅ Complètes', value: `\`${completedListens}x\``, inline: true },
        { name: '⏰ Temps total', value: `\`${totalMinutes}min\``, inline: true },
        { name: '🎤 Artiste', value: `\`${artistListens}x (${artistHours}h)\``, inline: true }
      )
      .addFields({ name: '▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬', value: '\u200b', inline: false })
      .setTimestamp()
      .setFooter({ text: `🎧 Spotify Premium Tracker • ${new Date().toLocaleDateString('fr-FR')}` });

    const rowButtons = new ActionRowBuilder().addComponents(
      new ButtonBuilder().setLabel('Spotify').setURL(track.url).setStyle(ButtonStyle.Link).setEmoji('🎵')
    );

    await channel.send({ embeds: [embed], components: [rowButtons] });
  } catch (error) {
    console.error('❌ Erreur notification Spotify:', error);
  }
}

async function generateSpotifyWrapped() {
  try {
    const stats = {};
    
    const generalResult = await pool.query(`
      SELECT 
        COUNT(*) as total_tracks,
        SUM(listen_count) as total_listens,
        SUM(total_listen_time) as total_time
      FROM spotify_tracks
    `);
    stats.general = generalResult.rows[0] || { total_tracks: 0, total_listens: 0, total_time: 0 };

    const topTracksResult = await pool.query(`
      SELECT track_name, artist, listen_count, album_cover
      FROM spotify_tracks
      ORDER BY listen_count DESC
      LIMIT 5
    `);
    stats.topTracks = topTracksResult.rows;

    const topArtistsResult = await pool.query(`
      SELECT artist_name, listen_count, total_time
      FROM spotify_artists
      ORDER BY listen_count DESC
      LIMIT 5
    `);
    stats.topArtists = topArtistsResult.rows;

    const timeStatsResult = await pool.query(`
      SELECT time_of_day, COUNT(*) as count
      FROM spotify_listens
      GROUP BY time_of_day
      ORDER BY count DESC
    `);
    stats.timeStats = timeStatsResult.rows;

    return stats;
  } catch (error) {
    console.error('❌ Erreur generate wrapped:', error);
    return null;
  }
}

// ==================== COMMANDES ====================

const commands = [
  new SlashCommandBuilder()
    .setName('spotify')
    .setDescription('Commandes Spotify')
    .addSubcommand(sub => sub.setName('channel').setDescription('Configure le channel de notifications'))
    .addSubcommand(sub => sub.setName('toggle').setDescription('Active/désactive les notifications'))
    .addSubcommand(sub => sub.setName('top').setDescription('Top 10 musiques et artistes'))
    .addSubcommand(sub => sub.setName('search').setDescription('Rechercher une musique')
      .addStringOption(opt => opt.setName('query').setDescription('Recherche').setRequired(true)))
    .addSubcommand(sub => sub.setName('stats').setDescription('Statistiques détaillées'))
    .addSubcommand(sub => sub.setName('wrapped').setDescription('Récapitulatif Wrapped'))
    .addSubcommand(sub => sub.setName('current').setDescription('Musique en cours'))
    .addSubcommand(sub => sub.setName('compare').setDescription('Comparer deux artistes')
      .addStringOption(opt => opt.setName('artist1').setDescription('Artiste 1').setRequired(true))
      .addStringOption(opt => opt.setName('artist2').setDescription('Artiste 2').setRequired(true))),

  new SlashCommandBuilder()
    .setName('dashboard')
    .setDescription('Tableau de bord global'),

  new SlashCommandBuilder()
    .setName('achievements')
    .setDescription('Voir les paliers')
    .addSubcommand(sub => sub.setName('list').setDescription('Liste de tous les paliers'))
    .addSubcommand(sub => sub.setName('progress').setDescription('Ta progression actuelle')),

  new SlashCommandBuilder()
    .setName('insights')
    .setDescription('Analyses avancées')
    .addSubcommand(sub => sub.setName('mood').setDescription('Analyse de tes humeurs musicales'))
    .addSubcommand(sub => sub.setName('discovery').setDescription('Taux de découverte'))
    .addSubcommand(sub => sub.setName('habits').setDescription('Tes habitudes d\'écoute')),

  new SlashCommandBuilder()
    .setName('setup')
    .setDescription('Configuration initiale du bot')
    .addChannelOption(opt => opt.setName('spotify').setDescription('Channel pour Spotify').setRequired(true))
    .addChannelOption(opt => opt.setName('announcements').setDescription('Channel pour les annonces').setRequired(true))
].map(cmd => cmd.toJSON());

// ==================== BOT START ====================

client.once('ready', async () => {
  console.log(`✅ Bot connecté: ${client.user.tag}`);
  console.log(`📊 Serveurs: ${client.guilds.cache.size}`);
  console.log(`👥 Utilisateurs: ${client.users.cache.size}`);
  
  try {
    // Initialiser la base de données
    await initDatabase();
    console.log('✅ Base de données initialisée');

    // Enregistrer les commandes
    const rest = new REST({ version: '10' }).setToken(config.discordToken);
    await rest.put(Routes.applicationCommands(client.user.id), { body: commands });
    console.log('✅ Commandes slash enregistrées');

    // Initialiser Spotify
    const tokenRefreshed = await refreshSpotifyToken();
    if (tokenRefreshed) {
      console.log('🎵 Token Spotify obtenu, démarrage du tracking...');
      startSpotifyTracking();
    } else {
      console.error('❌ Impossible d\'obtenir le token Spotify. Vérifiez vos credentials.');
    }

  } catch (error) {
    console.error('❌ Erreur lors de l\'initialisation:', error);
  }
});

// Fonction de tracking Spotify séparée
function startSpotifyTracking() {
  // Tracking Spotify toutes les 30 secondes
  setInterval(async () => {
    try {
      const track = await getCurrentSpotifyTrack();

      if (track) {
        console.log(`🎵 En écoute: ${track.name}`);

        if (!lastSpotifyTrack || lastSpotifyTrack.id !== track.id) {
          // Sauvegarder la précédente track
          if (lastSpotifyTrack && trackStartTime) {
            const listenDuration = Date.now() - trackStartTime;
            const completed = listenDuration >= (lastSpotifyTrack.duration * 0.8);
            await saveSpotifyTrack(lastSpotifyTrack, completed);
          }

          // IMPORTANT: Sauvegarder d'abord PUIS notifier
          lastSpotifyTrack = track;
          trackStartTime = Date.now();
          
          // Petite attente pour s'assurer que la DB est à jour
          setTimeout(async () => {
            await notifySpotifyTrack(track);
          }, 500);
        }
      } else {
        // Plus rien en écoute
        if (lastSpotifyTrack && trackStartTime) {
          const listenDuration = Date.now() - trackStartTime;
          const completed = listenDuration >= (lastSpotifyTrack.duration * 0.8);
          await saveSpotifyTrack(lastSpotifyTrack, completed);
          lastSpotifyTrack = null;
          trackStartTime = null;
        }
      }
    } catch (error) {
      console.error('❌ Erreur tracking Spotify:', error.message);
    }
  }, 30000);

  // Refresh token toutes les 50 minutes
  setInterval(async () => {
    try {
      await refreshSpotifyToken();
    } catch (error) {
      console.error('❌ Erreur refresh token:', error);
    }
  }, 3000000);
  
  console.log('✅ Tracking Spotify démarré (intervalle: 30s)');
}

// ==================== GESTION COMMANDES ====================

client.on('interactionCreate', async interaction => {
  if (!interaction.isChatInputCommand()) return;
  
  const { commandName, options } = interaction;

  // ==================== SETUP ====================
  if (commandName === 'setup') {
    try {
      const spotifyChannel = options.getChannel('spotify');
      const announcementsChannel = options.getChannel('announcements');

      await pool.query(`
        INSERT INTO discord_config (guild_id, spotify_channel_id, announcements_channel_id, spotify_notifications)
        VALUES ($1, $2, $3, TRUE)
        ON CONFLICT (guild_id) DO UPDATE SET
          spotify_channel_id = $2,
          announcements_channel_id = $3
      `, [interaction.guildId, spotifyChannel.id, announcementsChannel.id]);

      const embed = new EmbedBuilder()
        .setColor('#1DB954')
        .setTitle('✅ Configuration terminée !')
        .setDescription('Le bot est maintenant configuré et prêt à tracker ta musique.')
        .addFields(
          { name: '🎵 Channel Spotify', value: `<#${spotifyChannel.id}>`, inline: true },
          { name: '📢 Channel Annonces', value: `<#${announcementsChannel.id}>`, inline: true }
        )
        .setTimestamp();

      await interaction.reply({ embeds: [embed] });
    } catch (error) {
      console.error('❌ Erreur setup:', error);
      await interaction.reply('❌ Erreur lors de la configuration.');
    }
  }

  // ==================== SPOTIFY ====================
  if (commandName === 'spotify') {
    const sub = options.getSubcommand();

    if (sub === 'channel') {
      try {
        await pool.query(`
          INSERT INTO discord_config (guild_id, spotify_channel_id, spotify_notifications)
          VALUES ($1, $2, TRUE)
          ON CONFLICT (guild_id) DO UPDATE SET spotify_channel_id = $2
        `, [interaction.guildId, interaction.channelId]);

        await interaction.reply('✅ Channel configuré pour Spotify !');
      } catch (error) {
        console.error('❌ Erreur channel:', error);
        await interaction.reply('❌ Erreur lors de la configuration.');
      }
    }

    if (sub === 'toggle') {
      try {
        const result = await pool.query('SELECT spotify_notifications FROM discord_config WHERE guild_id = $1', [interaction.guildId]);
        const newState = result.rows.length > 0 ? !result.rows[0].spotify_notifications : true;

        await pool.query(`
          INSERT INTO discord_config (guild_id, spotify_notifications)
          VALUES ($1, $2)
          ON CONFLICT (guild_id) DO UPDATE SET spotify_notifications = $2
        `, [interaction.guildId, newState]);

        await interaction.reply(`🔔 Notifications ${newState ? 'activées ✅' : 'désactivées ❌'} !`);
      } catch (error) {
        console.error('❌ Erreur toggle:', error);
        await interaction.reply('❌ Erreur lors du changement.');
      }
    }

    if (sub === 'current') {
      const track = await getCurrentSpotifyTrack();
      if (!track) return interaction.reply('❌ Aucune musique en cours.');

      const progressPercent = Math.round((track.progress / track.duration) * 100);
      const progressBar = '█'.repeat(Math.floor(progressPercent / 5)) + '░'.repeat(20 - Math.floor(progressPercent / 5));

      const embed = new EmbedBuilder()
        .setColor('#1DB954')
        .setTitle('🎵 En écoute maintenant')
        .setDescription(`**${track.name}**\n${track.artist}`)
        .setThumbnail(track.albumCover)
        .addFields(
          { name: 'Album', value: track.album, inline: true },
          { name: 'Popularité', value: `${track.popularity}/100`, inline: true },
          { name: 'Progression', value: `${progressBar} ${progressPercent}%\n\`${Math.floor(track.progress/1000)}s / ${Math.floor(track.duration/1000)}s\``, inline: false }
        )
        .setTimestamp();

      const row = new ActionRowBuilder().addComponents(
        new ButtonBuilder().setLabel('Ouvrir sur Spotify').setURL(track.url).setStyle(ButtonStyle.Link).setEmoji('🎵')
      );

      await interaction.reply({ embeds: [embed], components: [row] });
    }

    if (sub === 'top') {
      await interaction.deferReply();

      try {
        const tracksResult = await pool.query(`
          SELECT track_name, artist, listen_count, total_listen_time
          FROM spotify_tracks
          ORDER BY listen_count DESC
          LIMIT 10
        `);

        if (tracksResult.rows.length === 0) {
          return interaction.editReply('❌ Aucune donnée disponible.');
        }

        const embed1 = new EmbedBuilder()
          .setColor('#1DB954')
          .setTitle('🎵 Top 10 Musiques')
          .setDescription(tracksResult.rows.map((t, i) => {
            const minutes = Math.round(t.total_listen_time / 60000);
            return `**${i+1}.** ${t.track_name}\n> ${t.artist} • \`${t.listen_count}x\` • \`${minutes}min\``;
          }).join('\n\n'))
          .setTimestamp();

        await interaction.editReply({ embeds: [embed1] });

        const artistsResult = await pool.query(`
          SELECT artist_name, listen_count, total_time
          FROM spotify_artists
          ORDER BY listen_count DESC
          LIMIT 10
        `);

        if (artistsResult.rows.length > 0) {
          const embed2 = new EmbedBuilder()
            .setColor('#1DB954')
            .setTitle('🎤 Top 10 Artistes')
            .setDescription(artistsResult.rows.map((a, i) => {
              const hours = Math.floor(a.total_time / 3600000);
              const minutes = Math.round((a.total_time % 3600000) / 60000);
              return `**${i+1}.** ${a.artist_name}\n> \`${a.listen_count}x\` • \`${hours}h ${minutes}min\``;
            }).join('\n\n'))
            .setTimestamp();

          await interaction.followUp({ embeds: [embed2] });
        }
      } catch (error) {
        console.error('❌ Erreur top:', error);
        await interaction.editReply('❌ Erreur lors de la récupération des données.');
      }
    }

    if (sub === 'search') {
      const query = options.getString('query');

      try {
        const result = await pool.query(`
          SELECT * FROM spotify_tracks
          WHERE track_name ILIKE $1 OR artist ILIKE $1
          ORDER BY listen_count DESC
          LIMIT 5
        `, [`%${query}%`]);

        if (result.rows.length === 0) {
          return interaction.reply(`❌ Aucun résultat pour "${query}"`);
        }

        const embed = new EmbedBuilder()
          .setColor('#1DB954')
          .setTitle(`🔍 Résultats pour "${query}"`)
          .setDescription(result.rows.map(t => {
            const minutes = Math.round(t.total_listen_time / 60000);
            return `**${t.track_name}**\n> ${t.artist}\n> \`${t.listen_count}x\` • \`${minutes}min\``;
          }).join('\n\n'))
          .setTimestamp();

        await interaction.reply({ embeds: [embed] });
      } catch (error) {
        console.error('❌ Erreur search:', error);
        await interaction.reply('❌ Erreur lors de la recherche.');
      }
    }

    if (sub === 'stats') {
      await interaction.deferReply();

      try {
        const statsResult = await pool.query(`
          SELECT 
            COUNT(*) as total_tracks,
            SUM(listen_count) as total_listens,
            SUM(total_listen_time) as total_time,
            AVG(popularity) as avg_popularity
          FROM spotify_tracks
        `);
        const stats = statsResult.rows[0];

        const artistsResult = await pool.query('SELECT COUNT(DISTINCT artist_name) as unique_artists FROM spotify_artists');
        const uniqueArtists = artistsResult.rows[0].unique_artists;

        const mostPlayedResult = await pool.query(`
          SELECT track_name, artist, listen_count
          FROM spotify_tracks
          ORDER BY listen_count DESC
          LIMIT 1
        `);
        const mostPlayed = mostPlayedResult.rows[0];

        const hours = Math.floor((stats.total_time || 0) / 3600000);
        const minutes = Math.round(((stats.total_time || 0) % 3600000) / 60000);
        const avgListens = Math.round((stats.total_listens || 0) / Math.max(1, stats.total_tracks || 1));
        const days = Math.floor(hours / 24);

        const embed = new EmbedBuilder()
          .setColor('#1DB954')
          .setAuthor({ name: '📊 Statistiques Spotify Détaillées', iconURL: 'https://i.imgur.com/vFqjWF3.png' })
          .setDescription('> Analyse complète de ton activité musicale')
          .addFields(
            { name: '\u200b', value: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', inline: false },
            { name: '🎵 Bibliothèque', value: `\`\`\`yaml\nMorceaux: ${stats.total_tracks || 0}\nArtistes: ${uniqueArtists || 0}\n\`\`\``, inline: true },
            { name: '📊 Écoutes', value: `\`\`\`yaml\nTotal: ${stats.total_listens || 0}\nMoyenne: ${avgListens}/titre\n\`\`\``, inline: true },
            { name: '⏱️ Temps', value: `\`\`\`yaml\n${hours}h ${minutes}min\n${days} jours continus\n\`\`\``, inline: true },
            { name: '\u200b', value: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', inline: false },
            { name: '🔥 Popularité moyenne', value: `\`${Math.round(stats.avg_popularity || 0)}/100\``, inline: true }
          );

        if (mostPlayed) {
          embed.addFields(
            { name: '👑 Titre le plus écouté', value: `**${mostPlayed.track_name}**\n${mostPlayed.artist}\n\`${mostPlayed.listen_count}x\``, inline: true },
            { name: '📈 Rythme d\'écoute', value: `\`${Math.round((stats.total_listens || 0) / Math.max(1, days))} titres/jour\``, inline: true }
          );
        }

        embed.setTimestamp().setFooter({ text: '🎧 Analytics Premium' });

        await interaction.editReply({ embeds: [embed] });
      } catch (error) {
        console.error('❌ Erreur stats:', error);
        await interaction.editReply('❌ Erreur lors de la récupération des statistiques.');
      }
    }

    if (sub === 'wrapped') {
      await interaction.deferReply();

      try {
        const stats = await generateSpotifyWrapped();
        if (!stats) {
          return interaction.editReply('❌ Erreur lors de la génération du Wrapped.');
        }

        const hours = Math.floor((stats.general?.total_time || 0) / 3600000);
        const minutes = Math.round(((stats.general?.total_time || 0) % 3600000) / 60000);

        const embed = new EmbedBuilder()
          .setColor('#1DB954')
          .setAuthor({ name: '🎊 Spotify Wrapped', iconURL: 'https://i.imgur.com/vFqjWF3.png' })
          .setTitle('Récapitulatif • Tous les temps')
          .setDescription('> Découvre tes statistiques musicales !')
          .addFields(
            { name: '\u200b', value: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', inline: false },
            { name: '⏱️ Temps d\'écoute total', value: `\`\`\`yaml\n${hours}h ${minutes}min\n\`\`\``, inline: true },
            { name: '🎵 Morceaux écoutés', value: `\`\`\`yaml\n${stats.general?.total_tracks || 0} titres\n\`\`\``, inline: true },
            { name: '🔁 Total d\'écoutes', value: `\`\`\`yaml\n${stats.general?.total_listens || 0}x\n\`\`\``, inline: true },
            { name: '\u200b', value: '**🏆 TOP 5 MORCEAUX**', inline: false }
          );

        if (stats.topTracks && stats.topTracks.length > 0) {
          stats.topTracks.forEach((t, i) => {
            const emoji = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][i];
            embed.addFields({
              name: `${emoji} ${t.track_name}`,
              value: `> ${t.artist} • \`${t.listen_count}x\``,
              inline: false
            });
          });
        }

        embed.addFields({ name: '\u200b', value: '**🎤 TOP 5 ARTISTES**', inline: false });

        if (stats.topArtists && stats.topArtists.length > 0) {
          stats.topArtists.forEach((a, i) => {
            const emoji = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣'][i];
            const artistHours = Math.floor((a.total_time || 0) / 3600000);
            const artistMinutes = Math.round(((a.total_time || 0) % 3600000) / 60000);
            embed.addFields({
              name: `${emoji} ${a.artist_name}`,
              value: `> \`${a.listen_count}x\` • \`${artistHours}h ${artistMinutes}min\``,
              inline: true
            });
          });
        }

        if (stats.timeStats && stats.timeStats.length > 0) {
          const timeEmojis = { morning: '🌅', afternoon: '☀️', evening: '🌙' };
          const timeNames = { morning: 'matin', afternoon: 'après-midi', evening: 'soir' };
          const topTime = stats.timeStats[0];
          embed.addFields({
            name: '\u200b',
            value: `**⏰ Tu écoutes surtout le** ${timeEmojis[topTime.time_of_day]} **${timeNames[topTime.time_of_day]}** (${topTime.count} écoutes)`,
            inline: false
          });
        }

        embed.setTimestamp().setFooter({ text: '🎧 Wrapped Premium' });

        await interaction.editReply({ embeds: [embed] });
      } catch (error) {
        console.error('❌ Erreur wrapped:', error);
        await interaction.editReply('❌ Erreur lors de la génération du Wrapped.');
      }
    }

    if (sub === 'compare') {
      const a1 = options.getString('artist1');
      const a2 = options.getString('artist2');

      try {
        const artist1Result = await pool.query('SELECT * FROM spotify_artists WHERE artist_name ILIKE $1', [`%${a1}%`]);
        const artist2Result = await pool.query('SELECT * FROM spotify_artists WHERE artist_name ILIKE $1', [`%${a2}%`]);

        if (artist1Result.rows.length === 0 || artist2Result.rows.length === 0) {
          return interaction.reply('❌ Un ou plusieurs artistes introuvables.');
        }

        const artist1 = artist1Result.rows[0];
        const artist2 = artist2Result.rows[0];

        const hours1 = Math.floor(artist1.total_time / 3600000);
        const minutes1 = Math.round((artist1.total_time % 3600000) / 60000);
        const hours2 = Math.floor(artist2.total_time / 3600000);
        const minutes2 = Math.round((artist2.total_time % 3600000) / 60000);

        const embed = new EmbedBuilder()
          .setColor('#1DB954')
          .setTitle(`⚔️ ${artist1.artist_name} vs ${artist2.artist_name}`)
          .addFields(
            { name: artist1.artist_name, value: `\`\`\`yaml\n${artist1.listen_count} écoutes\n${hours1}h ${minutes1}min\n\`\`\``, inline: true },
            { name: 'VS', value: '\u200b', inline: true },
            { name: artist2.artist_name, value: `\`\`\`yaml\n${artist2.listen_count} écoutes\n${hours2}h ${minutes2}min\n\`\`\``, inline: true }
          )
          .setTimestamp();

        await interaction.reply({ embeds: [embed] });
      } catch (error) {
        console.error('❌ Erreur compare:', error);
        await interaction.reply('❌ Erreur lors de la comparaison.');
      }
    }
  }

  // ==================== DASHBOARD ====================
  if (commandName === 'dashboard') {
    await interaction.deferReply();

    try {
      const statsResult = await pool.query(`
        SELECT 
          COUNT(*) as total_tracks,
          SUM(listen_count) as total_listens,
          SUM(total_listen_time) as total_time
        FROM spotify_tracks
      `);
      const stats = statsResult.rows[0];

      const topTrackResult = await pool.query(`
        SELECT track_name, artist, listen_count
        FROM spotify_tracks
        ORDER BY listen_count DESC
        LIMIT 1
      `);
      const topTrack = topTrackResult.rows[0];

      const topArtistResult = await pool.query(`
        SELECT artist_name, listen_count
        FROM spotify_artists
        ORDER BY listen_count DESC
        LIMIT 1
      `);
      const topArtist = topArtistResult.rows[0];

      const achievementsResult = await pool.query('SELECT COUNT(*) as count FROM achievements');
      const achievementsCount = achievementsResult.rows[0].count;

      const hours = Math.floor((stats.total_time || 0) / 3600000);
      const minutes = Math.round(((stats.total_time || 0) % 3600000) / 60000);

      const embed = new EmbedBuilder()
        .setColor('#1DB954')
        .setAuthor({ name: '🎛️ Dashboard Global', iconURL: 'https://i.imgur.com/vFqjWF3.png' })
        .setDescription('> Vue d\'ensemble de ton activité musicale')
        .addFields(
          { name: '\u200b', value: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', inline: false },
          { name: '⏱️ Temps total', value: `\`${hours}h ${minutes}min\``, inline: true },
          { name: '🎵 Morceaux', value: `\`${stats.total_tracks || 0}\``, inline: true },
          { name: '🔁 Écoutes', value: `\`${stats.total_listens || 0}\``, inline: true },
          { name: '\u200b', value: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', inline: false }
        );

      if (topTrack) {
        embed.addFields({
          name: '👑 Titre favori',
          value: `**${topTrack.track_name}**\n${topTrack.artist} • \`${topTrack.listen_count}x\``,
          inline: true
        });
      }

      if (topArtist) {
        embed.addFields({
          name: '🎤 Artiste favori',
          value: `**${topArtist.artist_name}**\n\`${topArtist.listen_count}x\``,
          inline: true
        });
      }

      embed.addFields(
        { name: '🏆 Paliers débloqués', value: `\`${achievementsCount}\``, inline: true },
        { name: '\u200b', value: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', inline: false }
      );

      embed.setTimestamp().setFooter({ text: '📊 Dashboard Premium' });

      await interaction.editReply({ embeds: [embed] });
    } catch (error) {
      console.error('❌ Erreur dashboard:', error);
      await interaction.editReply('❌ Erreur lors de la génération du dashboard.');
    }
  }

  // ==================== ACHIEVEMENTS ====================
  if (commandName === 'achievements') {
    const sub = options.getSubcommand();

    if (sub === 'list') {
      const embed = new EmbedBuilder()
        .setColor('#FFD700')
        .setAuthor({ name: '🏆 Liste des Paliers', iconURL: 'https://i.imgur.com/9fz2gQX.png' })
        .setDescription('> Débloquez tous ces paliers en écoutant de la musique !')
        .addFields(
          { name: '\u200b', value: '**⏱️ TEMPS D\'ÉCOUTE**', inline: false }
        );

      achievements.listening_time.forEach(a => {
        embed.addFields({
          name: `${a.emoji} ${a.title}`,
          value: `> ${a.desc}`,
          inline: true
        });
      });

      embed.addFields({ name: '\u200b', value: '**🎵 ÉCOUTES PAR TITRE**', inline: false });

      achievements.track_listens.forEach(a => {
        embed.addFields({
          name: `${a.emoji} ${a.title}`,
          value: `> ${a.desc}`,
          inline: true
        });
      });

      embed.addFields({ name: '\u200b', value: '**🎤 ÉCOUTES PAR ARTISTE**', inline: false });

      achievements.artist_listens.forEach(a => {
        embed.addFields({
          name: `${a.emoji} ${a.title}`,
          value: `> ${a.desc}`,
          inline: true
        });
      });

      embed.addFields({ name: '\u200b', value: '**📀 MORCEAUX UNIQUES**', inline: false });

      achievements.unique_tracks.forEach(a => {
        embed.addFields({
          name: `${a.emoji} ${a.title}`,
          value: `> ${a.desc}`,
          inline: true
        });
      });

      embed.setTimestamp().setFooter({ text: '🏆 Achievement System' });

      await interaction.reply({ embeds: [embed] });
    }

    if (sub === 'progress') {
      await interaction.deferReply();

      try {
        const unlockedResult = await pool.query('SELECT key FROM achievements');
        const unlocked = unlockedResult.rows.map(r => r.key);

        const totalTimeResult = await pool.query('SELECT SUM(total_listen_time) as total FROM spotify_tracks');
        const totalHours = Math.floor((totalTimeResult.rows[0]?.total || 0) / 3600000);

        const maxListensResult = await pool.query('SELECT MAX(listen_count) as max FROM spotify_tracks');
        const maxTrackListens = maxListensResult.rows[0]?.max || 0;

        const maxArtistResult = await pool.query('SELECT MAX(listen_count) as max FROM spotify_artists');
        const maxArtistListens = maxArtistResult.rows[0]?.max || 0;

        const uniqueTracksResult = await pool.query('SELECT COUNT(*) as count FROM spotify_tracks');
        const uniqueTracks = parseInt(uniqueTracksResult.rows[0]?.count || 0);

        const embed = new EmbedBuilder()
          .setColor('#FFD700')
          .setAuthor({ name: '📈 Progression des Paliers', iconURL: 'https://i.imgur.com/9fz2gQX.png' })
          .setDescription('> Voici ta progression vers les prochains paliers')
          .addFields(
            { name: '\u200b', value: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', inline: false },
            { name: '⏱️ Temps d\'écoute', value: `\`${totalHours}h\``, inline: true },
            { name: '🎵 Max écoutes/titre', value: `\`${maxTrackListens}x\``, inline: true },
            { name: '🎤 Max écoutes/artiste', value: `\`${maxArtistListens}x\``, inline: true },
            { name: '📀 Morceaux uniques', value: `\`${uniqueTracks}\``, inline: true },
            { name: '🏆 Paliers débloqués', value: `\`${unlocked.length}\``, inline: true },
            { name: '\u200b', value: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', inline: false }
          );

        // Prochain palier temps
        const nextTimeAchievement = achievements.listening_time.find(a => 
          totalHours < a.hours && !unlocked.includes(`listening_time_${a.hours}`)
        );
        if (nextTimeAchievement) {
          const progress = Math.round((totalHours / nextTimeAchievement.hours) * 100);
          embed.addFields({
            name: `⏱️ Prochain: ${nextTimeAchievement.emoji} ${nextTimeAchievement.title}`,
            value: `> ${progress}% (${totalHours}h / ${nextTimeAchievement.hours}h)`,
            inline: false
          });
        }

        // Prochain palier titre
        const nextTrackAchievement = achievements.track_listens.find(a => 
          maxTrackListens < a.count && !unlocked.includes(`track_listens_${a.count}`)
        );
        if (nextTrackAchievement) {
          const progress = Math.round((maxTrackListens / nextTrackAchievement.count) * 100);
          embed.addFields({
            name: `🎵 Prochain: ${nextTrackAchievement.emoji} ${nextTrackAchievement.title}`,
            value: `> ${progress}% (${maxTrackListens} / ${nextTrackAchievement.count} écoutes)`,
            inline: false
          });
        }

        embed.setTimestamp().setFooter({ text: '📈 Progress Tracker' });

        await interaction.editReply({ embeds: [embed] });
      } catch (error) {
        console.error('❌ Erreur progress:', error);
        await interaction.editReply('❌ Erreur lors de la récupération de la progression.');
      }
    }
  }

  // ==================== INSIGHTS ====================
  if (commandName === 'insights') {
    const sub = options.getSubcommand();

    if (sub === 'mood') {
      await interaction.deferReply();

      try {
        const popularityResult = await pool.query(`
          SELECT AVG(popularity) as avg_pop
          FROM spotify_tracks
        `);
        const avgPopularity = Math.round(popularityResult.rows[0]?.avg_pop || 0);

        const timeStatsResult = await pool.query(`
          SELECT time_of_day, COUNT(*) as count
          FROM spotify_listens
          GROUP BY time_of_day
          ORDER BY count DESC
        `);

        let mood = 'Équilibré';
        if (avgPopularity > 80) mood = 'Mainstream';
        else if (avgPopularity < 40) mood = 'Underground';

        const embed = new EmbedBuilder()
          .setColor('#9B59B6')
          .setTitle('🎭 Analyse de tes humeurs musicales')
          .setDescription('> Découvre ton profil d\'écoute')
          .addFields(
            { name: '🎵 Profil musical', value: `\`${mood}\``, inline: true },
            { name: '🔥 Popularité moyenne', value: `\`${avgPopularity}/100\``, inline: true },
            { name: '\u200b', value: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', inline: false }
          );

        if (timeStatsResult.rows.length > 0) {
          const timeEmojis = { morning: '🌅', afternoon: '☀️', evening: '🌙' };
          const timeNames = { morning: 'Matin', afternoon: 'Après-midi', evening: 'Soir' };
          
          embed.addFields({
            name: '⏰ Moments préférés',
            value: timeStatsResult.rows.map(t => 
              `${timeEmojis[t.time_of_day]} ${timeNames[t.time_of_day]}: \`${t.count} écoutes\``
            ).join('\n'),
            inline: false
          });
        }

        embed.setTimestamp().setFooter({ text: '🎭 Mood Analytics' });

        await interaction.editReply({ embeds: [embed] });
      } catch (error) {
        console.error('❌ Erreur mood:', error);
        await interaction.editReply('❌ Erreur lors de l\'analyse.');
      }
    }

    if (sub === 'discovery') {
      await interaction.deferReply();

      try {
        const last30DaysResult = await pool.query(`
          SELECT COUNT(DISTINCT track_id) as new_tracks
          FROM spotify_listens
          WHERE listened_at >= NOW() - INTERVAL '30 days'
        `);
        const newTracks = parseInt(last30DaysResult.rows[0]?.new_tracks || 0);

        const totalResult = await pool.query('SELECT COUNT(*) as total FROM spotify_tracks');
        const totalTracks = parseInt(totalResult.rows[0]?.total || 1);

        const discoveryRate = Math.round((newTracks / totalTracks) * 100);

        let status = 'Explorateur';
        if (discoveryRate > 50) status = 'Grand Explorateur 🌟';
        else if (discoveryRate > 30) status = 'Explorateur Actif 🔍';
        else if (discoveryRate < 10) status = 'Fidèle aux classiques 📻';

        const embed = new EmbedBuilder()
          .setColor('#3498DB')
          .setTitle('🔍 Taux de découverte')
          .setDescription('> Analyse de ton exploration musicale')
          .addFields(
            { name: '📊 Taux de découverte', value: `\`${discoveryRate}%\``, inline: true },
            { name: '🆕 Nouveaux titres (30j)', value: `\`${newTracks}\``, inline: true },
            { name: '📀 Bibliothèque totale', value: `\`${totalTracks}\``, inline: true },
            { name: '\u200b', value: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', inline: false },
            { name: '🎯 Statut', value: `**${status}**`, inline: false }
          )
          .setTimestamp()
          .setFooter({ text: '🔍 Discovery Analytics' });

        await interaction.editReply({ embeds: [embed] });
      } catch (error) {
        console.error('❌ Erreur discovery:', error);
        await interaction.editReply('❌ Erreur lors de l\'analyse.');
      }
    }

    if (sub === 'habits') {
      await interaction.deferReply();

      try {
        const dayStatsResult = await pool.query(`
          SELECT day_of_week, COUNT(*) as count
          FROM spotify_listens
          GROUP BY day_of_week
          ORDER BY count DESC
        `);

        const avgDailyResult = await pool.query(`
          SELECT AVG(tracks_played) as avg
          FROM daily_stats
        `);
        const avgDaily = Math.round(avgDailyResult.rows[0]?.avg || 0);

        const completionResult = await pool.query(`
          SELECT 
            COUNT(CASE WHEN completed = TRUE THEN 1 END) as completed,
            COUNT(*) as total
          FROM spotify_listens
        `);
        const completionRate = Math.round((completionResult.rows[0].completed / completionResult.rows[0].total) * 100);

        const embed = new EmbedBuilder()
          .setColor('#E74C3C')
          .setTitle('📊 Tes habitudes d\'écoute')
          .setDescription('> Analyse comportementale musicale')
          .addFields(
            { name: '🎵 Moyenne quotidienne', value: `\`${avgDaily} titres/jour\``, inline: true },
            { name: '✅ Taux de complétion', value: `\`${completionRate}%\``, inline: true },
            { name: '\u200b', value: '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━', inline: false }
          );

        if (dayStatsResult.rows.length > 0) {
          const dayNames = {
            monday: 'Lundi', tuesday: 'Mardi', wednesday: 'Mercredi',
            thursday: 'Jeudi', friday: 'Vendredi', saturday: 'Samedi', sunday: 'Dimanche'
          };
          const topDay = dayStatsResult.rows[0];
          
          embed.addFields({
            name: '📅 Jours préférés',
            value: dayStatsResult.rows.slice(0, 3).map((d, i) => 
              `${i === 0 ? '🥇' : i === 1 ? '🥈' : '🥉'} ${dayNames[d.day_of_week]}: \`${d.count} écoutes\``
            ).join('\n'),
            inline: false
          });
        }

        embed.setTimestamp().setFooter({ text: '📊 Habits Analytics' });

        await interaction.editReply({ embeds: [embed] });
      } catch (error) {
        console.error('❌ Erreur habits:', error);
        await interaction.editReply('❌ Erreur lors de l\'analyse.');
      }
    }
  }
});

// ==================== SERVEUR WEB ====================
const keepAlive = require('./keep-alive');
keepAlive();

// ==================== GESTION DES ERREURS GLOBALES ====================

// Erreurs non capturées
process.on('unhandledRejection', (error) => {
  console.error('❌ Unhandled Rejection:', error);
});

process.on('uncaughtException', (error) => {
  console.error('❌ Uncaught Exception:', error);
});

// Gestion de l'arrêt propre
process.on('SIGINT', async () => {
  console.log('\n🛑 Arrêt du bot...');
  
  // Sauvegarder la dernière track si nécessaire
  if (lastSpotifyTrack && trackStartTime) {
    const listenDuration = Date.now() - trackStartTime;
    const completed = listenDuration >= (lastSpotifyTrack.duration * 0.8);
    await saveSpotifyTrack(lastSpotifyTrack, completed);
  }
  
  await pool.end();
  client.destroy();
  process.exit(0);
});

// ==================== LOGIN ====================

console.log('🚀 Démarrage du bot...');

// Vérifier les credentials avant de démarrer
if (!config.discordToken) {
  console.error('❌ DISCORD_TOKEN manquant dans les variables d\'environnement');
  process.exit(1);
}

if (!config.spotifyClientId || !config.spotifyClientSecret || !config.spotifyRefreshToken) {
  console.warn('⚠️ Credentials Spotify manquantes. Le tracking ne fonctionnera pas.');
}

client.login(config.discordToken).then(() => {
  console.log('🤖 Connexion Discord OK');
}).catch(err => {
  console.error('❌ Erreur connexion Discord:', err);
});