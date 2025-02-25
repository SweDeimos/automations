from plexapi.server import PlexServer
from config import PLEX_SERVER_URL, PLEX_TOKEN
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

def update_plex_library(file_path: str) -> str:
    """
    Updates the Plex library to scan for new media files.
    
    Args:
        file_path: Path to the file that was added
        
    Returns:
        Status message indicating success or failure
    """
    try:
        logger.info(f"🎬 Updating Plex library for: {os.path.basename(file_path) if file_path else 'all libraries'}")
        plex = PlexServer(PLEX_SERVER_URL, PLEX_TOKEN)
        
        # Get all library sections
        libraries = plex.library.sections()
        logger.info(f"📚 Found {len(libraries)} Plex libraries: {', '.join(lib.title for lib in libraries)}")
        
        # Update appropriate library based on file path
        if file_path and ("movies" in file_path.lower() or "movie" in file_path.lower()):
            movie_library = next((lib for lib in libraries if lib.type == 'movie'), None)
            if movie_library:
                logger.info(f"🔄 Updating Movies library: {movie_library.title}")
                movie_library.update()
                message = f"Plex Movies library '{movie_library.title}' updated"
            else:
                logger.warning("⚠️ No Movies library found in Plex")
                message = "No Movies library found in Plex"
        elif file_path and ("tv" in file_path.lower() or "series" in file_path.lower()):
            tv_library = next((lib for lib in libraries if lib.type == 'show'), None)
            if tv_library:
                logger.info(f"🔄 Updating TV Shows library: {tv_library.title}")
                tv_library.update()
                message = f"Plex TV Shows library '{tv_library.title}' updated"
            else:
                logger.warning("⚠️ No TV Shows library found in Plex")
                message = "No TV Shows library found in Plex"
        else:
            # Update all libraries if we can't determine the type
            logger.info("🔄 Updating all Plex libraries")
            updated_libraries = []
            for library in libraries:
                logger.info(f"  - Updating {library.title}")
                library.update()
                updated_libraries.append(library.title)
            
            message = f"Updated {len(updated_libraries)} Plex libraries: {', '.join(updated_libraries)}"
        
        logger.info(f"✅ {message}")
        return message
    except Exception as e:
        error_message = f"❌ Error updating Plex: {e}"
        logger.error(error_message)
        return "Plex update failed. Check logs for details."

def get_recent_movies(limit: int = 5) -> Optional[List]:
    """
    Returns the most recently updated movies from the Plex 'Movies' library.
    
    Args:
        limit: Maximum number of movies to return
        
    Returns:
        List of recent movies or None if an error occurred
    """
    try:
        logger.info(f"🔍 Retrieving {limit} recent movies from Plex")
        plex = PlexServer(PLEX_SERVER_URL, PLEX_TOKEN)
        
        # Try to get the Movies library
        movie_library = next((lib for lib in plex.library.sections() if lib.type == 'movie'), None)
        if not movie_library:
            logger.warning("⚠️ No Movies library found in Plex")
            return None
            
        logger.info(f"📚 Connected to Movies library: {movie_library.title}")
            
        # Get all movies from the section
        movies = movie_library.all()
        logger.info(f"📊 Found {len(movies)} total movies in library")
        
        # Sort movies by their updated time in descending order
        sorted_movies = sorted(movies, key=lambda m: m.updatedAt, reverse=True)
        
        # Log the recent movies
        recent = sorted_movies[:limit]
        logger.info(f"✅ Retrieved {len(recent)} recent movies")
        
        for i, movie in enumerate(recent, 1):
            added_date = movie.addedAt.strftime("%Y-%m-%d") if hasattr(movie, 'addedAt') else 'Unknown'
            logger.info(f"  {i}. {movie.title} ({getattr(movie, 'year', 'N/A')}) - Added: {added_date}")
            
        return recent
    except Exception as e:
        logger.error(f"❌ Error retrieving recent movies from Plex: {e}")
        return None