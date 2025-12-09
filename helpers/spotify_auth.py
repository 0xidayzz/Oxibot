# helpers/spotify_auth.py
import os
import requests
import spotipy
import time # Ajout pour gérer le timing du refresh

class SpotifyClient:
    """Gère l'authentification et les appels à l'API Spotify."""
    
    def __init__(self):
        self.CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
        self.CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
        self.REFRESH_TOKEN = os.getenv('SPOTIFY_REFRESH_TOKEN')
        self.USER_ID = os.getenv('SPOTIFY_USER_ID')
        self.access_token = None
        self.token_expiry_time = 0
        self.sp = None
        self._refresh_access_token()
        self.sp = spotipy.Spotify(auth=self.access_token)

    def _refresh_access_token(self):
        """Utilise le Refresh Token pour obtenir un nouvel Access Token."""
        
        # Pas besoin de rafraîchir si le token est encore valide
        if self.access_token and time.time() < self.token_expiry_time - 60:
            return

        if not self.REFRESH_TOKEN:
            print("ERREUR: SPOTIFY_REFRESH_TOKEN est vide. Impossible de s'authentifier.")
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
            self.token_expiry_time = time.time() + token_info.get('expires_in', 3600)
            print("Nouveau Access Token Spotify obtenu.")
        else:
            print(f"Erreur de rafraîchissement du token Spotify. Statut: {response.status_code}")
            print(f"Réponse: {response.text}")
            self.access_token = None

    def get_currently_playing(self):
        """Récupère la piste actuellement jouée par l'utilisateur."""
        
        # Vérification et rafraîchissement automatique
        self._refresh_access_token()
        
        if not self.access_token:
            return None
        
        try:
            # Réutilise l'objet spotipy avec le token rafraîchi
            self.sp = spotipy.Spotify(auth=self.access_token) 
            data = self.sp.current_user_playing_track()
            return data
        except Exception as e:
            # Si l'API renvoie une erreur (token expiré ou autre), on force un refresh
            print(f"Erreur lors de la récupération de la piste actuelle: {e}")
            self.access_token = None # Invalide l'ancien token
            return None

# Initialisation globale pour être importée par les cogs
spotify_client = SpotifyClient()