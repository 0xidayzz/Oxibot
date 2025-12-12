// index.js - Bot Discord Premium pour tracker Spotify, YouTube, GitHub, Twitch
const { Client, GatewayIntentBits, EmbedBuilder, SlashCommandBuilder, REST, Routes, ActionRowBuilder, ButtonBuilder, ButtonStyle } = require('discord.js');
const express = require('express');
const sqlite3 = require('sqlite3').verbose();
const axios = require('axios');
const cron = require('node-cron');

// Configuration
const config = {
  discordToken: process.env.DISCORD_TOKEN,
  spotifyClientId: process.env.SPOTIFY_CLIENT_ID,
  spotifyClientSecret: process.env.SPOTIFY_CLIENT_SECRET,
  spotifyRefreshToken: process.env.SPOTIFY_REFRESH_TOKEN,
  youtubeApiKey: process.env.YOUTUBE_API_KEY,
  githubToken: process.env.GITHUB_TOKEN,
  githubUsername: process.env.GITHUB_USERNAME,
  twitchClientId: process.env.TWITCH_CLIENT_ID,
  twitchClientSecret: process.env.TWITCH_CLIENT_SECRET,
  twitchUsername: process.env.TWITCH_USERNAME
};

const client = new Client({
  intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages, GatewayIntentBits.MessageContent]
});

const db = new sqlite3.Database('./tracker.db');

// Initialisation de la base de données
db.serialize(() => {
  db.run(`CREATE TABLE IF NOT EXISTS spotify_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT, track_id TEXT UNIQUE, track_name TEXT, artist TEXT, album TEXT,
    album_cover TEXT, duration_ms INTEGER, listen_count INTEGER DEFAULT 1, total_listen_time INTEGER DEFAULT 0,
    skip_count INTEGER DEFAULT 0, completed_listens INTEGER DEFAULT 0, first_listened DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_listened DATETIME DEFAULT CURRENT_TIMESTAMP, spotify_url TEXT, preview_url TEXT, popularity INTEGER
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS spotify_listens (
    id INTEGER PRIMARY KEY AUTOINCREMENT, track_id TEXT, listened_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    duration_ms INTEGER, completed INTEGER DEFAULT 0, time_of_day TEXT, day_of_week TEXT
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS spotify_artists (
    id INTEGER PRIMARY KEY AUTOINCREMENT, artist_name TEXT UNIQUE, listen_count INTEGER DEFAULT 0,
    total_time INTEGER DEFAULT 0, genres TEXT, image_url TEXT
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS youtube_watch_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, video_id TEXT, title TEXT, channel_name TEXT, channel_id TEXT,
    duration INTEGER, watched_at DATETIME DEFAULT CURRENT_TIMESTAMP, thumbnail TEXT, category TEXT,
    view_count INTEGER, like_count INTEGER
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS youtube_subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id TEXT UNIQUE, channel_name TEXT, last_video_id TEXT,
    last_checked DATETIME DEFAULT CURRENT_TIMESTAMP, subscriber_count INTEGER, thumbnail TEXT,
    notification_enabled INTEGER DEFAULT 1
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS github_commits (
    id INTEGER PRIMARY KEY AUTOINCREMENT, repo_name TEXT, commit_hash TEXT UNIQUE, message TEXT,
    additions INTEGER, deletions INTEGER, committed_at DATETIME, branch TEXT
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS twitch_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, streamer_name TEXT, streamer_id TEXT, stream_title TEXT,
    category TEXT, duration INTEGER, watched_at DATETIME DEFAULT CURRENT_TIMESTAMP, viewer_count INTEGER, thumbnail TEXT
  )`);

  db.run(`CREATE TABLE IF NOT EXISTS discord_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT, guild_id TEXT UNIQUE, spotify_channel_id TEXT,
    youtube_channel_id TEXT, youtube_reco_channel_id TEXT, spotify_notifications INTEGER DEFAULT 1,
    youtube_notifications INTEGER DEFAULT 1
  )`);
});

let spotifyAccessToken = '';
let lastSpotifyTrack = null;
let trackStartTime = null;
let twitchAccessToken = '';

// ==================== SPOTIFY ====================

async function refreshSpotifyToken() {
  try {
    const response = await axios.post('https://accounts.spotify.com/api/token', 
      new URLSearchParams({grant_type: 'refresh_token', refresh_token: config.spotifyRefreshToken}), {
        headers: {
          'Authorization': 'Basic ' + Buffer.from(config.spotifyClientId + ':' + config.spotifyClientSecret).toString('base64'),
          'Content-Type': 'application/x-www-form-urlencoded'
        }
      }
    );
    spotifyAccessToken = response.data.access_token;
    console.log('✅ Spotify token refreshed');
  } catch (error) {
    console.error('❌ Erreur refresh Spotify token:', error.message);
  }
}

async function getCurrentSpotifyTrack() {
  try {
    const response = await axios.get('https://api.spotify.com/v1/me/player/currently-playing', {
      headers: { 'Authorization': `Bearer ${spotifyAccessToken}` }
    });

    if (response.data && response.data.is_playing) {
      const track = response.data.item;
      return {
        id: track.id, name: track.name, artist: track.artists.map(a => a.name).join(', '),
        artists: track.artists, album: track.album.name, albumCover: track.album.images[0]?.url,
        duration: track.duration_ms, progress: response.data.progress_ms, url: track.external_urls.spotify,
        previewUrl: track.preview_url, popularity: track.popularity
      };
    }
    return null;
  } catch (error) {
    if (error.response?.status === 401) await refreshSpotifyToken();
    return null;
  }
}

function saveSpotifyTrack(track, completed = false) {
  const now = new Date();
  const timeOfDay = now.getHours() < 12 ? 'morning' : now.getHours() < 18 ? 'afternoon' : 'evening';
  const dayOfWeek = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'][now.getDay()];

  db.run(`INSERT INTO spotify_tracks (track_id, track_name, artist, album, album_cover, duration_ms, 
    listen_count, total_listen_time, completed_listens, last_listened, spotify_url, preview_url, popularity)
    VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)
    ON CONFLICT(track_id) DO UPDATE SET listen_count = listen_count + 1,
      total_listen_time = total_listen_time + ?, completed_listens = completed_listens + ?, last_listened = CURRENT_TIMESTAMP`,
    [track.id, track.name, track.artist, track.album, track.albumCover, track.duration, 
     track.duration, completed ? 1 : 0, track.url, track.previewUrl, track.popularity, track.duration, completed ? 1 : 0]
  );

  db.run(`INSERT INTO spotify_listens (track_id, duration_ms, completed, time_of_day, day_of_week) VALUES (?, ?, ?, ?, ?)`,
    [track.id, track.duration, completed ? 1 : 0, timeOfDay, dayOfWeek]);

  for (const artist of track.artists) {
    db.run(`INSERT INTO spotify_artists (artist_name, listen_count, total_time) VALUES (?, 1, ?)
      ON CONFLICT(artist_name) DO UPDATE SET listen_count = listen_count + 1, total_time = total_time + ?`,
      [artist.name, track.duration, track.duration]);
  }
}

async function notifySpotifyTrack(track) {
  db.get(`SELECT spotify_channel_id, spotify_notifications FROM discord_config LIMIT 1`, async (err, row) => {
    if (row && row.spotify_channel_id && row.spotify_notifications) {
      const channel = await client.channels.fetch(row.spotify_channel_id);
      if (channel) {
        const embed = new EmbedBuilder()
          .setColor('#1DB954')
          .setAuthor({ name: '🎵 En écoute maintenant', iconURL: 'https://i.imgur.com/vFqjWF3.png' })
          .setTitle(track.name)
          .setDescription(`**${track.artist}**\n${track.album}`)
          .setThumbnail(track.albumCover)
          .addFields(
            { name: '⏱️ Durée', value: `${Math.floor(track.duration/60000)}:${String(Math.floor((track.duration%60000)/1000)).padStart(2, '0')}`, inline: true },
            { name: '🔥 Popularité', value: `${track.popularity}/100`, inline: true }
          )
          .setTimestamp()
          .setFooter({ text: 'Spotify Tracker' });

        const row = new ActionRowBuilder().addComponents(
          new ButtonBuilder().setLabel('Écouter sur Spotify').setURL(track.url).setStyle(ButtonStyle.Link).setEmoji('🎵')
        );
        channel.send({ embeds: [embed], components: [row] });
      }
    }
  });
}

async function generateSpotifyWrapped(period = 'all') {
  return new Promise((resolve) => {
    const stats = {};
    db.get(`SELECT COUNT(*) as total_tracks, SUM(listen_count) as total_listens, 
      SUM(total_listen_time) as total_time FROM spotify_tracks`, (err, general) => {
      stats.general = general;
      db.all(`SELECT track_name, artist, listen_count, album_cover FROM spotify_tracks 
        ORDER BY listen_count DESC LIMIT 5`, (err, topTracks) => {
        stats.topTracks = topTracks;
        db.all(`SELECT artist_name, listen_count, total_time FROM spotify_artists 
          ORDER BY listen_count DESC LIMIT 5`, (err, topArtists) => {
          stats.topArtists = topArtists;
          db.all(`SELECT time_of_day, COUNT(*) as count FROM spotify_listens 
            GROUP BY time_of_day ORDER BY count DESC`, (err, timeStats) => {
            stats.timeStats = timeStats;
            resolve(stats);
          });
        });
      });
    });
  });
}

// ==================== YOUTUBE ====================

async function checkYouTubeSubscriptions() {
  db.all(`SELECT * FROM youtube_subscriptions WHERE notification_enabled = 1`, async (err, subs) => {
    if (!subs) return;
    for (const sub of subs) {
      try {
        const response = await axios.get(`https://www.googleapis.com/youtube/v3/search`, {
          params: {key: config.youtubeApiKey, channelId: sub.channel_id, part: 'snippet', order: 'date', type: 'video', maxResults: 1}
        });
        if (response.data.items && response.data.items.length > 0) {
          const video = response.data.items[0];
          if (video.id.videoId !== sub.last_video_id) {
            const videoDetails = await getYouTubeVideoDetails(video.id.videoId);
            if (videoDetails) await notifyNewYouTubeVideo(videoDetails, sub.channel_name);
            db.run(`UPDATE youtube_subscriptions SET last_video_id = ?, last_checked = CURRENT_TIMESTAMP WHERE channel_id = ?`,
              [video.id.videoId, sub.channel_id]);
          }
        }
      } catch (error) {
        console.error('Erreur YouTube check:', error.message);
      }
    }
  });
}

async function getYouTubeVideoDetails(videoId) {
  try {
    const response = await axios.get('https://www.googleapis.com/youtube/v3/videos', {
      params: {key: config.youtubeApiKey, id: videoId, part: 'snippet,contentDetails,statistics'}
    });
    const video = response.data.items[0];
    return {
      id: videoId, title: video.snippet.title, channelName: video.snippet.channelTitle,
      channelId: video.snippet.channelId, thumbnail: video.snippet.thumbnails.high.url,
      viewCount: video.statistics.viewCount, likeCount: video.statistics.likeCount, publishedAt: video.snippet.publishedAt
    };
  } catch (error) {
    console.error('Erreur YouTube details:', error.message);
    return null;
  }
}

async function notifyNewYouTubeVideo(video, channelName) {
  db.get(`SELECT youtube_channel_id, youtube_notifications FROM discord_config LIMIT 1`, async (err, row) => {
    if (row && row.youtube_channel_id && row.youtube_notifications) {
      const channel = await client.channels.fetch(row.youtube_channel_id);
      if (channel) {
        const embed = new EmbedBuilder()
          .setColor('#FF0000')
          .setAuthor({ name: '📹 Nouvelle vidéo !', iconURL: 'https://i.imgur.com/qbNLfYk.png' })
          .setTitle(video.title)
          .setURL(`https://www.youtube.com/watch?v=${video.id}`)
          .setDescription(`**${channelName}** vient de publier une nouvelle vidéo !`)
          .setImage(video.thumbnail)
          .addFields(
            { name: '👁️ Vues', value: video.viewCount ? parseInt(video.viewCount).toLocaleString() : 'N/A', inline: true },
            { name: '👍 Likes', value: video.likeCount ? parseInt(video.likeCount).toLocaleString() : 'N/A', inline: true }
          )
          .setTimestamp(new Date(video.publishedAt))
          .setFooter({ text: 'YouTube Tracker' });

        const row = new ActionRowBuilder().addComponents(
          new ButtonBuilder().setLabel('Regarder').setURL(`https://www.youtube.com/watch?v=${video.id}`).setStyle(ButtonStyle.Link).setEmoji('▶️')
        );
        channel.send({ embeds: [embed], components: [row] });
      }
    }
  });
}

async function sendYouTubeRecommendations() {
  db.all(`SELECT channel_id, channel_name FROM youtube_subscriptions ORDER BY RANDOM() LIMIT 3`, async (err, channels) => {
    if (!channels) return;
    db.get(`SELECT youtube_reco_channel_id FROM discord_config LIMIT 1`, async (err, row) => {
      if (row && row.youtube_reco_channel_id) {
        const channel = await client.channels.fetch(row.youtube_reco_channel_id);
        if (channel) {
          const embed = new EmbedBuilder()
            .setColor('#FF0000')
            .setAuthor({ name: '🎬 Recommandations du soir', iconURL: 'https://i.imgur.com/qbNLfYk.png' })
            .setDescription('Voici 3 vidéos sélectionnées pour toi ce soir :')
            .setTimestamp()
            .setFooter({ text: 'Recommandations personnalisées' });

          for (const ch of channels) {
            try {
              const response = await axios.get(`https://www.googleapis.com/youtube/v3/search`, {
                params: {key: config.youtubeApiKey, channelId: ch.channel_id, part: 'snippet', order: 'date', type: 'video', maxResults: 1}
              });
              if (response.data.items && response.data.items.length > 0) {
                const video = response.data.items[0];
                embed.addFields({
                  name: `📺 ${ch.channel_name}`,
                  value: `[${video.snippet.title}](https://www.youtube.com/watch?v=${video.id.videoId})`
                });
              }
            } catch (error) {
              console.error('Erreur YouTube reco:', error.message);
            }
          }
          channel.send({ embeds: [embed] });
        }
      }
    });
  });
}

// ==================== GITHUB ====================

async function checkGitHubActivity() {
  try {
    const response = await axios.get(`https://api.github.com/users/${config.githubUsername}/events`, {
      headers: { 'Authorization': `token ${config.githubToken}` }
    });
    for (const event of response.data) {
      if (event.type === 'PushEvent') {
        for (const commit of event.payload.commits) {
          db.run(`INSERT OR IGNORE INTO github_commits (repo_name, commit_hash, message, additions, deletions, committed_at, branch)
            VALUES (?, ?, ?, 0, 0, ?, ?)`, [event.repo.name, commit.sha, commit.message, event.created_at, event.payload.ref]);
        }
      }
    }
  } catch (error) {
    console.error('Erreur GitHub check:', error.message);
  }
}

// ==================== TWITCH ====================

async function refreshTwitchToken() {
  try {
    const response = await axios.post('https://id.twitch.tv/oauth2/token', null, {
      params: {client_id: config.twitchClientId, client_secret: config.twitchClientSecret, grant_type: 'client_credentials'}
    });
    twitchAccessToken = response.data.access_token;
    console.log('✅ Twitch token refreshed');
  } catch (error) {
    console.error('❌ Erreur refresh Twitch token:', error.message);
  }
}

// ==================== COMMANDES ====================

const commands = [
  new SlashCommandBuilder().setName('spotify').setDescription('Commandes Spotify')
    .addSubcommand(sub => sub.setName('channel').setDescription('Configure le channel'))
    .addSubcommand(sub => sub.setName('toggle').setDescription('Toggle notifications'))
    .addSubcommand(sub => sub.setName('top').setDescription('Top 10'))
    .addSubcommand(sub => sub.setName('search').setDescription('Rechercher').addStringOption(opt => opt.setName('query').setDescription('Recherche').setRequired(true)))
    .addSubcommand(sub => sub.setName('stats').setDescription('Stats'))
    .addSubcommand(sub => sub.setName('wrapped').setDescription('Wrapped').addStringOption(opt => opt.setName('period').setDescription('Période').addChoices(
      { name: 'Semaine', value: 'week' }, { name: 'Mois', value: 'month' }, { name: 'Tout', value: 'all' })))
    .addSubcommand(sub => sub.setName('current').setDescription('Musique actuelle'))
    .addSubcommand(sub => sub.setName('compare').setDescription('Comparer artistes')
      .addStringOption(opt => opt.setName('artist1').setDescription('Artiste 1').setRequired(true))
      .addStringOption(opt => opt.setName('artist2').setDescription('Artiste 2').setRequired(true))),

  new SlashCommandBuilder().setName('youtube').setDescription('Commandes YouTube')
    .addSubcommand(sub => sub.setName('time').setDescription('Temps de visionnage'))
    .addSubcommand(sub => sub.setName('channel').setDescription('Configure le channel'))
    .addSubcommand(sub => sub.setName('toggle').setDescription('Toggle notifications'))
    .addSubcommand(sub => sub.setName('reco').setDescription('Recommandations'))
    .addSubcommand(sub => sub.setName('stats').setDescription('Stats'))
    .addSubcommand(sub => sub.setName('add-sub').setDescription('Ajouter abonnement').addStringOption(opt => opt.setName('channel_id').setDescription('ID chaîne').setRequired(true)))
    .addSubcommand(sub => sub.setName('list-subs').setDescription('Liste abonnements')),

  new SlashCommandBuilder().setName('github').setDescription('Commandes GitHub')
    .addSubcommand(sub => sub.setName('activity').setDescription('Activité'))
    .addSubcommand(sub => sub.setName('stats').setDescription('Stats'))
    .addSubcommand(sub => sub.setName('streak').setDescription('Streak')),

  new SlashCommandBuilder().setName('twitch').setDescription('Commandes Twitch')
    .addSubcommand(sub => sub.setName('time').setDescription('Temps'))
    .addSubcommand(sub => sub.setName('top').setDescription('Top'))
    .addSubcommand(sub => sub.setName('stats').setDescription('Stats')),

  new SlashCommandBuilder().setName('dashboard').setDescription('Dashboard global')
].map(cmd => cmd.toJSON());

// ==================== BOT START ====================

client.once('ready', async () => {
  console.log(`✅ Bot connecté: ${client.user.tag}`);
  const rest = new REST({ version: '10' }).setToken(config.discordToken);
  try {
    await rest.put(Routes.applicationCommands(client.user.id), { body: commands });
    console.log('✅ Commandes enregistrées');
  } catch (error) {
    console.error('❌ Erreur commandes:', error);
  }

  await refreshSpotifyToken();
  await refreshTwitchToken();

  setInterval(async () => {
    const track = await getCurrentSpotifyTrack();
    if (track) {
      if (!lastSpotifyTrack || lastSpotifyTrack.id !== track.id) {
        if (lastSpotifyTrack && trackStartTime) {
          const listenDuration = Date.now() - trackStartTime;
          const completed = listenDuration >= (lastSpotifyTrack.duration * 0.8);
          saveSpotifyTrack(lastSpotifyTrack, completed);
        }
        await notifySpotifyTrack(track);
        lastSpotifyTrack = track;
        trackStartTime = Date.now();
      }
    } else if (lastSpotifyTrack && trackStartTime) {
      const listenDuration = Date.now() - trackStartTime;
      const completed = listenDuration >= (lastSpotifyTrack.duration * 0.8);
      saveSpotifyTrack(lastSpotifyTrack, completed);
      lastSpotifyTrack = null;
      trackStartTime = null;
    }
  }, 30000);

  setInterval(checkYouTubeSubscriptions, 3600000);
  setInterval(checkGitHubActivity, 300000);
  cron.schedule('0 20 * * *', sendYouTubeRecommendations, { timezone: 'Europe/Paris' });
  setInterval(refreshSpotifyToken, 3000000);
  setInterval(refreshTwitchToken, 3000000);
});

// ==================== GESTION COMMANDES ====================

client.on('interactionCreate', async interaction => {
  if (!interaction.isChatInputCommand()) return;
  const { commandName, options } = interaction;

  if (commandName === 'spotify') {
    const sub = options.getSubcommand();
    
    if (sub === 'channel') {
      db.run(`INSERT INTO discord_config (guild_id, spotify_channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET spotify_channel_id = ?`,
        [interaction.guildId, interaction.channelId, interaction.channelId]);
      await interaction.reply('✅ Channel configuré pour Spotify !');
    }
    
    if (sub === 'toggle') {
      db.get(`SELECT spotify_notifications FROM discord_config WHERE guild_id = ?`, [interaction.guildId], (err, row) => {
        const newState = row ? !row.spotify_notifications : 1;
        db.run(`INSERT INTO discord_config (guild_id, spotify_notifications) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET spotify_notifications = ?`,
          [interaction.guildId, newState, newState]);
        interaction.reply(`🔔 Notifications ${newState ? 'ON' : 'OFF'} !`);
      });
    }
    
    if (sub === 'current') {
      const track = await getCurrentSpotifyTrack();
      if (!track) return interaction.reply('❌ Aucune musique en cours.');
      const embed = new EmbedBuilder()
        .setColor('#1DB954').setTitle('🎵 En écoute').setDescription(`**${track.name}**\n${track.artist}`)
        .setThumbnail(track.albumCover)
        .addFields(
          { name: 'Album', value: track.album, inline: true },
          { name: 'Progress', value: `${Math.floor(track.progress/1000)}s / ${Math.floor(track.duration/1000)}s`, inline: true }
        );
      interaction.reply({ embeds: [embed] });
    }
    
    if (sub === 'top') {
      db.all(`SELECT track_name, artist, listen_count, album_cover FROM spotify_tracks ORDER BY listen_count DESC LIMIT 10`, (err, tracks) => {
        if (!tracks || tracks.length === 0) return interaction.reply('Aucune donnée.');
        const embed = new EmbedBuilder().setColor('#1DB954').setTitle('🎵 Top 10 Musiques')
          .setDescription(tracks.map((t, i) => `**${i+1}.** ${t.track_name} - ${t.artist} (${t.listen_count}x)`).join('\n'));
        interaction.reply({ embeds: [embed] });
      });
      db.all(`SELECT artist_name, SUM(listen_count) as total FROM spotify_artists GROUP BY artist_name ORDER BY total DESC LIMIT 10`, (err, artists) => {
        if (artists && artists.length > 0) {
          const embed = new EmbedBuilder().setColor('#1DB954').setTitle('🎤 Top 10 Artistes')
            .setDescription(artists.map((a, i) => `**${i+1}.** ${a.artist_name} (${a.total}x)`).join('\n'));
          interaction.followUp({ embeds: [embed] });
        }
      });
    }
    
    if (sub === 'search') {
      const query = options.getString('query');
      db.all(`SELECT * FROM spotify_tracks WHERE track_name LIKE ? OR artist LIKE ? ORDER BY listen_count DESC LIMIT 5`,
        [`%${query}%`, `%${query}%`], (err, tracks) => {
          if (!tracks || tracks.length === 0) return interaction.reply(`Aucun résultat pour "${query}"`);
          const embed = new EmbedBuilder().setColor('#1DB954').setTitle(`🔍 Résultats: "${query}"`)
            .setDescription(tracks.map(t => `**${t.track_name}** - ${t.artist}\n${t.listen_count}x | ${Math.round(t.total_listen_time/60000)}min`).join('\n\n'));
          interaction.reply({ embeds: [embed] });
        });
    }
    
    if (sub === 'stats') {
      db.get(`SELECT COUNT(*) as total_tracks, SUM(listen_count) as total_listens, SUM(total_listen_time) as total_time FROM spotify_tracks`, (err, stats) => {
        if (!stats) return interaction.reply('Aucune donnée.');
        const hours = Math.round(stats.total_time / 3600000);
        const minutes = Math.round((stats.total_time % 3600000) / 60000);
        const embed = new EmbedBuilder().setColor('#1DB954').setTitle('📊 Stats Spotify')
          .addFields(
            { name: 'Morceaux', value: `${stats.total_tracks}`, inline: true },
            { name: 'Écoutes', value: `${stats.total_listens}`, inline: true },
            { name: 'Temps', value: `${hours}h ${minutes}m`, inline: true }
          );
        interaction.reply({ embeds: [embed] });
      });
    }
    
    if (sub === 'wrapped') {
      const period = options.getString('period') || 'all';
      const stats = await generateSpotifyWrapped(period);
      const hours = Math.round(stats.general.total_time / 3600000);
      const embed = new EmbedBuilder().setColor('#1DB954').setTitle(`🎊 Spotify Wrapped - ${period === 'week' ? 'Semaine' : period === 'month' ? 'Mois' : 'Total'}`)
        .addFields({ name: '⏱️ Temps total', value: `${hours}h` })
        .addFields({ name: '🎵 Top 5 Morceaux', value: stats.topTracks.map((t, i) => `${i+1}. ${t.track_name} - ${t.artist}`).join('\n') })
        .addFields({ name: '🎤 Top 5 Artistes', value: stats.topArtists.map((a, i) => `${i+1}. ${a.artist_name}`).join('\n') });
      interaction.reply({ embeds: [embed] });
    }
    
    if (sub === 'compare') {
      const a1 = options.getString('artist1');
      const a2 = options.getString('artist2');
      db.get(`SELECT * FROM spotify_artists WHERE artist_name LIKE ?`, [`%${a1}%`], (err, artist1) => {
        db.get(`SELECT * FROM spotify_artists WHERE artist_name LIKE ?`, [`%${a2}%`], (err, artist2) => {
          if (!artist1 || !artist2) return interaction.reply('Artiste(s) introuvable(s).');
          const embed = new EmbedBuilder().setColor('#1DB954').setTitle(`⚔️ ${artist1.artist_name} vs ${artist2.artist_name}`)
            .addFields(
              { name: artist1.artist_name, value: `${artist1.listen_count} écoutes\n${Math.round(artist1.total_time/60000)} min`, inline: true },
              { name: artist2.artist_name, value: `${artist2.listen_count} écoutes\n${Math.round(artist2.total_time/60000)} min`, inline: true }
            );
          interaction.reply({ embeds: [embed] });
        });
      });
    }
  }

  if (commandName === 'youtube') {
    const sub = options.getSubcommand();
    
    if (sub === 'channel') {
      db.run(`INSERT INTO discord_config (guild_id, youtube_channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET youtube_channel_id = ?`,
        [interaction.guildId, interaction.channelId, interaction.channelId]);
      await interaction.reply('✅ Channel configuré pour YouTube !');
    }
    
    if (sub === 'toggle') {
      db.get(`SELECT youtube_notifications FROM discord_config WHERE guild_id = ?`, [interaction.guildId], (err, row) => {
        const newState = row ? !row.youtube_notifications : 1;
        db.run(`INSERT INTO discord_config (guild_id, youtube_notifications) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET youtube_notifications = ?`,
          [interaction.guildId, newState, newState]);
        interaction.reply(`🔔 Notifications YouTube ${newState ? 'ON' : 'OFF'} !`);
      });
    }
    
    if (sub === 'time') {
      db.get(`SELECT SUM(duration) as total FROM youtube_watch_history`, (err, result) => {
        const hours = Math.floor((result?.total || 0) / 3600);
        const minutes = Math.floor(((result?.total || 0) % 3600) / 60);
        const embed = new EmbedBuilder().setColor('#FF0000').setTitle('⏱️ Temps YouTube')
          .setDescription(`**${hours}h ${minutes}m** au total`);
        interaction.reply({ embeds: [embed] });
      });
    }
    
    if (sub === 'reco') {
      await sendYouTubeRecommendations();
      await interaction.reply('✅ Recommandations envoyées !');
    }
    
    if (sub === 'stats') {
      db.all(`SELECT channel_name, COUNT(*) as count, SUM(duration) as time FROM youtube_watch_history GROUP BY channel_name ORDER BY count DESC LIMIT 5`, (err, channels) => {
        if (!channels || channels.length === 0) return interaction.reply('Aucune donnée YouTube.');
        const embed = new EmbedBuilder().setColor('#FF0000').setTitle('📊 Stats YouTube')
          .setDescription(channels.map(c => `**${c.channel_name}**: ${c.count} vidéos, ${Math.floor(c.time/60)}min`).join('\n'));
        interaction.reply({ embeds: [embed] });
      });
    }
    
    if (sub === 'add-sub') {
      const channelId = options.getString('channel_id');
      try {
        const response = await axios.get('https://www.googleapis.com/youtube/v3/channels', {
          params: {key: config.youtubeApiKey, id: channelId, part: 'snippet'}
        });
        if (response.data.items && response.data.items.length > 0) {
          const channel = response.data.items[0];
          db.run(`INSERT INTO youtube_subscriptions (channel_id, channel_name, thumbnail) VALUES (?, ?, ?) ON CONFLICT(channel_id) DO NOTHING`,
            [channelId, channel.snippet.title, channel.snippet.thumbnails.default.url]);
          await interaction.reply(`✅ Abonnement ajouté: **${channel.snippet.title}**`);
        } else {
          await interaction.reply('❌ Chaîne introuvable.');
        }
      } catch (error) {
        await interaction.reply('❌ Erreur lors de l\'ajout.');
      }
    }
    
    if (sub === 'list-subs') {
      db.all(`SELECT channel_name, notification_enabled FROM youtube_subscriptions`, (err, subs) => {
        if (!subs || subs.length === 0) return interaction.reply('Aucun abonnement.');
        const embed = new EmbedBuilder().setColor('#FF0000').setTitle('📺 Abonnements YouTube')
          .setDescription(subs.map(s => `${s.notification_enabled ? '🔔' : '🔕'} ${s.channel_name}`).join('\n'));
        interaction.reply({ embeds: [embed] });
      });
    }
  }

  if (commandName === 'github') {
    const sub = options.getSubcommand();
    
    if (sub === 'activity') {
      db.all(`SELECT * FROM github_commits ORDER BY committed_at DESC LIMIT 10`, (err, commits) => {
        if (!commits || commits.length === 0) return interaction.reply('Aucune activité GitHub.');
        const embed = new EmbedBuilder().setColor('#000000').setTitle('💻 Activité GitHub')
          .setDescription(commits.map(c => `**${c.repo_name}**\n${c.message.substring(0, 100)}\n\`${c.commit_hash.substring(0, 7)}\``).join('\n\n'));
        interaction.reply({ embeds: [embed] });
      });
    }
    
    if (sub === 'stats') {
      db.all(`SELECT repo_name, COUNT(*) as commits FROM github_commits GROUP BY repo_name ORDER BY commits DESC`, (err, repos) => {
        if (!repos || repos.length === 0) return interaction.reply('Aucune stat GitHub.');
        const embed = new EmbedBuilder().setColor('#000000').setTitle('📊 Stats GitHub')
          .setDescription(repos.map(r => `**${r.repo_name}**: ${r.commits} commits`).join('\n'));
        interaction.reply({ embeds: [embed] });
      });
    }
    
    if (sub === 'streak') {
      db.all(`SELECT DATE(committed_at) as date FROM github_commits ORDER BY committed_at DESC`, (err, commits) => {
        if (!commits || commits.length === 0) return interaction.reply('Aucune donnée.');
        let streak = 1;
        let maxStreak = 1;
        for (let i = 0; i < commits.length - 1; i++) {
          const current = new Date(commits[i].date);
          const next = new Date(commits[i + 1].date);
          const diff = Math.abs(current - next) / (1000 * 60 * 60 * 24);
          if (diff <= 1) {
            streak++;
            maxStreak = Math.max(maxStreak, streak);
          } else {
            streak = 1;
          }
        }
        const embed = new EmbedBuilder().setColor('#000000').setTitle('🔥 Streak GitHub')
          .addFields(
            { name: 'Streak actuel', value: `${streak} jours`, inline: true },
            { name: 'Meilleur streak', value: `${maxStreak} jours`, inline: true }
          );
        interaction.reply({ embeds: [embed] });
      });
    }
  }

  if (commandName === 'twitch') {
    const sub = options.getSubcommand();
    
    if (sub === 'time') {
      db.all(`SELECT streamer_name, SUM(duration) as total FROM twitch_sessions GROUP BY streamer_name ORDER BY total DESC`, (err, streamers) => {
        if (!streamers || streamers.length === 0) return interaction.reply('Aucune donnée Twitch.');
        const embed = new EmbedBuilder().setColor('#9146FF').setTitle('⏱️ Temps Twitch')
          .setDescription(streamers.map(s => `**${s.streamer_name}**: ${Math.round(s.total/60)} min`).join('\n'));
        interaction.reply({ embeds: [embed] });
      });
    }
    
    if (sub === 'top') {
      db.all(`SELECT streamer_name, COUNT(*) as sessions, SUM(duration) as total FROM twitch_sessions GROUP BY streamer_name ORDER BY total DESC LIMIT 10`, (err, streamers) => {
        if (!streamers || streamers.length === 0) return interaction.reply('Aucune donnée Twitch.');
        const embed = new EmbedBuilder().setColor('#9146FF').setTitle('🏆 Top Streamers')
          .setDescription(streamers.map((s, i) => `**${i+1}.** ${s.streamer_name} - ${Math.round(s.total/60)}min (${s.sessions} sessions)`).join('\n'));
        interaction.reply({ embeds: [embed] });
      });
    }
    
    if (sub === 'stats') {
      db.get(`SELECT COUNT(*) as sessions, SUM(duration) as total FROM twitch_sessions`, (err, stats) => {
        if (!stats) return interaction.reply('Aucune donnée.');
        const hours = Math.floor(stats.total / 60);
        const embed = new EmbedBuilder().setColor('#9146FF').setTitle('📊 Stats Twitch')
          .addFields(
            { name: 'Sessions', value: `${stats.sessions}`, inline: true },
            { name: 'Temps total', value: `${hours}h`, inline: true },
            { name: 'Moyenne/session', value: `${Math.round(stats.total/stats.sessions)}min`, inline: true }
          );
        interaction.reply({ embeds: [embed] });
      });
    }
  }

  if (commandName === 'dashboard') {
    const dashData = {};
    
    db.get(`SELECT SUM(total_listen_time) as time FROM spotify_tracks`, (err, spotify) => {
      dashData.spotify = spotify;
      db.get(`SELECT artist_name FROM spotify_artists ORDER BY listen_count DESC LIMIT 1`, (err, topArtist) => {
        dashData.topArtist = topArtist;
        db.get(`SELECT SUM(duration) as time FROM youtube_watch_history`, (err, youtube) => {
          dashData.youtube = youtube;
          db.get(`SELECT COUNT(*) as commits FROM github_commits`, (err, github) => {
            dashData.github = github;
            db.get(`SELECT SUM(duration) as time FROM twitch_sessions`, (err, twitch) => {
              dashData.twitch = twitch;
              
              const spotifyHours = Math.round((dashData.spotify?.time || 0) / 3600000);
              const youtubeHours = Math.floor((dashData.youtube?.time || 0) / 3600);
              const twitchHours = Math.floor((dashData.twitch?.time || 0) / 60);
              
              const embed = new EmbedBuilder()
                .setColor('#5865F2')
                .setTitle('📊 Dashboard Global')
                .setDescription('Vue d\'ensemble de toutes tes activités')
                .addFields(
                  { name: '🎵 Spotify', value: `${spotifyHours}h d'écoute\nTop: ${dashData.topArtist?.artist_name || 'N/A'}`, inline: true },
                  { name: '📹 YouTube', value: `${youtubeHours}h de visionnage`, inline: true },
                  { name: '💻 GitHub', value: `${dashData.github?.commits || 0} commits`, inline: true },
                  { name: '🎮 Twitch', value: `${twitchHours}h de stream`, inline: true }
                )
                .setTimestamp()
                .setFooter({ text: 'Multi-Platform Tracker' });
              
              interaction.reply({ embeds: [embed] });
            });
          });
        });
      });
    });
  }
});

// ==================== SERVEUR WEB ====================

const app = express();
app.get('/', (req, res) => res.send('🤖 Bot Discord en ligne !'));
app.listen(3000, () => console.log('✅ Serveur web sur port 3000'));

client.login(config.discordToken);