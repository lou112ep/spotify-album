import os
import json
import time
import requests
import subprocess
from dotenv import load_dotenv
from spotify_client import SpotifyClient

# Carica le variabili d'ambiente e le impostazioni
load_dotenv()
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")

# Costanti per i nomi dei file
SEED_FILE = 'seed_artists.txt'
PROCESSED_FILE = 'processed_artists.txt'
SETTINGS_FILE = 'discovery_settings.json'

def load_settings():
    """Carica le impostazioni dal file JSON."""
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERRORE: File '{SETTINGS_FILE}' non trovato.")
        return None

def read_ids_from_file(filename):
    """Legge gli ID da un file, uno per riga."""
    if not os.path.exists(filename):
        return set()
    with open(filename, 'r') as f:
        return {line.strip() for line in f if line.strip()}

def write_ids_to_file(filename, ids):
    """Scrive un set di ID in un file, uno per riga."""
    with open(filename, 'w') as f:
        for item_id in sorted(list(ids)):
            f.write(f"{item_id}\n")

def discover_related_artists(client, settings):
    """Logica di scoperta basata sugli artisti correlati."""
    print("\n--- Inizio scoperta per Artisti Correlati ---")
    seed_artists = read_ids_from_file(SEED_FILE)
    processed_artists = read_ids_from_file(PROCESSED_FILE)
    
    new_seeds = seed_artists - processed_artists
    artists_to_download = set()

    if not new_seeds:
        print("Nessun nuovo artista 'seme' da processare.")
    else:
        print(f"Trovati {len(new_seeds)} nuovi artisti seme: {', '.join(new_seeds)}")
        popularity_threshold = settings.get('popularity_threshold_artist', 50)

        for artist_id in new_seeds:
            print(f"\nProcesso l'artista seme: {artist_id}")
            related = client.get_related_artists(artist_id)
            
            for artist in related:
                artist_name = artist.get('name')
                artist_popularity = artist.get('popularity', 0)
                related_artist_id = artist.get('id')

                if related_artist_id in processed_artists:
                    continue

                if artist_popularity >= popularity_threshold:
                    print(f"  -> Trovato artista correlato popolare: {artist_name} (Pop: {artist_popularity})... AGGIUNTO ALLA CODA.")
                    artists_to_download.add(related_artist_id)
            
            processed_artists.add(artist_id)
            time.sleep(1)

    write_ids_to_file(PROCESSED_FILE, processed_artists)
    remaining_seeds = seed_artists - new_seeds
    write_ids_to_file(SEED_FILE, remaining_seeds)
    print("--- Fine scoperta per Artisti Correlati ---")
    return processed_artists, artists_to_download

def discover_from_top_charts(client, settings, processed_artists):
    """Logica di scoperta basata sulle classifiche Top."""
    print("\n--- Inizio scoperta dalle Top Charts ---")
    chart_names = {
        "Top 50 Italia": "it", # Stringa di ricerca più affidabile
        "Top 50 Global": "global"
    }
    artists_to_download = set()
    popularity_threshold = settings.get('popularity_threshold_artist', 50)

    for name, region in chart_names.items():
        print(f"\nProcesso la classifica: {name}")
        search_result = client.search_playlist(name)
        
        # CONTROLLO DI SICUREZZA:
        # Se la ricerca non produce risultati, avvisa e passa al prossimo.
        if not search_result:
            print(f"  -> ATTENZIONE: Nessuna playlist trovata per la ricerca '{name}'. Salto.")
            continue
        
        playlist_id = search_result[0].get('id')
        print(f"  -> Trovato ID playlist: {playlist_id}")
        
        artists = client.get_playlist_track_artists(playlist_id)
        if not artists:
            print(f"  -> Impossibile recuperare artisti per la playlist {playlist_id}.")
            continue

        for artist in artists:
            artist_id = artist.get('id')
            if artist_id in processed_artists or artist_id in artists_to_download:
                continue

            artist_popularity = artist.get('popularity', 0)
            if artist_popularity >= popularity_threshold:
                print(f"  -> Trovato artista popolare: {artist.get('name')} (Pop: {artist_popularity})... AGGIUNTO ALLA CODA.")
                artists_to_download.add(artist_id)
        
        time.sleep(1)

    print("--- Fine scoperta dalle Top Charts ---")
    return artists_to_download

def discover_from_genres(client, settings, processed_artists):
    """Logica di scoperta basata sui generi musicali."""
    print("\n--- Inizio scoperta per Generi Musicali ---")
    genres = settings.get('seed_genres', [])
    artists_to_download = set()
    
    if not genres:
        print("Nessun genere 'seme' definito nelle impostazioni.")
        return artists_to_download

    popularity_threshold = settings.get('popularity_threshold_artist', 50)

    for genre in genres:
        print(f"\nProcesso il genere: {genre}")
        results = client.search_for_genre(genre)
            
        for artist in results:
            artist_id = artist.get('id')
            if artist_id in processed_artists or artist_id in artists_to_download:
                continue

            artist_popularity = artist.get('popularity', 0)
            if artist_popularity >= popularity_threshold:
                print(f"  -> Trovato artista popolare: {artist.get('name')} (Pop: {artist_popularity})... AGGIUNTO ALLA CODA.")
                artists_to_download.add(artist_id)
        
        time.sleep(1)

    print("--- Fine scoperta per Generi Musicali ---")
    return artists_to_download

def download_popular_tracks(client, artist_id, settings, cookie_file):
    """Scarica le tracce più popolari di un artista."""
    print(f"\n--- Inizio download per l'artista {artist_id} ---")
    
    albums = client.get_artist_albums(artist_id)
    if not albums:
        print(f"Nessun album trovato per l'artista {artist_id}.")
        return

    track_popularity_threshold = settings.get('popularity_threshold_track', 20)
    tracks_to_download = []

    for album in albums:
        album_name = album.get('name')
        tracks = client.get_album_tracks(album.get('id'))
        if not tracks:
            continue
        
        for track in tracks:
            track_popularity = track.get('popularity', 0)
            if track_popularity >= track_popularity_threshold:
                track_url = track.get('external_urls', {}).get('spotify')
                track_name = track.get('name')
                if track_url and track_name:
                    tracks_to_download.append(track_url)
                    print(f"  -> Aggiunta traccia '{track_name}' (Pop: {track_popularity}) dall'album '{album_name}'")
        time.sleep(1)

    if not tracks_to_download:
        print(f"Nessuna traccia abbastanza popolare da scaricare per l'artista {artist_id}.")
        return
        
    output_dir = "/app/music"
    for i, track_url in enumerate(tracks_to_download):
        print(f"  Scaricando traccia {i+1}/{len(tracks_to_download)}...")
        command = ['spotdl', track_url, '--format', 'opus', '--output', output_dir]
        if cookie_file and os.path.exists(cookie_file):
            command.extend(['--cookie-file', cookie_file])
        
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1)
            for line in iter(process.stdout.readline, ''):
                if line:
                    print(f"    {line.strip()}")
            process.wait(timeout=180)
            if process.returncode != 0:
                print(f"    ATTENZIONE: spotdl ha restituito un errore per {track_url}")
        except subprocess.TimeoutExpired:
            process.kill()
            print(f"    ERRORE: Timeout superato per {track_url}")
        except Exception as e:
            print(f"    ERRORE CRITICO per {track_url}: {e}")

def main():
    print("Avvio dello script di scoperta musicale...")
    settings = load_settings()
    if not settings:
        return

    client = SpotifyClient(CLIENT_ID, CLIENT_SECRET)

    processed_artists, new_artists_related = discover_related_artists(client, settings)
    all_known_artists = processed_artists.union(new_artists_related)
    
    new_artists_charts = discover_from_top_charts(client, settings, all_known_artists)
    all_known_artists.update(new_artists_charts)

    new_artists_genres = discover_from_genres(client, settings, all_known_artists)
    
    final_artists_to_download = new_artists_related.union(new_artists_charts, new_artists_genres)

    if final_artists_to_download:
        print(f"\n--- Inizio Download Automatico ---")
        print(f"Totale artisti unici da scaricare: {len(final_artists_to_download)}")
        cookie_file = "cookies.txt"
        
        for i, artist_id in enumerate(final_artists_to_download):
            print(f"\nScaricando artista {i+1}/{len(final_artists_to_download)}: {artist_id}")
            download_popular_tracks(client, artist_id, settings, cookie_file)
            processed_artists.add(artist_id)
            write_ids_to_file(PROCESSED_FILE, processed_artists)
            print(f"Artista {artist_id} segnato come processato.")

    else:
        print("\nNessun nuovo artista da scaricare in questa sessione complessiva.")

    print("\nScript di scoperta completato.")

if __name__ == "__main__":
    main()
