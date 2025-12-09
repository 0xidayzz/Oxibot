import spotipy
from spotipy.oauth2 import SpotifyOAuth
import config

class SpotifyClient:
    def __init__(self):
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=config.SPOTIFY_CLIENT_ID,
            client_secret=config.SPOTIFY_CLIENT_SECRET,
            redirect_uri=config.SPOTIFY_REDIRECT_URI,
            scope=config.SPOTIFY_SCOPE
        ))
        self.current_track_id = None
    
    def get_current_track(self):
        """Récupère le titre en cours de lecture"""
        try:
            current = self.sp.current_playback()
            
            if current and current['is_playing']:
                track = current['item']
                
                track_data = {
                    'track_id': track['id'],
                    'track_name': track['name'],
                    'artist_name': ', '.join([artist['name'] for artist in track['artists']]),
                    'album_name': track['album']['name'],
                    'duration_ms': track['duration_ms'],
                    'image_url': track['album']['images'][0]['url'] if track['album']['images'] else None,
                    'progress_ms': current['progress_ms'],
                    'spotify_url': track['external_urls']['spotify']
                }
                
                return track_data
            
        except Exception as e:
            print(f"Erreur lors de la récupération du titre : {e}")
        
        return None
    
    def get_followed_artists(self):
        """Récupère la liste des artistes suivis"""
        try:
            results = self.sp.current_user_followed_artists(limit=50)
            artists = []
            
            for artist in results['artists']['items']:
                artists.append({
                    'artist_id': artist['id'],
                    'artist_name': artist['name']
                })
            
            return artists
        
        except Exception as e:
            print(f"Erreur lors de la récupération des artistes : {e}")
            return []
    
    def get_artist_latest_releases(self, artist_id, last_check_date):
        """Récupère les dernières sorties d'un artiste"""
        try:
            albums = self.sp.artist_albums(
                artist_id,
                album_type='album,single',
                limit=10
            )
            
            new_releases = []
            for album in albums['items']:
                release_date = album['release_date']
                
                # Vérifier si la sortie est nouvelle
                if release_date > last_check_date.strftime('%Y-%m-%d'):
                    new_releases.append({
                        'release_id': album['id'],
                        'artist_id': artist_id,
                        'release_name': album['name'],
                        'release_type': album['album_type'],
                        'release_date': release_date,
                        'image_url': album['images'][0]['url'] if album['images'] else None,
                        'spotify_url': album['external_urls']['spotify']
                    })
            
            return new_releases
        
        except Exception as e:
            print(f"Erreur lors de la récupération des sorties : {e}")
            return []
    
    def get_track_info(self, track_name=None, track_id=None):
        """Récupère les informations détaillées d'un titre"""
        try:
            if track_id:
                track = self.sp.track(track_id)
            elif track_name:
                results = self.sp.search(q=track_name, type='track', limit=1)
                if results['tracks']['items']:
                    track = results['tracks']['items'][0]
                else:
                    return None
            else:
                return None
            
            return {
                'track_id': track['id'],
                'track_name': track['name'],
                'artist_name': ', '.join([artist['name'] for artist in track['artists']]),
                'album_name': track['album']['name'],
                'duration_ms': track['duration_ms'],
                'image_url': track['album']['images'][0]['url'] if track['album']['images'] else None,
                'spotify_url': track['external_urls']['spotify'],
                'release_date': track['album']['release_date']
            }
        
        except Exception as e:
            print(f"Erreur lors de la récupération des infos : {e}")
            return None
    
    def get_artist_info(self, artist_name=None, artist_id=None):
        """Récupère les informations détaillées d'un artiste"""
        try:
            if artist_id:
                artist = self.sp.artist(artist_id)
            elif artist_name:
                results = self.sp.search(q=artist_name, type='artist', limit=1)
                if results['artists']['items']:
                    artist = results['artists']['items'][0]
                else:
                    return None
            else:
                return None
            
            return {
                'artist_id': artist['id'],
                'artist_name': artist['name'],
                'genres': ', '.join(artist['genres'][:3]) if artist['genres'] else 'N/A',
                'popularity': artist['popularity'],
                'followers': artist['followers']['total'],
                'image_url': artist['images'][0]['url'] if artist['images'] else None,
                'spotify_url': artist['external_urls']['spotify']
            }
        
        except Exception as e:
            print(f"Erreur lors de la récupération des infos artiste : {e}")
            return None