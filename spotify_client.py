import requests
import base64
import json
import time

# Funzione per ottenere il token di accesso da Spotify
def get_spotify_token(client_id, client_secret):
    """Ottiene un token di accesso da Spotify."""
    auth_url = 'https://accounts.spotify.com/api/token'
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode('utf-8')).decode('utf-8')
    headers = {'Authorization': f'Basic {auth_header}'}
    data = {'grant_type': 'client_credentials'}
    try:
        response = requests.post(auth_url, headers=headers, data=data, timeout=10)
        response.raise_for_status()
        token_info = response.json()
        return token_info.get('access_token')
    except requests.exceptions.RequestException as e:
        print(f"Errore durante l'ottenimento del token: {e}")
        return None
    except json.JSONDecodeError:
        print("Errore: Risposta non valida da Spotify durante l'ottenimento del token.")
        return None

# Funzione per cercare l'ID dell'artista
def search_artist_id(artist_name, token):
    """Cerca l'ID Spotify di un artista dato il suo nome."""
    search_url = 'https://api.spotify.com/v1/search'
    headers = {'Authorization': f'Bearer {token}'}
    params = {'q': artist_name, 'type': 'artist', 'market': 'IT', 'limit': 1}
    try:
        response = requests.get(search_url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        search_results = response.json()
        artists = search_results.get('artists', {}).get('items', [])
        if artists:
            return artists[0] # Ritorna l'intero oggetto artista
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"Errore durante la ricerca dell'artista: {e}")
        return None
    except (KeyError, IndexError, json.JSONDecodeError):
        print("Errore: Formato della risposta di ricerca artista non valido.")
        return None

# Funzione per ottenere gli album di un artista
def get_artist_albums(artist_id, token):
    """Recupera tutti gli album di un artista dato il suo ID."""
    albums = []
    url = f'https://api.spotify.com/v1/artists/{artist_id}/albums'
    headers = {'Authorization': f'Bearer {token}'}
    params = {'include_groups': 'album,single', 'market': 'IT', 'limit': 50}
    try:
        while url:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            page = response.json()
            albums.extend(page.get('items', []))
            url = page.get('next')
            params = {}
        return albums
    except requests.exceptions.RequestException as e:
        print(f"Errore durante il recupero degli album: {e}")
        return None
    except (KeyError, json.JSONDecodeError):
        print("Errore: Formato della risposta degli album non valido.")
        return None

# Funzione per ottenere le tracce di un album
def get_album_tracks(album_id, token):
    """Recupera tutte le tracce di un album dato il suo ID."""
    tracks = []
    url = f'https://api.spotify.com/v1/albums/{album_id}/tracks'
    headers = {'Authorization': f'Bearer {token}'}
    params = {'market': 'IT', 'limit': 50, 'fields': 'items(name,popularity,id,external_urls.spotify),next'}
    try:
        while url:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            page = response.json()
            tracks.extend(page.get('items', []))
            url = page.get('next')
            params = {}
        return tracks
    except requests.exceptions.RequestException as e:
        print(f"Errore durante il recupero delle tracce dell'album: {e}")
        return None
    except (KeyError, json.JSONDecodeError):
        print("Errore: Formato della risposta delle tracce non valido.")
        return None
