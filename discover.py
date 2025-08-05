def discover_from_top_charts(client, settings, processed_artists):
    """Logica di scoperta basata sulle classifiche Top."""
    print("\n--- Inizio scoperta dalle Top Charts ---")
    
    # Riscriviamo la logica per usare la ricerca, che è più affidabile
    # degli ID diretti per le classifiche.
    chart_names = {
        "Top 50 - Italia": "it",
        "Top 50 - Global": "global"
    }
    
    artists_to_download = set()
    popularity_threshold = settings.get('popularity_threshold_artist', 50)

    for name, region in chart_names.items():
        print(f"\nProcesso la classifica: {name}")
        # Usiamo il client per cercare la playlist e poi ottenerne le tracce
        search_result = client.search_playlist(name)
        if not search_result:
            print(f"  -> Nessuna playlist trovata per '{name}'.")
            continue
        
        # Prendiamo la prima playlist trovata, che è quasi sempre quella ufficiale
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
