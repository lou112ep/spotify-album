# Spotify Artist Album Downloader

Questo script Python scarica tutti gli album e i singoli di artisti specificati da Spotify utilizzando `spotdl`.

## Setup

1.  **Clona il repository (opzionale):**
    ```bash
    git clone <url-del-repository>
    cd <directory-repository>
    ```

2.  **Crea e attiva un ambiente virtuale:**
    ```bash
    python3 -m venv spotify_album_env
    source spotify_album_env/bin/activate
    ```
    *(Su Windows, usa `spotify_album_env\Scripts\activate`)*

3.  **Installa le dipendenze:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configura le credenziali:**
    *   Crea un file chiamato `.env` nella directory principale.
    *   Aggiungi le seguenti righe, sostituendo i valori con le tue credenziali reali:
        ```dotenv
        CLIENT_ID="IL_TUO_CLIENT_ID_SPOTIFY"
        CLIENT_SECRET="IL_TUO_CLIENT_SECRET_SPOTIFY"
        TELEGRAM_BOT_TOKEN="IL_TUO_TOKEN_BOT_TELEGRAM" # Opzionale
        TELEGRAM_CHAT_ID="IL_TUO_CHAT_ID_TELEGRAM"   # Opzionale
        ```
    *   Puoi ottenere le credenziali Spotify creando un'app su [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/).
    *   Le credenziali Telegram sono necessarie solo se vuoi ricevere notifiche.

5.  **Prepara la lista artisti:**
    *   Crea un file chiamato `artists.txt` nella directory principale.
    *   Aggiungi un nome di artista per riga. Esempio:
        ```
        Artista Uno
        Artista Due
        Un Altro Artista
        ```

## Esecuzione

Assicurati che l'ambiente virtuale sia attivo, poi esegui lo script:

```bash
python spotify_album.py
```

Lo script leggerà gli artisti da `artists.txt`, scaricherà i loro album (in formato Opus) nella directory corrente e invierà notifiche su Telegram (se configurato). Gli errori di download verranno registrati in `errors.log`.
