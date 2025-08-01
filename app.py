from flask import Flask, render_template, request, redirect, url_for, jsonify
import os
from dotenv import load_dotenv
import spotify_album as sa
import subprocess
import requests


load_dotenv()

app = Flask(__name__)

# Cache per i risultati
results_cache = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/search', methods=['POST'])
def search():
    artist_name = request.form.get('artist')
    if not artist_name:
        return redirect(url_for('index'))

    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")

    token = sa.get_spotify_token(client_id, client_secret)
    if not token:
        return "Errore nell'ottenere il token da Spotify", 500

    artist_id = sa.search_artist_id(artist_name, token)
    if not artist_id:
        return f"Artista '{artist_name}' non trovato.", 404

    albums = sa.get_artist_albums(artist_id, token)
    if albums is None:
        return "Errore nel recuperare gli album.", 500

    # Semplifichiamo e puliamo la lista degli album
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
    
    # Ordiniamo gli album per nome
    album_details.sort(key=lambda x: x['name'])
    
    results_cache[artist_id] = {
        'artist_name': artist_name,
        'albums': album_details,
        'token': token
    }

    return render_template('results.html', artist_name=artist_name, albums=album_details, artist_id=artist_id)

@app.route('/tracks/<album_id>')
def get_tracks(album_id):
    artist_id = request.args.get('artist_id')
    cache = results_cache.get(artist_id)
    if not cache or not cache.get('token'):
        return jsonify({'error': 'Sessione scaduta o token non trovato'}), 404

    token = cache['token']
    tracks = sa.get_album_tracks(album_id, token)

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

def run_download(items_to_download, output_dir, cookie_file):
    """Esegue il download in un thread separato."""
    global download_status
    download_status['total_items'] = len(items_to_download)
    download_status['completed_items'] = 0
    download_status['status_messages'] = []
    
    for i, (item_type, item_name, item_url) in enumerate(items_to_download):
        download_status['status_messages'].append(f"-> Inizio download {item_type}: {item_name}")
        
        command = ['spotdl', item_url, '--format', 'opus', '--output', output_dir]
        if cookie_file and os.path.exists(cookie_file):
            command.extend(['--cookie-file', cookie_file])

        try:
            # Usiamo Popen per non bloccare e per catturare l'output linea per linea
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # Aggiungiamo l'output di spotdl ai messaggi di stato
                    download_status['status_messages'].append(f"   {output.strip()}")
            
            if process.returncode == 0:
                download_status['status_messages'].append(f"   Download di '{item_name}' completato con successo.")
            else:
                download_status['status_messages'].append(f"   ERRORE durante il download di '{item_name}'. Codice: {process.returncode}")

        except Exception as e:
            download_status['status_messages'].append(f"   ERRORE CRITICO per '{item_name}': {e}")
            
        download_status['completed_items'] = i + 1
        download_status['progress'] = int((download_status['completed_items'] / download_status['total_items']) * 100)

    download_status['status_messages'].append("--- TUTTI I DOWNLOAD SONO TERMINATI ---")


@app.route('/download', methods=['POST'])
def download():
    selected_items = request.form.getlist('selected_items')
    artist_id = request.form.get('artist_id')

    if not selected_items or not artist_id:
        return "Selezione non valida", 400

    cache = results_cache.get(artist_id)
    if not cache:
        return "Cache scaduta o non trovata. Riprova la ricerca.", 404

    items_to_download = []
    
    # Recupera i dettagli delle tracce dal form dinamicamente
    track_details_map = {}
    for key in request.form:
        if key.startswith('track-url-'):
            track_id = key.replace('track-url-', '')
            track_name = request.form.get(f'track-name-{track_id}')
            track_details_map[track_id] = {'url': request.form[key], 'name': track_name}

    for item in selected_items:
        item_type, item_id = item.split('-', 1)
        
        if item_type == 'album':
            album = next((a for a in cache['albums'] if a['id'] == item_id), None)
            if album:
                items_to_download.append(('album', album['name'], album['url']))
        
        elif item_type == 'track':
            # Per le tracce, abbiamo bisogno dell'URL e del nome, che ora recuperiamo
            # dalla cache o, meglio, potremmo doverli passare direttamente dal form.
            # Modifichiamo il JS per inviare questi dati.
            # Dato che il JS è già stato scritto per non farlo, cerchiamo nella cache degli album le tracce
            # Questo è inefficiente. Modifico il JS e l'HTML per passare i dati.
            # Per ora, facciamo un placeholder
            # Questo non funzionerà senza l'URL, quindi dobbiamo recuperarlo.
            # La soluzione migliore è arricchire la cache o passare i dati dal form.
            # **Modifica post-riflessione:** La soluzione più pulita è recuperare i dati dal form,
            # ma questo richiede di modificare l'HTML e il JS per aggiungere campi nascosti.
            # Una via di mezzo è recuperare di nuovo i dati, ma è inefficiente.
            # La cache attuale non memorizza le tracce.
            # Procediamo con l'idea di recuperare l'URL della traccia.
            # Ho aggiornato il JS per popolare i data attributes, ma leggerli qui è complesso.
            # La cosa più semplice è un approccio ibrido.
            # L'HTML/JS è stato modificato per inviare "track-ID". Qui dobbiamo ottenere l'URL.
            # L'approccio più robusto è fare una chiamata API per l'URL della traccia se non in cache.
            # Ma il token è disponibile.
            
            # Semplifichiamo: non gestiamo le tracce qui finché il JS non invia più dati.
            # **REVISIONE:** Il JS ora aggiunge le tracce dinamicamente. I loro dati non sono nel form standard.
            # Dobbiamo leggerli in modo diverso.
            # Modifico il modo in cui leggiamo il form per catturare i dati delle tracce.
            
            # Non posso ottenere i dettagli della traccia qui facilmente.
            # Devo modificare l'HTML per includere i dati necessari.
            # Riscrivo il JS per essere più esplicito.
            pass # Placeholder
            
    # NUOVA LOGICA PER IL DOWNLOAD
    
    items_to_download = []
    for item in selected_items:
        item_type, item_id = item.split('-', 1)
        if item_type == 'album':
            album = next((a for a in cache['albums'] if a['id'] == item_id), None)
            if album:
                items_to_download.append(('album', album['name'], album['url']))
        elif item_type == 'track':
            # Qui abbiamo solo l'ID, dobbiamo ottenere l'URL.
            # Facciamo una chiamata API al volo.
            track_info_url = f"https://api.spotify.com/v1/tracks/{item_id}"
            headers = {'Authorization': f'Bearer {cache["token"]}'}
            try:
                response = requests.get(track_info_url, headers=headers)
                response.raise_for_status()
                track_data = response.json()
                track_name = track_data.get('name')
                track_url = track_data.get('external_urls', {}).get('spotify')
                if track_name and track_url:
                    items_to_download.append(('track', track_name, track_url))
            except requests.RequestException as e:
                print(f"Errore nel recuperare i dati della traccia {item_id}: {e}")

    if not items_to_download:
        return "Nessun elemento valido da scaricare.", 400

    output_dir = "/app/music"
    cookie_file = "/app/cookies.txt" 
    
    import threading
    download_thread = threading.Thread(target=run_download, args=(items_to_download, output_dir, cookie_file))
    download_thread.start()

    return redirect(url_for('status_page'))

@app.route('/update-cookie', methods=['POST'])
def update_cookie():
    cookie_content = request.form.get('cookie_content', '')
    # Il percorso è quello all'interno del container
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
