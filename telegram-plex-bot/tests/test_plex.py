from plexapi.server import PlexServer
from config import PLEX_SERVER_URL, PLEX_TOKEN

try:
    plex = PlexServer(PLEX_SERVER_URL, PLEX_TOKEN)
    print("Successfully connected to Plex!")
    # You can try other Plex API operations here, like listing libraries
    for section in plex.library.sections():
        print(section.title)
except Exception as e:
    print(f"Error connecting to Plex: {e}")