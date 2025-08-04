import yt_dlp
from yt_dlp.utils import DownloadError
from typing import Dict, Optional, Any, List
import logging
from datetime import datetime
import re
import time

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("yt_extractor.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("YouTubeExtractor")


class YouTubeExtractor:
    """
    Enhanced YouTube video metadata extractor with:
    - Better error handling
    - Rate limiting protection
    - Comprehensive metadata extraction
    - URL validation
    """

    def __init__(self):
        self.ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": False,
            "skip_download": True,
            "socket_timeout": 15,
            "extractor_args": {"youtube": {"skip": ["hls", "dash", "translated_subs"]}},
            "logger": logger,
            "retries": 3,
            "sleep_interval": 5,  # Seconds between retries
        }
        self.ydl = yt_dlp.YoutubeDL(self.ydl_opts)
        self.url_regex = re.compile(
            r"(https?://)?(www\.)?"
            r"(youtube|youtu|youtube-nocookie)\.(com|be)/"
            r"(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})"
        )
        self.last_request_time = 0
        self.request_delay = 2  # Seconds between requests

    def validate_url(self, url: str) -> bool:
        """Validate YouTube URL format with strict checks"""
        if not url or not isinstance(url, str):
            return False
        match = self.url_regex.match(url)
        return bool(match and len(match.group(6)) == 11)  # Verify video ID length

    def get_info(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract and sanitize video information with retry logic

        Args:
            url: Valid YouTube URL

        Returns:
            Dict: Standardized video metadata including:
                - video_id, title, channel, duration (seconds)
                - thumbnail_url, view_count, upload_date
                - is_live (bool), duration_text (HH:MM:SS)
            None if extraction fails after retries
        """
        if not self.validate_url(url):
            logger.error(f"Invalid YouTube URL format: {url}")
            return None

        self._respect_rate_limit()

        try:
            with self.ydl:
                result = self.ydl.extract_info(url, download=False)
                return self._process_result(result) if result else None

        except DownloadError as e:
            logger.error(f"Download failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return None

    def _respect_rate_limit(self):
        """Enforce minimum delay between requests"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.request_delay:
            time.sleep(self.request_delay - elapsed)
        self.last_request_time = time.time()

    def _process_result(self, result: Dict) -> Optional[Dict[str, Any]]:
        """Process and standardize the extracted data"""
        if "entries" in result:  # Handle playlists/channels
            videos = [e for e in result["entries"] if e and "id" in e]
            if not videos:
                logger.warning("No valid videos found in playlist")
                return None
            result = videos[0]  # Use first video in playlist

        return self._sanitize_metadata(result) if "id" in result else None

    def _sanitize_metadata(self, video: Dict) -> Dict[str, Any]:
        """Convert and standardize video metadata"""
        metadata = {
            "video_id": video.get("id"),
            "title": self._clean_text(video.get("title", "Untitled")),
            "channel": self._clean_text(video.get("uploader", "Unknown")),
            "duration": int(video.get("duration", 0)),
            "views": int(video.get("view_count", 0)),
            "thumbnail": video.get("thumbnail"),
            "is_live": bool(video.get("is_live", False)),
            "upload_date": self._parse_date(video.get("upload_date")),
            "categories": video.get("categories", []),
            "tags": video.get("tags", []),
        }

        # Add formatted duration
        metadata["duration_text"] = self._format_duration(metadata["duration"])
        return metadata

    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean and normalize text fields"""
        if not text:
            return ""
        return " ".join(text.strip().split())  # Remove extra whitespace

    @staticmethod
    def _parse_date(date_str: Optional[str]) -> Optional[str]:
        """Convert YYYYMMDD to ISO format"""
        if not date_str or len(date_str) != 8:
            return None
        try:
            return datetime.strptime(date_str, "%Y%m%d").date().isoformat()
        except ValueError:
            return None

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Convert seconds to HH:MM:SS or MM:SS"""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


# Module-level instance for easy import
yt_extractor = YouTubeExtractor()
