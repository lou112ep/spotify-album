    def search_playlist(self, playlist_name):
        """Cerca una playlist per nome."""
        search_url = 'https://api.spotify.com/v1/search'
        params = {'q': playlist_name, 'type': 'playlist', 'market': 'IT', 'limit': 1}
        data = self._make_request(search_url, params=params)
        return data.get('playlists', {}).get('items', []) if data else []

    def get_tracks_by_ids(self, track_ids):
        """Recupera i dettagli di più tracce in una sola chiamata."""
        url = f"https://api.spotify.com/v1/tracks?ids={','.join(track_ids)}"
        data = self._make_request(url)
        return data.get('tracks', []) if data else []
