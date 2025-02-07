# unpacker.py
import os
import patoolib
import logging

logger = logging.getLogger(__name__)


def unpack_download_if_needed(file_path: str):
    if file_path and file_path.endswith((".zip", ".rar", ".7z")): # Check if file_path exists
        extract_to = os.path.join("extracted", os.path.basename(file_path))
        os.makedirs("extracted", exist_ok=True)
        try:
            patoolib.extract_archive(file_path, outdir=extract_to)
            logger.info(f"Extracted {file_path} to {extract_to}") # Use logger
            return extract_to
        except patoolib.util.PatoolError as e:  # Catch specific patoolib errors
            error_message = f"Error during extraction (patoolib): {e}"
            logger.error(error_message)
            return None
        except Exception as e: # Catch other errors
            error_message = f"Error during extraction: {e}"
            logger.error(error_message)
            return None
    return None # Return None if not an archive or file_path is None
