import yt_dlp
from yt_dlp.utils import DownloadError, MaxDownloadsReached
from typing import Dict, Optional, Any, Union
import logging
from datetime import datetime
import re

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('yt_extractor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('YouTubeExtractor')

class YouTubeExtractor:
    """
    Robust YouTube video metadata extractor with enhanced error handling and sanitization.
    Handles videos, playlists, and live streams.
    """
    
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
            'socket_timeout': 15,
            'extractor_args': {
                'youtube': {
                    'skip': ['hls', 'dash', 'translated_subs']
                }
            },
            'logger': logger
        }
        self.ydl = yt_dlp.YoutubeDL(self.ydl_opts)
        self.url_regex = re.compile(
            r'(https?://)?(www\.)?'
            r'(youtube|youtu|youtube-nocookie)\.(com|be)/'
            r'(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
        )

    def validate_url(self, url: str) -> bool:
        """Validate YouTube URL format"""
        return bool(self.url_regex.match(url))

    def get_info(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract and sanitize video information from YouTube URL
        
        Args:
            url: Valid YouTube URL (video/playlist/live)
            
        Returns:
            Dict: {
                'video_id': str,
                'title': str,
                'channel': str,
                'duration': int (seconds),
                'view_count': int,
                'thumbnail': str (URL),
                'is_live': bool,
                ...other metadata
            }
            or None if extraction fails
        """
        if not self.validate_url(url):
            logger.error(f"Invalid YouTube URL: {url}")
            return None

        try:
            with self.ydl:
                result = self.ydl.extract_info(url, download=False)
                
                if not result:
                    logger.error(f"No data extracted from URL: {url}")
                    return None
                    
                # Handle different content types
                video = self._extract_primary_video(result)
                return self._sanitize_video_info(video) if video else None
                
        except MaxDownloadsReached:
            logger.error("YouTube rate limit reached - try again later")
        except DownloadError as e:
            logger.error(f"DownloadError: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return None

    def _extract_primary_video(self, data: Dict) -> Optional[Dict]:
        """Extract main video from possible playlist/stream"""
        if 'entries' in data:  # Playlist/channel
            entries = [e for e in data['entries'] if e and 'id' in e]
            return entries[0] if entries else None
        return data if 'id' in data else None

    def _sanitize_video_info(self, video: Dict) -> Dict[str, Any]:
        """Sanitize and standardize video metadata"""
        info_map = {
            'id': ('video_id', str),
            'title': ('title', str),
            'uploader': ('channel', str),
            'duration': ('duration', int),
            'view_count': ('views', int),
            'thumbnail': ('thumbnail', str),
            'is_live': ('is_live', bool),
            'upload_date': ('upload_date', lambda x: datetime.strptime(x, '%Y%m%d').date()),
            'categories': ('categories', list),
            'tags': ('tags', list)
        }
        
        result = {}
        for yt_key, (our_key, type_fn) in info_map.items():
            try:
                if value := video.get(yt_key):
                    result[our_key] = type_fn(value)
            except (ValueError, TypeError):
                logger.warning(f"Failed to convert {yt_key} to {type_fn.__name__}")
                continue
                
        # Additional calculated fields
        if 'duration' in result:
            result['duration_text'] = self._format_duration(result['duration'])
            
        return result

    @staticmethod
    def _format_duration(seconds: int) -> str:
        """Convert seconds to human-readable HH:MM:SS"""
        hours, remainder = divmod(seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours}:{minutes:02d}:{seconds:02d}" if hours else f"{minutes}:{seconds:02d}"

# Singleton pattern for module-level usage
yt_extractor = YouTubeExtractor()