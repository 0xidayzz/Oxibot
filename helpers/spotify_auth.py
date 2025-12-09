# helpers/spotify_auth.py
import os
import requests
import json
from spotipy.oauth2 import SpotifyOAuth
import spotipy

class SpotifyClient:
    """Gère l'authentification et les appels à l'API Spotify."""
    
    def __init__(self):
        self.CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
        self.CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.REFRESH_TOKEN = os.getenv('SPOTIFY_REFRESH_TOKEN')
        self.USER_ID = os.getenv('SPOTIFY_USER_ID')
        self.access_token = None
        self.sp = None
        self._refresh_access_token()
        self.sp = spotipy.Spotify(auth=self.access_token)

    def _refresh_access_token(self):
        """Utilise le Refresh Token pour obtenir un nouvel Access Token."""
        if not self.REFRESH_TOKEN:
            print("ERREUR: SPOTIFY_REFRESH_TOKEN manquant. Veuillez l'obtenir manuellement.")
            return

        response = requests.post(
            'https://accounts.spotify.com/api/token',
            data={
                'grant_type': 'refresh_token',
                'refresh_token': self.REFRESH_TOKEN,
                'client_id': self.CLIENT_ID,
                'client_secret': self.CLIENT_SECRET
            }
        )
        
        if response.status_code == 200:
            token_info = response.json()
            self.access_token = token_info.get('access_token')
            print("Nouveau Access Token Spotify obtenu avec succès.")
        else:
            print(f"Erreur de rafraîchissement du token: {response.text}")
            self.access_token = None

    def get_currently_playing(self):
        """Récupère la piste actuellement jouée par l'utilisateur."""
        # On s'assure que le token est valide ou on le rafraîchit si besoin
        if not self.access_token:
             self._refresh_access_token()
        
        try:
            # Réutilise l'objet spotipy avec le token rafraîchi
            self.sp = spotipy.Spotify(auth=self.access_token) 
            data = self.sp.current_user_playing_track()
            return data
        except Exception as e:
            print(f"Erreur lors de la récupération de la piste actuelle: {e}")
            self._refresh_access_token() # Tenter de rafraîchir en cas d'erreur API
            return None

# Initialisation globale pour être importée par les cogs
spotify_client = SpotifyClient()