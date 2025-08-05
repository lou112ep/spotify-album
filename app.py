from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import os
import subprocess
from dotenv import load_dotenv
from spotify_client import SpotifyClient

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev")

# Inizializza il client Spotify una sola volta
spotify_client = SpotifyClient(os.getenv("CLIENT_ID"), os.getenv("CLIENT_SECRET"))

# Cache per i risultati
results_cache = {}

def add_to_seed_list(artist_id):
    """Aggiunge un ID artista al file seed, evitando duplicati."""
    file_path = 'seed_artists.txt'
    try:
        existing_ids = set()
        if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
            with open(file_path, 'r') as f:
                existing_ids = {line.strip() for line in f}
        
        if artist_id not in existing_ids:
            with open(file_path, 'a') as f:
                f.write(f"{artist_id}\n")
    except Exception as e:
        print(f"Errore durante l'aggiunta al file seed: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    artist_name = request.form.get('artist')
    if not artist_name:
        return redirect(url_for('index'))

    artist_info = spotify_client.search_artist(artist_name)
    if not artist_info:
        return f"Artista '{artist_name}' non trovato.", 404
    
    artist_id = artist_info['id']
    albums = spotify_client.get_artist_albums(artist_id)
    if albums is None:
        return "Errore nel recuperare gli album.", 500

    album_details = []
    seen_albums = set()
    for album in albums:
        album_name = album.get('name')
        if album_name.lower() not in seen_albums:
            album_details.append({
                'id': album.get('id'),
                'name': album_name,
                'url': album.get('external_urls', {}).get('spotify'),
                'image_url': album.get('images', [{}])[0].get('url') if album.get('images') else ''
            })
            seen_albums.add(album_name.lower())
    
    album_details.sort(key=lambda x: x['name'])
    
    results_cache[artist_id] = {
        'artist_name': artist_name,
        'albums': album_details
    }

    return render_template('results.html', artist_name=artist_name, albums=album_details, artist_id=artist_id)

@app.route('/tracks/<album_id>')
def get_tracks(album_id):
    tracks = spotify_client.get_album_tracks(album_id)

    if tracks is None:
        return jsonify({'error': 'Errore nel recuperare le tracce'}), 500

    track_details = [{
        'id': track.get('id'),
        'name': track.get('name'),
        'url': track.get('external_urls', {}).get('spotify')
    } for track in tracks]
    
    return jsonify(track_details)

# --- Download e Stato ---
download_status = {
    'progress': 0,
    'status_messages': [],
    'total_items': 0,
    'completed_items': 0,
}

def run_download(items_to_download):
    """Esegue il download in un thread separato."""
    global download_status

    if not items_to_download:
        download_status['progress'] = 100
        download_status['status_messages'].append("Nessun elemento valido da scaricare.")
        return

    output_dir = "/app/music"
    cookie_file = "/app/cookies.txt" 

    for i, (item_type, item_name, item_url) in enumerate(items_to_download):
        download_status['status_messages'].append(f"-> Inizio download {item_type}: {item_name}")
        
        command = ['spotdl', item_url, '--format', 'opus', '--output', output_dir]
        if cookie_file and os.path.exists(cookie_file):
            command.extend(['--cookie-file', cookie_file])

        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8', bufsize=1)
            
            for line in iter(process.stdout.readline, ''):
                if line:
                    download_status['status_messages'].append(f"   {line.strip()}")
            
            process.wait(timeout=180)

            if process.returncode == 0:
                download_status['status_messages'].append(f"   Download di '{item_name}' completato con successo.")
            else:
                download_status['status_messages'].append(f"   ERRORE durante il download di '{item_name}'. Codice: {process.returncode}")

        except subprocess.TimeoutExpired:
            process.kill()
            download_status['status_messages'].append(f"   ERRORE: Timeout (3 minuti) superato per '{item_name}'. Download interrotto e saltato.")
        except Exception as e:
            download_status['status_messages'].append(f"   ERRORE CRITICO per '{item_name}': {e}")
            
        download_status['completed_items'] = i + 1
        download_status['progress'] = int((download_status['completed_items'] / download_status['total_items']) * 100)

    download_status['status_messages'].append("--- TUTTI I DOWNLOAD SONO TERMINATI ---")
    if download_status['completed_items'] == download_status['total_items']:
        download_status['progress'] = 100

@app.route('/download', methods=['POST'])
def download():
    selected_items = request.form.getlist('selected_items')
    artist_id = request.form.get('artist_id')

    if not selected_items or not artist_id:
        return "Selezione non valida", 400

    add_to_seed_list(artist_id)
    
    items_to_download = []
    
    album_ids_to_download = []
    track_ids_to_download = []

    for item in selected_items:
        item_type, item_id = item.split('-', 1)
        if item_type == 'album':
            album_ids_to_download.append(item_id)
        elif item_type == 'track':
            track_ids_to_download.append(item_id)

    if album_ids_to_download:
        cache = results_cache.get(artist_id)
        if cache:
             for album_id in album_ids_to_download:
                album = next((a for a in cache['albums'] if a['id'] == album_id), None)
                if album:
                    items_to_download.append(('album', album['name'], album['url']))

    if track_ids_to_download:
        # Recuperiamo i dettagli in blocco
        tracks_data = spotify_client.get_tracks_by_ids(track_ids_to_download)
        for track_data in tracks_data:
            if track_data:
                track_name = track_data.get('name')
                track_url = track_data.get('external_urls', {}).get('spotify')
                if track_name and track_url:
                    items_to_download.append(('track', track_name, track_url))

    if not items_to_download:
        return "Nessun elemento valido da scaricare.", 400

    global download_status
    download_status = {
        'progress': 0,
        'status_messages': ["Inizializzazione del download..."],
        'total_items': len(items_to_download),
        'completed_items': 0,
    }
    
    import threading
    download_thread = threading.Thread(target=run_download, args=(items_to_download,))
    download_thread.start()

    return redirect(url_for('status_page'))

@app.route('/update-cookie', methods=['POST'])
def update_cookie():
    cookie_content = request.form.get('cookie_content', '')
    cookie_path = "/app/cookies.txt" 
    
    try:
        with open(cookie_path, 'w', encoding='utf-8') as f:
            f.write(cookie_content)
        flash('File cookie aggiornato con successo!', 'success')
    except Exception as e:
        print(f"Errore durante la scrittura del file cookie: {e}")
        flash(f"Errore durante l'aggiornamento del file cookie: {e}", 'error')
        
    return redirect(url_for('index'))

@app.route('/status')
def status():
    return jsonify(download_status)

@app.route('/status-page')
def status_page():
    return render_template('status.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5001)
