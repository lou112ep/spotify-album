import requests
import base64
import json
import time
import os

class SpotifyClient:
    """
    Un client per l'API di Spotify che gestisce automaticamente
    l'autenticazione e il rinnovo del token.
    """
    def __init__(self, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        self.access_token = None
        self.token_expiration_time = 0

    def _get_new_token(self):
        """Ottiene un nuovo token di accesso da Spotify."""
        auth_url = 'https://accounts.spotify.com/api/token'
        auth_header = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode('utf-8')).decode('utf-8')
        headers = {'Authorization': f'Basic {auth_header}'}
        data = {'grant_type': 'client_credentials'}
        
        try:
            response = requests.post(auth_url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            token_info = response.json()
            self.access_token = token_info.get('access_token')
            # Token scade dopo 3600s, lo rinnoviamo dopo 3500 per sicurezza
            self.token_expiration_time = time.time() + 3500 
            print(">>> Token Spotify rinnovato con successo. <<<")
            return True
        except requests.exceptions.RequestException as e:
            print(f"ERRORE CRITICO: Impossibile ottenere il token da Spotify: {e}")
            self.access_token = None
            return False

    def _ensure_token(self):
        """Assicura di avere un token valido, altrimenti ne richiede uno nuovo."""
        if not self.access_token or time.time() > self.token_expiration_time:
            return self._get_new_token()
        return True

    def _make_request(self, url, params=None, headers=None):
        """
        Esegue una richiesta GET all'API di Spotify, gestendo il token.
        """
        if not self._ensure_token():
            return None # Fallisce se non si può ottenere il token

        request_headers = {'Authorization': f'Bearer {self.access_token}'}
        if headers:
            request_headers.update(headers)

        try:
            response = requests.get(url, headers=request_headers, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            # Se l'errore è 401, il token potrebbe essere stato invalidato esternamente.
            # Forziamo un rinnovo al prossimo tentativo.
            if e.response and e.response.status_code == 401:
                print(">>> Errore 401 rilevato. Il token potrebbe essere scaduto. Forzo il rinnovo. <<<")
                self.access_token = None
            else:
                 print(f"Errore durante la richiesta API a {url}: {e}")
            return None

    def search_artist(self, artist_name):
        """Cerca un artista per nome."""
        search_url = 'https://api.spotify.com/v1/search'
        params = {'q': artist_name, 'type': 'artist', 'market': 'IT', 'limit': 1}
        data = self._make_request(search_url, params=params)
        if data and data.get('artists', {}).get('items'):
            return data['artists']['items'][0]
        return None

    def get_artist_albums(self, artist_id):
        """Recupera tutti gli album di un artista."""
        albums = []
        url = f'https://api.spotify.com/v1/artists/{artist_id}/albums'
        params = {'include_groups': 'album,single', 'market': 'IT', 'limit': 50}
        while url:
            page = self._make_request(url, params=params)
            if not page:
                break
            albums.extend(page.get('items', []))
            url = page.get('next')
            params = {} # I parametri sono già nell'URL 'next'
        return albums

    def get_album_tracks(self, album_id):
        """Recupera tutte le tracce di un album."""
        tracks = []
        url = f'https://api.spotify.com/v1/albums/{album_id}/tracks'
        params = {'market': 'IT', 'limit': 50, 'fields': 'items(name,popularity,id,external_urls.spotify),next'}
        while url:
            page = self._make_request(url, params=params)
            if not page:
                break
            tracks.extend(page.get('items', []))
            url = page.get('next')
            params = {}
        return tracks
    
    def get_related_artists(self, artist_id):
        """Ottiene gli artisti correlati da Spotify."""
        url = f'https://api.spotify.com/v1/artists/{artist_id}/related-artists'
        data = self._make_request(url)
        return data.get('artists', []) if data else []

    def get_playlist_track_artists(self, playlist_id):
        """Recupera gli artisti principali delle tracce di una playlist."""
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        params = {'fields': 'items(track(artists(id,name,popularity)))', 'limit': 50}
        data = self._make_request(url, params=params)
        artists = []
        if data:
            for item in data.get('items', []):
                track = item.get('track')
                if track and track.get('artists'):
                    artists.append(track['artists'][0])
        return artists

    def search_for_genre(self, genre):
        """Cerca artisti per un dato genere."""
        url = 'https://api.spotify.com/v1/search'
        params = {'q': f'genre:"{genre}"', 'type': 'artist', 'limit': 20}
        data = self._make_request(url, params=params)
        return data.get('artists', {}).get('items', []) if data else []
        
    def get_tracks_by_ids(self, track_ids):
        """Recupera i dettagli di più tracce in una sola chiamata."""
        url = f"https://api.spotify.com/v1/tracks?ids={','.join(track_ids)}"
        data = self._make_request(url)
        return data.get('tracks', []) if data else []
