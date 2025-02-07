from plexapi.server import PlexServer
from config import PLEX_SERVER_URL, PLEX_TOKEN
import logging

logger = logging.getLogger(__name__)

def update_plex_library(file_path: str) -> str:
    """
    Updates the Plex library so that it picks up the new movie file.
    Returns a status message.
    """
    try:
        plex = PlexServer(PLEX_SERVER_URL, PLEX_TOKEN)
        # Assume the movie is in a library named 'Movies'
        movie_library = plex.library.section('Movies')
        movie_library.update()
        message = f"Plex library updated for file: {file_path}"
        print(message)
        return message
    except Exception as e:
        print("Error updating Plex:", e)
        return "Plex update failed."

def get_recent_movies(limit: int = 5):
    """
    Returns the last `limit` updated movies from the Plex 'Movies' library.
    """
    try:
        plex = PlexServer(PLEX_SERVER_URL, PLEX_TOKEN)
        movie_library = plex.library.section('Movies')
        # Get all movies from the section
        movies = movie_library.all()
        # Sort movies by their updated time in descending order
        # The attribute name is 'updatedAt'; adjust if needed
        sorted_movies = sorted(movies, key=lambda m: m.updatedAt, reverse=True)
        return sorted_movies[:limit]
    except Exception as e:
        print("Error retrieving recent movies from Plex:", e)
        return None