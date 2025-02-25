# unpacker.py
import os
import patoolib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

def unpack_download_if_needed(file_path: str) -> Optional[str]:
    """
    Extracts archive files if the file is a supported archive format.
    
    Args:
        file_path: Path to the downloaded file
        
    Returns:
        Path to the extracted directory if extraction was successful,
        None if the file is not an archive or extraction failed
    """
    # Check if file exists and is a supported archive format
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"📁 File does not exist: {file_path}")
        return None
        
    supported_formats = (".zip", ".rar", ".7z")
    if not file_path.endswith(supported_formats):
        logger.debug(f"📄 Not an archive file: {file_path}")
        return None
    
    # Get file size
    file_size_bytes = os.path.getsize(file_path)
    file_size_mb = file_size_bytes / (1024 * 1024)
    
    logger.info(f"📦 Processing archive: {os.path.basename(file_path)} ({file_size_mb:.2f} MB)")
    
    # Create extraction directory
    extract_to = os.path.join("extracted", os.path.basename(file_path))
    os.makedirs("extracted", exist_ok=True)
    
    try:
        # Extract the archive
        logger.info(f"🔓 Starting extraction of {os.path.basename(file_path)}...")
        patoolib.extract_archive(file_path, outdir=extract_to)
        
        # Get extracted size
        extracted_size = get_directory_size(extract_to)
        extracted_size_mb = extracted_size / (1024 * 1024)
        
        # Count extracted files
        file_count = count_files(extract_to)
        
        logger.info(f"✅ Extraction complete: {os.path.basename(file_path)}")
        logger.info(f"   📊 Extracted {file_count} files, total size: {extracted_size_mb:.2f} MB")
        logger.info(f"   📂 Extraction path: {extract_to}")
        
        return extract_to
    except patoolib.util.PatoolError as e:
        logger.error(f"❌ Error during extraction (patoolib): {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Unexpected error during extraction: {e}")
        return None

def get_directory_size(path: str) -> int:
    """Calculate the total size of all files in a directory"""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            if os.path.exists(fp):
                total_size += os.path.getsize(fp)
    return total_size

def count_files(path: str) -> int:
    """Count the number of files in a directory"""
    count = 0
    for dirpath, dirnames, filenames in os.walk(path):
        count += len(filenames)
    return count
