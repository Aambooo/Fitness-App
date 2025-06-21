import yt_dlp
from yt_dlp.utils import DownloadError
from typing import Dict, Optional, Any
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)

class YouTubeExtractor:
    def __init__(self):
        self.ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
        }
        self.ydl = yt_dlp.YoutubeDL(self.ydl_opts)

    def get_info(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Extract video information from YouTube URL
        
        Args:
            url: YouTube video URL
            
        Returns:
            Dictionary with video info or None if extraction fails
        """
        try:
            with self.ydl:
                result = self.ydl.extract_info(url, download=False)
                
                if not result:
                    logging.error(f"No data extracted from URL: {url}")
                    return None
                    
                # Handle playlists (get first video)
                video = result['entries'][0] if 'entries' in result else result
                
                return self._format_video_info(video)
                
        except DownloadError as e:
            logging.error(f"DownloadError for URL {url}: {str(e)}")
        except Exception as e:
            logging.error(f"Unexpected error processing {url}: {str(e)}")
            
        return None

    def _format_video_info(self, video: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format extracted video information into standardized format
        
        Args:
            video: Raw video data from yt-dlp
            
        Returns:
            Formatted dictionary with selected video info
        """
        info_map = {
            'id': 'video_id',
            'title': 'title',
            'uploader': 'channel',
            'duration': 'duration',
            'view_count': 'view_count',
            'like_count': 'like_count',
            'channel_id': 'channel_id',
            'categories': 'categories',
            'tags': 'tags',
            'thumbnail': 'thumbnail',
            'upload_date': 'upload_date'
        }
        
        formatted = {}
        
        for yt_key, our_key in info_map.items():
            if yt_key in video:
                formatted[our_key] = video[yt_key]
                
        # Add additional calculated fields if needed
        if 'duration' in formatted:
            formatted['duration_text'] = self._format_duration(formatted['duration'])
            
        return formatted

    def _format_duration(self, seconds: int) -> str:
        """Convert duration in seconds to HH:MM:SS format"""
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        seconds = seconds % 60
        
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"

# Singleton instance for easy import
yt_extractor = YouTubeExtractor()