import requests
import base64
import json
import subprocess # Aggiunto import per eseguire comandi esterni
import os # Aggiunto import per leggere le variabili d'ambiente
from dotenv import load_dotenv # Aggiunto import per caricare il file .env
import logging # Aggiunto import per il logging
from subprocess import TimeoutExpired # Import specifico per l'eccezione di timeout

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# Funzione per inviare messaggi Telegram
def send_telegram_message(bot_token, chat_id, text):
    """Invia un messaggio a una chat Telegram specificata."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'Markdown' # Opzionale: per formattare il testo
    }
    try:
        response = requests.post(url, data=payload, timeout=10)
        response.raise_for_status()
        print(f"Notifica Telegram inviata con successo.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Errore durante l'invio della notifica Telegram: {e}")
        # Logga anche l'errore di Telegram, se vuoi
        # logging.error(f"Errore invio Telegram: {e}")
        return False
    except Exception as e:
        print(f"Errore inaspettato durante l'invio della notifica Telegram: {e}")
        # logging.error(f"Errore inaspettato invio Telegram: {e}")
        return False

# Funzione per ottenere il token di accesso da Spotify usando Client Credentials Flow
def get_spotify_token(client_id, client_secret):
    """Ottiene un token di accesso da Spotify."""
    auth_url = 'https://accounts.spotify.com/api/token'
    # Codifica client ID e secret in Base64
    auth_header = base64.b64encode(f"{client_id}:{client_secret}".encode('utf-8')).decode('utf-8')

    headers = {
        'Authorization': f'Basic {auth_header}'
    }
    data = {
        'grant_type': 'client_credentials'
    }

    try:
        response = requests.post(auth_url, headers=headers, data=data, timeout=10)
        response.raise_for_status() # Solleva un'eccezione per errori HTTP
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
    headers = {
        'Authorization': f'Bearer {token}'
    }
    params = {
        'q': artist_name,
        'type': 'artist',
        'market': 'IT', # Cerca nel mercato italiano
        'limit': 1      # Prendiamo solo il risultato più probabile
    }

    try:
        response = requests.get(search_url, headers=headers, params=params, timeout=10)
        response.raise_for_status()
        search_results = response.json()
        artists = search_results.get('artists', {}).get('items', [])
        if artists:
            return artists[0]['id'] # Ritorna l'ID del primo artista trovato
        else:
            return None
    except requests.exceptions.RequestException as e:
        print(f"Errore durante la ricerca dell'artista: {e}")
        return None
    except (KeyError, IndexError):
        print("Errore: Formato della risposta di ricerca artista non valido.")
        return None
    except json.JSONDecodeError:
         print("Errore: Risposta non valida da Spotify durante la ricerca dell'artista.")
         return None
     
# Funzione per ottenere gli album di un artista
def get_artist_albums(artist_id, token):
    """Recupera tutti gli album di un artista dato il suo ID."""
    albums = []
    url = f'https://api.spotify.com/v1/artists/{artist_id}/albums'
    headers = {
        'Authorization': f'Bearer {token}'
    }
    params = {
        'include_groups': 'album,single', # Puoi specificare 'album', 'single', 'appears_on', 'compila>
        'market': 'IT',
        'limit': 50 # Massimo consentito per richiesta
    }

    try:
        while url:
            response = requests.get(url, headers=headers, params=params, timeout=10)
            response.raise_for_status()
            page = response.json()
            albums.extend(page.get('items', []))
            url = page.get('next') # URL per la pagina successiva, se esiste
            # Rimuoviamo i parametri dalla richiesta successiva perché sono già nell'URL 'next'
            params = {}
        return albums
    except requests.exceptions.RequestException as e:
        print(f"Errore durante il recupero degli album: {e}")
        return None
    except KeyError:
        print("Errore: Formato della risposta degli album non valido.")
        return None
    except json.JSONDecodeError:
        print("Errore: Risposta non valida da Spotify durante il recupero degli album.")
        return None
    
# --- Funzione Principale per Processare un Singolo Artista ---
def process_artist(artist_name, client_id, client_secret, telegram_bot_token, telegram_chat_id, telegram_enabled):
    """Processa un singolo artista: cerca, scarica album e notifica."""
    print(f"\n--- Inizio elaborazione per l'artista: {artist_name} ---")

    access_token = get_spotify_token(client_id, client_secret)

    if access_token:
        # print("Token ottenuto con successo.") # Meno verboso nel loop
        artist_id = search_artist_id(artist_name, access_token)

        # Inizializza il contatore degli errori per questo artista
        artist_download_error_count = 0

        if artist_id:
            print(f"Trovato ID artista per '{artist_name}': {artist_id}")
            all_albums = get_artist_albums(artist_id, access_token)

            if all_albums is not None:
                print(f"\nAlbum trovati per {artist_name} (Mercato IT):")
                # Usiamo un set per tenere traccia dei nomi degli album ed evitare duplicati
                # (Spotify a volte ritorna diverse versioni dello stesso album)
                album_urls = {}
                for album in all_albums:
                    album_name = album.get('name')
                    album_url = album.get('external_urls', {}).get('spotify')
                    # Aggiungiamo solo se non è già presente con lo stesso nome (versione più semplice per evitare duplicati da diverse edizioni)
                    if album_name and album_url and album_name.lower() not in [n.lower() for n in album_urls.keys()]:
                         album_urls[album_name] = album_url

                if album_urls:
                     # Ordina alfabeticamente per nome album
                    sorted_albums = sorted(album_urls.items())
                    # Non stampiamo l'elenco qui per non intasare l'output se ci sono molti artisti
                    # for name, url in sorted_albums:
                    #       print(f"- {name}: {url}")

                    # Esegui spotdl per ogni album trovato
                    print(f"\n--- Avvio download di {len(sorted_albums)} album per {artist_name} con spotdl ---")
                    for name, url in sorted_albums:
                        print(f"\n-> Esecuzione di spotdl per l'album: {name} ({url})")
                        try:
                            # Costruisci il comando come lista, aggiungendo i parametri
                            command = ['spotdl', url, '--format', 'opus', '--bitrate', 'disable']
                            # Esegui il comando e attendi il completamento con un timeout di 600 secondi (10 minuti).
                            # Rimuovendo capture_output=True, l'output di spotdl
                            # verrà mostrato direttamente nel terminale.
                            # check=True solleverà ancora un'eccezione se spotdl ritorna un errore.
                            result = subprocess.run(command, check=True, timeout=600)
                            print(f"   spotdl completato per: {name}")
                            # Non è più necessario stampare result.stdout/stderr perché
                            # l'output è già andato sul terminale.
                        except FileNotFoundError:
                            error_message = f"Comando 'spotdl' non trovato. Assicurati che sia installato e nel PATH."
                            print(f"   ERRORE: {error_message}")
                            logging.error(f"{error_message} (Tentativo per album '{name}' di {artist_name} - {url})") # Log più specifico
                            logging.getLogger().handlers[0].flush() # Forza scrittura log
                            artist_download_error_count += 1 # Aggiunto incremento contatore mancante
                            break # Interrompi il ciclo per questo artista se spotdl non è trovato
                        except TimeoutExpired: # Gestione specifica per il timeout
                            error_message = f"Timeout (10 minuti) superato durante il download dell'album: {name}"
                            print(f"   ERRORE: {error_message} - Salto all'album successivo.")
                            logging.error(f"{error_message} (Artista: {artist_name} - {url})")
                            logging.getLogger().handlers[0].flush() # Forza scrittura log
                            artist_download_error_count += 1 # Incrementa contatore errori
                            # Continua con il prossimo album
                        except subprocess.CalledProcessError as e:
                            # L'errore di spotdl sarà già stato stampato sul terminale.
                            error_message = f"spotdl ha restituito un errore per {name} (codice: {e.returncode})"
                            print(f"   ERRORE: {error_message} - Salto all'album successivo.")
                            logging.error(f"{error_message} (Artista: {artist_name} - {url})")
                            logging.getLogger().handlers[0].flush() # Forza scrittura log
                            artist_download_error_count += 1 # Incrementa contatore errori
                            # Continua con il prossimo album
                        except Exception as e:
                            error_message = f"Errore inaspettato durante l'esecuzione di spotdl per {name}: {e}"
                            print(f"   ERRORE: {error_message} - Salto all'album successivo.")
                            logging.error(f"{error_message} (Artista: {artist_name} - {url})")
                            logging.getLogger().handlers[0].flush() # Forza scrittura log
                            artist_download_error_count += 1 # Incrementa contatore errori
                            # Continua con il prossimo album
                else:
                    print(f"Nessun album trovato da scaricare per '{artist_name}' nel mercato IT.")
                    # Invia notifica anche se non trova album
                    if telegram_enabled:
                        message = f"Ricerca per l'artista '{artist_name}' completata. Nessun album trovato nel mercato IT."
                        send_telegram_message(telegram_bot_token, telegram_chat_id, message)

            else: # Caso in cui get_artist_albums ritorna None
                print(f"Errore durante il recupero degli album per '{artist_name}'. Controlla i log di errore dell'applicazione o l'output.")
                # Invia notifica di errore
                if telegram_enabled:
                    message = f"Errore durante il recupero degli album per l'artista '{artist_name}'. Download interrotto per questo artista."
                    send_telegram_message(telegram_bot_token, telegram_chat_id, message)

        else:
            print(f"Artista '{artist_name}' non trovato su Spotify (Mercato IT).")
            # Invia notifica se l'artista non viene trovato
            if telegram_enabled:
                message = f"Artista '{artist_name}' non trovato su Spotify (Mercato IT)."
                send_telegram_message(telegram_bot_token, telegram_chat_id, message)

        # --- Notifica di completamento per questo artista ---
        if artist_id and telegram_enabled: # Solo se l'artista è stato trovato e telegram è abilitato
            # Usa il contatore degli errori specifici dell'artista
            if artist_download_error_count > 0:
                message = f"Elaborazione per l'artista '{artist_name}' completata. Si sono verificati {artist_download_error_count} errori durante il download degli album. Controlla errors.log per i dettagli."
            else:
                message = f"Elaborazione per l'artista '{artist_name}' completata con successo. Nessun errore di download registrato."
            send_telegram_message(telegram_bot_token, telegram_chat_id, message)

    else:
        print(f"Impossibile ottenere token di accesso Spotify per processare '{artist_name}'. Salto artista.")
        # Potenzialmente invia notifica se il token Spotify fallisce?
        if telegram_enabled:
            message = f"Errore: Impossibile ottenere il token di accesso Spotify. Impossibile processare l'artista '{artist_name}'."
            send_telegram_message(telegram_bot_token, telegram_chat_id, message)

# --- Main Script ---
if __name__ == "__main__":

    # Configura il logging per scrivere su file in modalità append
    logging.basicConfig(filename='errors.log',
                        filemode='a', # Aggiunto per assicurare l'append
                        level=logging.ERROR,
                        format='%(asctime)s - %(levelname)s - %(message)s')

    # Leggi le credenziali Spotify dall'ambiente
    client_id = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")
    # Leggi le credenziali Telegram dall'ambiente
    telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID")

    # Verifica preliminare delle credenziali Telegram
    telegram_enabled = True
    if not telegram_bot_token or not telegram_chat_id:
        print("\nATTENZIONE: Token Bot Telegram o Chat ID non trovati nel .env. Le notifiche Telegram sono disabilitate.")
        telegram_enabled = False
    # else: # Rimuoviamo la stampa per pulizia output
        # print("Configurazione Telegram trovata. Le notifiche saranno inviate.")

    # Verifica credenziali Spotify
    if not client_id or not client_secret:
        print("ERRORE: CLIENT_ID o CLIENT_SECRET non trovate nel file .env o nelle variabili d'ambiente. Impossibile procedere.")
        exit() # Esci se mancano le credenziali Spotify

    # Leggi la lista degli artisti dal file artists.txt
    artists_file = "artists.txt"
    artists_to_process = []
    try:
        with open(artists_file, 'r', encoding='utf-8') as f:
            artists_to_process = [line.strip() for line in f if line.strip()]
        if not artists_to_process:
            print(f"ERRORE: Il file '{artists_file}' è vuoto o non contiene nomi validi.")
            exit()
        print(f"Trovati {len(artists_to_process)} artisti nel file '{artists_file}'.")
    except FileNotFoundError:
        print(f"ERRORE: File '{artists_file}' non trovato nella directory dello script. Crealo con un nome di artista per riga.")
        exit()
    except Exception as e:
        print(f"ERRORE inaspettato durante la lettura di '{artists_file}': {e}")
        exit()

    # Ciclo principale: processa ogni artista dalla lista
    total_artists = len(artists_to_process)
    for i, artist_name in enumerate(artists_to_process):
        print(f"\n[{i+1}/{total_artists}] Elaborazione artista: {artist_name}")
        try:
            process_artist(artist_name,
                           client_id,
                           client_secret,
                           telegram_bot_token,
                           telegram_chat_id,
                           telegram_enabled)
        except Exception as e:
            # Cattura eccezioni non gestite all'interno di process_artist
            error_message = f"Errore GRAVE e inaspettato durante l'elaborazione dell'artista '{artist_name}': {e}"
            print(error_message)
            logging.error(error_message) # Logga l'errore grave
            logging.getLogger().handlers[0].flush()
            if telegram_enabled:
                send_telegram_message(telegram_bot_token, telegram_chat_id, error_message + " Salto all'artista successivo.")
        print(f"--- Elaborazione per '{artist_name}' terminata. --- ")

    print("\n--- Tutte le elaborazioni sono terminate. ---")