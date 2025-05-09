#!/usr/bin/env python3
"""
Code Crawler - A web crawler that collects code snippets, repositories, and datasets
for various programming languages using ScraperAPI and Oxylabs to bypass anti-scraping protections.

This is a production-grade implementation with robust error handling, performance optimizations,
and secure credential management.
"""

import os
import json
import time
import random
import logging
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse, quote_plus
import concurrent.futures
import hashlib
from typing import Dict, List, Optional, Tuple, Set, Any, Union, Callable
from threading import Lock
import base64
from functools import lru_cache
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Load environment variables from .env file
load_dotenv()

# Configure logging with proper rotation to prevent large log files
import logging.handlers

# Create logs directory if it doesn't exist
os.makedirs('logs', exist_ok=True)

# Set up rotating file handler
file_handler = logging.handlers.RotatingFileHandler(
    "logs/crawler_log.txt", 
    maxBytes=10*1024*1024,  # 10MB max file size
    backupCount=5,           # Keep 5 backup copies
    encoding='utf-8'
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        file_handler,
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CodeCrawler")

# Constants - Get API keys from environment variables
SCRAPER_API_KEY = os.environ.get("SCRAPER_API_KEY", "")
OXYLABS_USERNAME = os.environ.get("OXYLABS_USERNAME", "")
OXYLABS_PASSWORD = os.environ.get("OXYLABS_PASSWORD", "")
DATA_DIR = os.environ.get("DATA_DIR", "collected_data")
ITEMS_PER_LANGUAGE = int(os.environ.get("ITEMS_PER_LANGUAGE", "1000"))
MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "8"))
REQUEST_TIMEOUT = int(os.environ.get("REQUEST_TIMEOUT", "60"))

# Supported programming languages
LANGUAGES = [
    "Swift", "Python", "Lua", "C", "C++", 
    "Objective-C", "C#", "Ruby", "JavaScript", "TypeScript"
]

# File extensions mapping for language detection
LANGUAGE_FILE_EXTENSIONS = {
    "Swift": [".swift"],
    "Python": [".py", ".ipynb"],
    "Lua": [".lua"],
    "C": [".c", ".h"],
    "C++": [".cpp", ".hpp", ".cc", ".hh", ".cxx", ".hxx"],
    "Objective-C": [".m", ".mm"],
    "C#": [".cs"],
    "Ruby": [".rb", ".rake", ".gemspec"],
    "JavaScript": [".js", ".jsx", ".mjs"],
    "TypeScript": [".ts", ".tsx"]
}

# Ensure data directory exists
os.makedirs(DATA_DIR, exist_ok=True)
for lang in LANGUAGES:
    os.makedirs(os.path.join(DATA_DIR, lang), exist_ok=True)

class ScraperAPIClient:
    """Client for interacting with ScraperAPI to bypass anti-scraping measures.
    
    Features:
    - Connection pooling for improved performance
    - Advanced retry strategy with exponential backoff
    - Configurable rate limiting
    - Efficient error handling
    """
    
    def __init__(self, api_key: str, max_retries: int = 5, rate_limit_per_minute: int = 60):
        """
        Initialize the ScraperAPI client with configurable settings.
        
        Args:
            api_key: ScraperAPI authentication key
            max_retries: Maximum number of retry attempts for failed requests
            rate_limit_per_minute: Maximum requests allowed per minute
        """
        if not api_key:
            raise ValueError("ScraperAPI key cannot be empty")
        
        self.api_key = api_key
        self.base_url = "http://api.scraperapi.com"
        self.rate_limit = rate_limit_per_minute
        self.request_count = 0
        self.last_request_time = time.time()
        self.request_timestamps = []  # For tracking request timing
        self.lock = Lock()
        
        # Create session with connection pooling and retry strategy
        self.session = self._create_session(max_retries)
        
    def _create_session(self, max_retries: int) -> requests.Session:
        """
        Create a requests session with connection pooling and retry configuration.
        
        Args:
            max_retries: Maximum number of retry attempts
            
        Returns:
            Configured requests.Session object
        """
        session = requests.Session()
        
        # Configure retry strategy with exponential backoff
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=2.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            respect_retry_after_header=True
        )
        
        # Configure connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,  # Number of connection pools
            pool_maxsize=50       # Max connections per pool
        )
        
        # Mount adapter for both HTTP and HTTPS
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers and timeout
        session.headers.update({
            "User-Agent": "CodeCrawler/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml",
            "Accept-Language": "en-US,en;q=0.9"
        })
        
        return session
    
    def _get_proxy_url(self, url: str, render: bool = False, country_code: str = None) -> str:
        """
        Create a ScraperAPI proxy URL for the target URL with advanced options.
        
        Args:
            url: Target URL to scrape
            render: Whether to render JavaScript
            country_code: Optional country code for geo-targeting
            
        Returns:
            ScraperAPI proxy URL
        """
        params = {
            "api_key": self.api_key,
            "url": quote_plus(url),
        }
        
        if render:
            params["render"] = "true"
            
        if country_code:
            params["country_code"] = country_code
            
        # Add premium parameters if needed
        # params["premium"] = "true"  # Uncomment to use premium proxy
            
        param_str = "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
        return f"{self.base_url}/?{param_str}"
    
    def _enforce_rate_limit(self):
        """
        Enforce rate limiting using sliding window algorithm.
        """
        current_time = time.time()
        
        # Remove timestamps older than 60 seconds
        self.request_timestamps = [t for t in self.request_timestamps if current_time - t <= 60]
        
        # If we're at or over the rate limit, wait
        if len(self.request_timestamps) >= self.rate_limit:
            # Wait until the oldest timestamp is 60 seconds old
            oldest = self.request_timestamps[0]
            wait_time = max(0, 60 - (current_time - oldest))
            
            if wait_time > 0:
                logger.info(f"ScraperAPI rate limiting: sleeping for {wait_time:.2f} seconds")
                time.sleep(wait_time)
    
    def get(self, url: str, render: bool = False, retry_count: int = None, 
            backoff_factor: float = None, country_code: str = None) -> Optional[requests.Response]:
        """
        Make a GET request through ScraperAPI with rate limiting and retries.
        
        Args:
            url: Target URL to scrape
            render: Whether to render JavaScript
            retry_count: Optional override for retry count
            backoff_factor: Optional override for backoff factor
            country_code: Optional country code for geo-targeting
            
        Returns:
            Response object or None if request failed
        """
        with self.lock:
            # Apply rate limiting
            self._enforce_rate_limit()
            
            # Prepare request
            proxy_url = self._get_proxy_url(url, render, country_code)
            
            try:
                logger.info(f"ScraperAPI fetching: {url}")
                
                # Add current timestamp to the list for rate limiting
                self.request_timestamps.append(time.time())
                
                # Make request with error handling
                response = self.session.get(proxy_url, timeout=REQUEST_TIMEOUT)
                
                # Check if the request was successful
                if response.status_code == 200:
                    logger.debug(f"Successfully fetched {url}")
                    return response
                else:
                    # If we get here, it means the built-in retry mechanism failed
                    logger.error(f"ScraperAPI request failed with status {response.status_code}: {response.text[:100]}")
                    return None
                    
            except requests.RequestException as e:
                logger.error(f"ScraperAPI request error: {str(e)}")
                return None
            
            except Exception as e:
                logger.error(f"Unexpected error with ScraperAPI: {str(e)}")
                return None

class OxylabsClient:
    """Client for interacting with Oxylabs Realtime API.
    
    Features:
    - Connection pooling for improved performance
    - Advanced retry strategy with exponential backoff
    - Configurable rate limiting
    - Efficient error handling
    - Result caching
    """
    
    def __init__(self, username: str, password: str, max_retries: int = 5, rate_limit_per_minute: int = 60):
        """
        Initialize the Oxylabs client with configurable settings.
        
        Args:
            username: Oxylabs account username
            password: Oxylabs account password
            max_retries: Maximum number of retry attempts for failed requests
            rate_limit_per_minute: Maximum requests allowed per minute
        """
        if not username or not password:
            raise ValueError("Oxylabs credentials cannot be empty")
        
        self.base_url = "https://realtime.oxylabs.io/v1/queries"
        self.auth = (username, password)
        self.rate_limit = rate_limit_per_minute
        self.request_timestamps = []  # For tracking request timing
        self.lock = Lock()
        self.result_cache = {}  # Simple cache for results
        self.cache_ttl = 3600  # Cache TTL in seconds (1 hour)
        
        # Create session with connection pooling and retry strategy
        self.session = self._create_session(max_retries)
    
    def _create_session(self, max_retries: int) -> requests.Session:
        """
        Create a requests session with connection pooling and retry configuration.
        
        Args:
            max_retries: Maximum number of retry attempts
            
        Returns:
            Configured requests.Session object
        """
        session = requests.Session()
        
        # Configure retry strategy with exponential backoff
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=2.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"],
            respect_retry_after_header=True
        )
        
        # Configure connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,  # Number of connection pools
            pool_maxsize=50       # Max connections per pool
        )
        
        # Mount adapter for both HTTP and HTTPS
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            "User-Agent": "CodeCrawler/1.0",
            "Accept": "application/json",
            "Content-Type": "application/json"
        })
        
        return session
    
    def _enforce_rate_limit(self):
        """
        Enforce rate limiting using sliding window algorithm.
        """
        current_time = time.time()
        
        # Remove timestamps older than 60 seconds
        self.request_timestamps = [t for t in self.request_timestamps if current_time - t <= 60]
        
        # If we're at or over the rate limit, wait
        if len(self.request_timestamps) >= self.rate_limit:
            # Wait until the oldest timestamp is 60 seconds old
            oldest = self.request_timestamps[0]
            wait_time = max(0, 60 - (current_time - oldest))
            
            if wait_time > 0:
                logger.info(f"Oxylabs rate limiting: sleeping for {wait_time:.2f} seconds")
                time.sleep(wait_time)
    
    def _check_cache(self, url: str, render: bool) -> Optional[object]:
        """
        Check if we have a cached response for this URL.
        
        Args:
            url: The URL to check in the cache
            render: Whether JavaScript rendering was requested
            
        Returns:
            Cached response object or None if not found/expired
        """
        cache_key = f"{url}:{render}"
        cached_item = self.result_cache.get(cache_key)
        
        if cached_item:
            timestamp, content = cached_item
            current_time = time.time()
            
            # If cache entry is still valid
            if current_time - timestamp < self.cache_ttl:
                logger.debug(f"Cache hit for {url}")
                return content
            else:
                # Remove expired cache entry
                del self.result_cache[cache_key]
                
        return None
    
    def _update_cache(self, url: str, render: bool, content: object):
        """
        Update the cache with a new response.
        
        Args:
            url: The URL being cached
            render: Whether JavaScript rendering was requested
            content: The response content to cache
        """
        cache_key = f"{url}:{render}"
        self.result_cache[cache_key] = (time.time(), content)
        
        # Limit cache size to prevent memory issues
        if len(self.result_cache) > 1000:
            # Remove oldest items if cache gets too large
            oldest_keys = sorted(
                self.result_cache.keys(), 
                key=lambda k: self.result_cache[k][0]
            )[:200]  # Remove oldest 20% of entries
            
            for key in oldest_keys:
                del self.result_cache[key]
    
    def get(self, url: str, render: bool = False, retry_count: int = None, 
            backoff_factor: float = None, country_code: str = None) -> Optional[requests.Response]:
        """
        Make a GET request through Oxylabs Realtime API with rate limiting and retries.
        
        Args:
            url: Target URL to scrape
            render: Whether to render JavaScript
            retry_count: Optional override for retry count
            backoff_factor: Optional override for backoff factor
            country_code: Optional country code for geo-targeting
            
        Returns:
            Response object or None if request failed
        """
        with self.lock:
            # Check cache first
            cached_response = self._check_cache(url, render)
            if cached_response:
                return cached_response
            
            # Apply rate limiting
            self._enforce_rate_limit()
            
            # Prepare request payload
            payload = {
                "source": "universal",
                "url": url,
                "parse": True,
                "render": "html" if render else None
            }
            
            # Add geo-targeting if specified
            if country_code:
                payload["geo_location"] = country_code
                
            try:
                logger.info(f"Oxylabs fetching: {url}")
                
                # Add current timestamp to the list for rate limiting
                self.request_timestamps.append(time.time())
                
                # Make request with error handling
                response = self.session.post(
                    self.base_url,
                    auth=self.auth,
                    json=payload,
                    timeout=REQUEST_TIMEOUT
                )
                
                # Process response
                if response.status_code == 200:
                    try:
                        data = response.json()
                        content = data.get("results", [{}])[0].get("content", "")
                        
                        # Create a Response-like object
                        class OxylabsResponse:
                            def __init__(self, content):
                                self.status_code = 200
                                self.text = content
                                self.content = content.encode('utf-8')
                                
                                # Add convenience method to match requests.Response
                                def json(self):
                                    return json.loads(content)
                        
                        result = OxylabsResponse(content)
                        
                        # Cache the result
                        self._update_cache(url, render, result)
                        
                        logger.debug(f"Successfully fetched {url}")
                        return result
                    except (ValueError, KeyError) as e:
                        logger.error(f"Error parsing Oxylabs response JSON: {str(e)}")
                        return None
                else:
                    # If we get here, it means the built-in retry mechanism failed
                    logger.error(f"Oxylabs request failed with status {response.status_code}: {response.text[:100]}")
                    return None
                     
            except requests.RequestException as e:
                logger.error(f"Oxylabs request error: {str(e)}")
                return None
            
            except Exception as e:
                logger.error(f"Unexpected error with Oxylabs: {str(e)}")
                return None

class CodeData:
    """
    Class for managing and storing collected code data.
    
    Features:
    - Efficient storage and retrieval with incremental updates
    - Data validation and sanitization
    - Memory-optimized data structures
    - Automatic compression for large datasets
    - Checkpoint/resume functionality
    - Thread-safe operations
    """
    
    # Valid item types
    VALID_ITEM_TYPES = {"snippet", "codebase", "dataset", "documentation"}
    
    # Number of items to collect before auto-saving
    AUTO_SAVE_THRESHOLD = 10
    
    # Batch size for large operations
    BATCH_SIZE = 500
    
    def __init__(self, data_dir: str, use_compression: bool = True):
        """
        Initialize the CodeData manager.
        
        Args:
            data_dir: Directory to store data files
            use_compression: Whether to compress large data files
        """
        self.data_dir = data_dir
        self.use_compression = use_compression
        self.current_data = {}
        self.global_hashes = set()
        self.dirty_languages = set()  # Track which languages have unsaved changes
        self.lock = Lock()
        self.checkpoint_file = os.path.join(data_dir, "checkpoint.json")
        
        # Ensure data directory exists with proper structure
        self._ensure_directory_structure()
        
        # Load existing data and checkpoint info
        self._load_existing_data()
    
    def _ensure_directory_structure(self):
        """Create necessary directory structure for data storage."""
        try:
            # Create main data directory
            os.makedirs(self.data_dir, exist_ok=True)
            
            # Create subdirectories for each language
            for lang in LANGUAGES:
                lang_dir = os.path.join(self.data_dir, lang)
                os.makedirs(lang_dir, exist_ok=True)
                
            # Create exports directory
            os.makedirs(os.path.join(self.data_dir, "exports"), exist_ok=True)
            
            # Create temp directory for atomic writes
            os.makedirs(os.path.join(self.data_dir, "temp"), exist_ok=True)
            
            logger.debug(f"Directory structure for {self.data_dir} initialized")
        except OSError as e:
            logger.error(f"Failed to create directory structure: {str(e)}")
            raise
    
    def _load_existing_data(self):
        """
        Load existing data from JSON files and checkpoint information.
        Uses incremental loading for large datasets to minimize memory usage.
        """
        logger.info("Loading existing code data...")
        
        # Check for checkpoint to support resume capability
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint_data = json.load(f)
                    logger.info(f"Found checkpoint data: {checkpoint_data}")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Could not load checkpoint data: {str(e)}")
                checkpoint_data = {}
        else:
            checkpoint_data = {}
        
        # Load data for each language
        for lang in LANGUAGES:
            self.current_data[lang] = []
            lang_dir = os.path.join(self.data_dir, lang)
            
            # Look for both regular and compressed data files
            data_file = os.path.join(lang_dir, f"{lang.lower()}_data.json")
            compressed_file = os.path.join(lang_dir, f"{lang.lower()}_data.json.gz")
            
            if os.path.exists(compressed_file) and self.use_compression:
                try:
                    import gzip
                    logger.info(f"Loading compressed data for {lang}")
                    with gzip.open(compressed_file, 'rt', encoding='utf-8') as f:
                        self._load_data_for_language(lang, f)
                except Exception as e:
                    logger.error(f"Error loading compressed data for {lang}: {str(e)}")
                    self.current_data[lang] = []
                    
            elif os.path.exists(data_file):
                try:
                    logger.info(f"Loading data for {lang}")
                    with open(data_file, 'r', encoding='utf-8') as f:
                        self._load_data_for_language(lang, f)
                except Exception as e:
                    logger.error(f"Error loading data for {lang}: {str(e)}")
                    self.current_data[lang] = []
            else:
                logger.info(f"No existing data found for {lang}")
                
        logger.info(f"Loaded {len(self.global_hashes)} unique items across all languages")
    
    def _load_data_for_language(self, language: str, file_handle):
        """
        Load data for a specific language from a file handle.
        
        Args:
            language: Language to load data for
            file_handle: File handle to read from
        """
        try:
            # Read and parse data incrementally for large files
            self.current_data[language] = []
            items_added = 0
            
            # Simple file size check to decide if we need incremental loading
            position = file_handle.tell()
            file_handle.seek(0, os.SEEK_END)
            file_size = file_handle.tell()
            file_handle.seek(position)
            
            # For large files, use incremental loading to reduce memory usage
            if file_size > 10 * 1024 * 1024:  # 10MB
                logger.info(f"Using incremental loading for large {language} data file ({file_size/1024/1024:.2f}MB)")
                
                # Loop through the file and parse JSON incrementally
                import ijson  # Incremental JSON parser
                
                for item in ijson.items(file_handle, 'item'):
                    if self._validate_item(item):
                        self.current_data[language].append(item)
                        self.global_hashes.add(item["id"])
                        items_added += 1
            else:
                # For smaller files, load all at once
                data = json.load(file_handle)
                
                for item in data:
                    if self._validate_item(item):
                        self.current_data[language].append(item)
                        self.global_hashes.add(item["id"])
                        items_added += 1
            
            logger.info(f"Loaded {items_added} valid items for {language}")
            
        except (json.JSONDecodeError, ijson.JSONError) as e:
            logger.warning(f"Error parsing JSON data for {language}: {str(e)}")
            self.current_data[language] = []
    
    def _validate_item(self, item: Dict) -> bool:
        """
        Validate an item to ensure it has all required fields and proper data types.
        
        Args:
            item: The item to validate
            
        Returns:
            True if item is valid, False otherwise
        """
        # Check for required fields
        required_fields = {"id", "type", "language", "content", "source_url", "timestamp"}
        if not all(field in item for field in required_fields):
            logger.debug(f"Item missing required fields: {set(item.keys())}")
            return False
        
        # Check for valid item type
        if item["type"] not in self.VALID_ITEM_TYPES:
            logger.debug(f"Invalid item type: {item['type']}")
            return False
        
        # Check for valid language
        if item["language"] not in LANGUAGES:
            logger.debug(f"Invalid language: {item['language']}")
            return False
        
        # Check for non-empty content
        if not item["content"] or not isinstance(item["content"], str):
            logger.debug("Empty or invalid content")
            return False
        
        # Check for valid URL
        if not item["source_url"] or not isinstance(item["source_url"], str):
            logger.debug("Invalid source URL")
            return False
        
        # All checks passed
        return True
    
    def _sanitize_content(self, content: str) -> str:
        """
        Sanitize content to remove control characters and normalize whitespace.
        
        Args:
            content: The content to sanitize
            
        Returns:
            Sanitized content string
        """
        if not content:
            return ""
        
        # Replace null bytes and other control characters
        content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', content)
        
        # Normalize line endings
        content = content.replace('\r\n', '\n').replace('\r', '\n')
        
        # Truncate extremely long content to prevent memory issues
        if len(content) > 1_000_000:  # 1MB limit
            logger.warning(f"Truncating extremely long content ({len(content)} chars)")
            content = content[:1_000_000] + "\n... [content truncated]"
            
        return content
    
    def _generate_item_id(self, item: Dict) -> str:
        """
        Generate a unique ID for an item based on its content and source URL.
        
        Args:
            item: Dictionary containing item data
            
        Returns:
            MD5 hash as hex string
        """
        content = item.get('content', '')
        url = item.get('source_url', '')
        lang = item.get('language', '')
        
        # Use both content and URL to ensure uniqueness
        input_str = f"{content}{url}{lang}"
        
        # Use a secure hash function
        return hashlib.sha256(input_str.encode('utf-8')).hexdigest()
    
    def add_item(self, language: str, item_type: str, content: str, 
                source_url: str, metadata: Dict = None) -> bool:
        """
        Add a new code item to the dataset.
        
        Args:
            language: Programming language of the code
            item_type: Type of item (snippet, codebase, etc)
            content: The code content
            source_url: URL where the code was found
            metadata: Additional metadata for the item
            
        Returns:
            True if item was added, False if it was a duplicate or invalid
        """
        # Validate inputs
        if language not in LANGUAGES:
            logger.warning(f"Skipping item with unsupported language: {language}")
            return False
        
        if item_type not in self.VALID_ITEM_TYPES:
            logger.warning(f"Skipping item with invalid type: {item_type}")
            return False
        
        if not content or not source_url:
            logger.warning("Skipping item with empty content or URL")
            return False
        
        # Sanitize content
        content = self._sanitize_content(content)
        if not content:
            logger.warning("Skipping item with empty content after sanitization")
            return False
        
        # Create and initialize item dictionary
        item = {
            "type": item_type,
            "language": language,
            "content": content,
            "source_url": source_url,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "metadata": metadata or {}
        }
        
        # Generate a unique ID
        item_id = self._generate_item_id(item)
        item["id"] = item_id
        
        # Thread-safe add operation
        with self.lock:
            # Check for duplicates
            if item_id in self.global_hashes:
                logger.debug(f"Skipping duplicate item with ID {item_id}")
                return False
            
            # Initialize language data if needed
            if language not in self.current_data:
                self.current_data[language] = []
            
            # Add the item
            self.global_hashes.add(item_id)
            self.current_data[language].append(item)
            self.dirty_languages.add(language)
            
            # Create checkpoint info for resume capability
            self._update_checkpoint()
            
            # Log success
            logger.info(f"Added new {item_type} for {language} from {source_url[:50]}...")
            
            # Auto-save periodically
            if len(self.current_data[language]) % self.AUTO_SAVE_THRESHOLD == 0:
                self.save_data(language)
                
        return True
    
    def _update_checkpoint(self):
        """Update checkpoint file for resume capability."""
        checkpoint_data = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "items_collected": {lang: len(items) for lang, items in self.current_data.items() if items},
            "total_items": len(self.global_hashes)
        }
        
        try:
            # Write to temp file first, then rename for atomic operation
            temp_file = f"{self.checkpoint_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(checkpoint_data, f)
            
            # Atomic rename
            import os
            os.replace(temp_file, self.checkpoint_file)
        except Exception as e:
            logger.error(f"Error updating checkpoint file: {str(e)}")
    
    def save_data(self, language: str = None):
        """
        Save collected data to JSON files.
        
        Args:
            language: Specific language to save, or all if None
        """
        with self.lock:
            languages_to_save = [language] if language else list(self.dirty_languages)
            
            if not languages_to_save:
                logger.debug("No data to save")
                return
            
            for lang in languages_to_save:
                if lang not in self.current_data or not self.current_data[lang]:
                    continue
                
                items = self.current_data[lang]
                lang_dir = os.path.join(self.data_dir, lang)
                lang_file = os.path.join(lang_dir, f"{lang.lower()}_data.json")
                temp_file = os.path.join(self.data_dir, "temp", f"{lang.lower()}_data.json.tmp")
                
                try:
                    # Determine whether to use compression
                    use_compression = self.use_compression and len(items) > 1000
                    
                    # Write to temp file first for atomic operation
                    if use_compression:
                        import gzip
                        compressed_file = f"{lang_file}.gz"
                        logger.info(f"Saving {len(items)} items for {lang} (compressed)")
                        
                        with gzip.open(temp_file + '.gz', 'wt', encoding='utf-8') as f:
                            json.dump(items, f, ensure_ascii=False)
                        
                        # Atomic rename
                        os.replace(temp_file + '.gz', compressed_file)
                        
                        # Remove uncompressed version if it exists
                        if os.path.exists(lang_file):
                            os.remove(lang_file)
                    else:
                        logger.info(f"Saving {len(items)} items for {lang}")
                        
                        with open(temp_file, 'w', encoding='utf-8') as f:
                            json.dump(items, f, ensure_ascii=False)
                        
                        # Atomic rename
                        os.replace(temp_file, lang_file)
                        
                        # Remove compressed version if it exists
                        compressed_file = f"{lang_file}.gz"
                        if os.path.exists(compressed_file):
                            os.remove(compressed_file)
                    
                    # Mark language as clean (saved)
                    if lang in self.dirty_languages:
                        self.dirty_languages.remove(lang)
                        
                except Exception as e:
                    logger.error(f"Error saving data for {lang}: {str(e)}")
    
    def export_dataset(self, split_by_language: bool = True, max_file_size: int = 100 * 1024 * 1024):
        """
        Export all collected data into dataset files.
        
        Args:
            split_by_language: Whether to split dataset by language
            max_file_size: Maximum file size before splitting in bytes (default 100MB)
        """
        logger.info("Exporting dataset...")
        
        # First, ensure all data is saved
        self.save_data()
        
        exports_dir = os.path.join(self.data_dir, "exports")
        os.makedirs(exports_dir, exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        # Strategy depends on whether we're splitting by language
        if split_by_language:
            for lang in LANGUAGES:
                if lang not in self.current_data or not self.current_data[lang]:
                    continue
                
                items = self.current_data[lang]
                if not items:
                    continue
                
                # Split into chunks if needed
                total_chunks = max(1, len(items) // self.BATCH_SIZE)
                
                if total_chunks == 1:
                    # Single file export
                    output_file = os.path.join(exports_dir, f"{lang.lower()}_dataset_{timestamp}.json")
                    
                    try:
                        # Determine if compression is needed
                        estimated_size = len(json.dumps(items[:100])) * len(items) / 100
                        use_compression = self.use_compression and estimated_size > max_file_size
                        
                        if use_compression:
                            import gzip
                            output_file += ".gz"
                            with gzip.open(output_file, 'wt', encoding='utf-8') as f:
                                json.dump(items, f, ensure_ascii=False)
                        else:
                            with open(output_file, 'w', encoding='utf-8') as f:
                                json.dump(items, f, ensure_ascii=False)
                                
                        logger.info(f"Exported {len(items)} items for {lang} to {output_file}")
                        
                    except Exception as e:
                        logger.error(f"Error exporting data for {lang}: {str(e)}")
                        
                else:
                    # Multi-file export
                    for chunk_idx in range(total_chunks):
                        start_idx = chunk_idx * self.BATCH_SIZE
                        end_idx = min(start_idx + self.BATCH_SIZE, len(items))
                        chunk = items[start_idx:end_idx]
                        
                        output_file = os.path.join(
                            exports_dir, 
                            f"{lang.lower()}_dataset_{timestamp}_part{chunk_idx+1}of{total_chunks}.json"
                        )
                        
                        try:
                            # Always use compression for multi-part exports
                            if self.use_compression:
                                import gzip
                                output_file += ".gz"
                                with gzip.open(output_file, 'wt', encoding='utf-8') as f:
                                    json.dump(chunk, f, ensure_ascii=False)
                            else:
                                with open(output_file, 'w', encoding='utf-8') as f:
                                    json.dump(chunk, f, ensure_ascii=False)
                                    
                            logger.info(f"Exported {len(chunk)} items for {lang} (part {chunk_idx+1}/{total_chunks})")
                            
                        except Exception as e:
                            logger.error(f"Error exporting data chunk for {lang}: {str(e)}")
        else:
            # Combined dataset export
            all_items = []
            for lang in LANGUAGES:
                if lang in self.current_data:
                    all_items.extend(self.current_data[lang])
            
            if not all_items:
                logger.warning("No items to export")
                return
            
            # Split into chunks if needed based on estimated size
            sample_size = min(100, len(all_items))
            estimated_size_per_item = len(json.dumps(all_items[:sample_size])) / sample_size
            estimated_total_size = estimated_size_per_item * len(all_items)
            
            total_chunks = max(1, int(estimated_total_size / max_file_size) + 1)
            items_per_chunk = len(all_items) // total_chunks + 1
            
            logger.info(f"Exporting {len(all_items)} total items in {total_chunks} chunks")
            
            for chunk_idx in range(total_chunks):
                start_idx = chunk_idx * items_per_chunk
                end_idx = min(start_idx + items_per_chunk, len(all_items))
                
                if start_idx >= len(all_items):
                    break
                    
                chunk = all_items[start_idx:end_idx]
                
                # Create filename
                if total_chunks == 1:
                    output_file = os.path.join(exports_dir, f"complete_dataset_{timestamp}.json")
                else:
                    output_file = os.path.join(
                        exports_dir, 
                        f"complete_dataset_{timestamp}_part{chunk_idx+1}of{total_chunks}.json"
                    )
                
                try:
                    # Use compression for larger datasets
                    if self.use_compression and len(chunk) > 1000:
                        import gzip
                        output_file += ".gz"
                        with gzip.open(output_file, 'wt', encoding='utf-8') as f:
                            json.dump(chunk, f, ensure_ascii=False)
                    else:
                        with open(output_file, 'w', encoding='utf-8') as f:
                            json.dump(chunk, f, ensure_ascii=False)
                            
                    logger.info(f"Exported {len(chunk)} items to {output_file}")
                    
                except Exception as e:
                    logger.error(f"Error exporting data chunk: {str(e)}")
        
        logger.info(f"Dataset export completed with {len(self.global_hashes)} total items")

class LanguageDetector:
    """
    Utility class to detect programming languages from code samples or file paths.
    
    Features:
    - Enhanced pattern recognition for language detection
    - Caching for improved performance
    - More comprehensive language patterns
    - Weighted scoring system for better accuracy
    - Content-based heuristics
    """
    
    # Compile patterns once for better performance
    EXTENSION_CACHE = {}
    PATTERN_CACHE = {}
    
    # More sophisticated patterns for language detection
    LANGUAGE_PATTERNS = {
        "Swift": [
            (r'import\s+Foundation', 3),
            (r'import\s+UIKit', 3),
            (r'import\s+SwiftUI', 4),
            (r'func\s+\w+\s*\([^)]*\)\s*->\s*\w+', 2),
            (r'class\s+\w+\s*:\s*\w+', 2),
            (r'var\s+\w+\s*:\s*\w+', 1),
            (r'let\s+\w+\s*:\s*\w+', 1),
            (r'@objc', 2),
            (r'guard\s+let', 3)
        ],
        "Python": [
            (r'import\s+\w+', 1),
            (r'from\s+[\w.]+\s+import', 2),
            (r'def\s+\w+\s*\(', 2),
            (r'if\s+__name__\s*==\s*[\'"]__main__[\'"]', 4),
            (r'class\s+\w+(?:\(.*?\))?:', 2),
            (r'with\s+.*?\s+as\s+', 3),
            (r'^\s*@\w+', 2),  # Decorators
            (r'try:(?:\s+.*?)?except', 3),
            (r'yield\s+', 3),
            (r'async\s+def|await\s+', 3)
        ],
        "C": [
            (r'#include\s+<[a-z0-9_]+\.h>', 3),
            (r'int\s+main\s*\(\s*(?:void|int\s+argc,\s*char\s*\*\s*argv\[\])\s*\)', 4),
            (r'void\s+\w+\s*\([^)]*\)', 2),
            (r'#define\s+\w+', 2),
            (r'typedef\s+struct', 3),
            (r'malloc\s*\(|free\s*\(', 3),
            (r'printf\s*\(|sprintf\s*\(|fprintf\s*\(', 2),
            (r'char\s+\w+\[', 2)
        ],
        "C++": [
            (r'#include\s+<iostream>', 3),
            (r'#include\s+<vector>', 3),
            (r'#include\s+<string>', 2),
            (r'namespace\s+\w+', 3),
            (r'std::', 3),
            (r'template\s*<', 4),
            (r'class\s+\w+\s*(?::\s*\w+)?(?:\s*{)?', 2),
            (r'virtual\s+\w+', 3),
            (r'public:|private:|protected:', 3),
            (r'new\s+\w+|delete\s+\w+', 2),
            (r'cout\s*<<|cin\s*>>', 3)
        ],
        "JavaScript": [
            (r'const\s+\w+\s*=', 2),
            (r'let\s+\w+\s*=', 2),
            (r'var\s+\w+\s*=', 1),
            (r'function\s+\w+\s*\(', 2),
            (r'addEventListener', 3),
            (r'document\.', 3),
            (r'window\.', 2),
            (r'=>', 1),
            (r'console\.log', 1),
            (r'new\s+Promise', 3),
            (r'async\s+function|await\s+', 3),
            (r'import\s+{[^}]*}\s+from', 3),
            (r'export\s+(?:default\s+)?(?:function|class|const)', 3)
        ],
        "TypeScript": [
            (r'interface\s+\w+', 4),
            (r':\s*(?:string|number|boolean|any)\b', 3),
            (r'<\w+>', 2),
            (r'class\s+\w+(?:<[^>]+>)?(?:\s+implements\s+\w+)?', 3),
            (r'private\s+\w+\s*:', 3),
            (r'public\s+\w+\s*:', 3),
            (r'protected\s+\w+\s*:', 3),
            (r'readonly\s+', 3),
            (r'namespace\s+\w+', 3),
            (r'enum\s+\w+', 3),
            (r'type\s+\w+\s*=', 4),
            (r'import\s+{[^}]*}\s+from', 2)
        ],
        "Ruby": [
            (r'require\s+[\'"]\w+[\'"]', 3),
            (r'def\s+\w+\s*(?:\(|$)', 3),
            (r'end$', 1),
            (r'module\s+\w+', 3),
            (r'class\s+\w+\s*(?:<\s*\w+)?', 3),
            (r'attr_accessor\s+:|\w+', 3),
            (r'do\s+\|[^|]+\|', 3),
            (r'=>', 1),
            (r'puts\s+|p\s+', 1),
            (r'lambda\s+{|->(?:\([^)]*\))?\s*{', 3)
        ],
        "C#": [
            (r'using\s+System', 3),
            (r'namespace\s+\w+', 3),
            (r'public\s+class\s+\w+', 3),
            (r'private\s+\w+\s+\w+\s*\{', 2),
            (r'internal\s+\w+', 3),
            (r'virtual\s+\w+', 3),
            (r'override\s+\w+', 3),
            (r'public\s+(?:static\s+)?void\s+Main', 4),
            (r'Console\.Write', 2),
            (r'IEnumerable<|List<', 3),
            (r'async\s+Task', 3)
        ],
        "Objective-C": [
            (r'#import\s+[<"]\w+\.h[>"]', 3),
            (r'@interface\s+\w+\s*:\s*\w+', 4),
            (r'@implementation\s+\w+', 4),
            (r'@property\s+\(\w+\)', 3),
            (r'@selector\(', 3),
            (r'@end', 2),
            (r'NSString\s*\*|NSArray\s*\*|NSDictionary\s*\*', 3),
            (r'\[\w+\s+\w+\]', 2),
            (r'^-\s*\(\w+\)', 3),
            (r'^[+]\s*\(\w+\)', 3)
        ],
        "Lua": [
            (r'function\s+\w+\s*\(', 3),
            (r'local\s+\w+\s*=', 2),
            (r'end$', 1),
            (r'require\s*\(?[\'"][^\'"]+[\'"]\)?', 3),
            (r'if\s+.+\s+then', 2),
            (r'elseif\s+.+\s+then', 3),
            (r'for\s+\w+\s*=\s*\d+\s*,\s*\d+', 3),
            (r'pairs\(|ipairs\(', 2),
            (r'while\s+.+\s+do', 2),
            (r'module\s*\(?[\'"][^\'"]+[\'"]\)?', 3)
        ]
    }
    
    @classmethod
    @lru_cache(maxsize=1024)
    def detect_from_extension(cls, file_path: str) -> Optional[str]:
        """
        Detect language based on file extension with caching.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Detected language or None if not detected
        """
        # Skip if no path or it's a directory
        if not file_path or file_path.endswith('/'):
            return None
        
        # Get extension, lowercase for consistency
        _, ext = os.path.splitext(file_path.lower())
        if not ext:
            return None
            
        # Check cache first
        if ext in cls.EXTENSION_CACHE:
            return cls.EXTENSION_CACHE[ext]
            
        # Find matching language
        for lang, extensions in LANGUAGE_FILE_EXTENSIONS.items():
            if ext in extensions:
                cls.EXTENSION_CACHE[ext] = lang
                return lang
        
        # No match found
        cls.EXTENSION_CACHE[ext] = None
        return None
    
    @classmethod
    @lru_cache(maxsize=128)
    def detect_from_content(cls, content: str, min_confidence: float = 0.6) -> Optional[str]:
        """
        Detect programming language from code content using a weighted pattern matching approach.
        
        Args:
            content: Code content to analyze
            min_confidence: Minimum confidence threshold (0.0-1.0)
            
        Returns:
            Detected language or None if confidence is below threshold
        """
        # Skip empty content
        if not content or len(content.strip()) < 10:
            return None
        
        # Take a sample for large content to improve performance
        if len(content) > 10000:
            # Sample the beginning, middle, and end
            begin = content[:3000]
            middle_start = max(0, (len(content) // 2) - 1500)
            middle = content[middle_start:middle_start + 3000]
            end = content[-3000:]
            sample = begin + "\n" + middle + "\n" + end
        else:
            sample = content
        
        # Calculate scores for each language
        scores = {}
        max_possible_scores = {}
        
        for lang, patterns in cls.LANGUAGE_PATTERNS.items():
            scores[lang] = 0
            max_possible_scores[lang] = sum(weight for _, weight in patterns)
            
            for pattern, weight in patterns:
                # Compile regex if needed
                if pattern not in cls.PATTERN_CACHE:
                    cls.PATTERN_CACHE[pattern] = re.compile(pattern, re.MULTILINE)
                
                regex = cls.PATTERN_CACHE[pattern]
                
                # Check if pattern exists, weight by number of matches with a cap
                matches = len(regex.findall(sample))
                if matches > 0:
                    # Cap the score increase to avoid over-counting repetitive patterns
                    score_increase = min(matches, 3) * weight
                    scores[lang] += score_increase
        
        # Calculate confidence scores (normalized)
        confidence_scores = {}
        for lang in scores:
            if max_possible_scores[lang] > 0:
                confidence_scores[lang] = scores[lang] / max_possible_scores[lang]
            else:
                confidence_scores[lang] = 0
        
        # Find the language with the highest confidence score
        if confidence_scores:
            best_lang = max(confidence_scores.items(), key=lambda x: x[1])
            lang_name, confidence = best_lang
            
            # Only return if confidence is above the threshold
            if confidence >= min_confidence:
                return lang_name
        
        # Apply heuristics for additional detection
        return cls._apply_heuristics(content)
    
    @classmethod
    def _apply_heuristics(cls, content: str) -> Optional[str]:
        """
        Apply additional heuristics for language detection when pattern matching is inconclusive.
        
        Args:
            content: Code content to analyze
            
        Returns:
            Detected language or None
        """
        # Count common language-specific markers
        markers = {
            "Python": ["def ", "import ", "class ", "if __name__", "print(", "yield ", "except:", "# ", """""],
            "JavaScript": ["const ", "function(", "var ", "let ", "document.", "() =>", "// ", "*/"],
            "TypeScript": ["interface ", "type ", ": string", ": number", ": boolean", "export class"],
            "C++": ["#include", "namespace", "template<", "::", "std::", "//"],
            "C#": ["using System", "namespace ", "public class", "private ", "internal ", "//"],
            "Ruby": ["require ", "def ", "end", "module ", "class ", "# "]
        }
        
        scores = {lang: 0 for lang in markers}
        
        # Count occurrences of each marker
        for lang, lang_markers in markers.items():
            for marker in lang_markers:
                occurrences = content.count(marker)
                if occurrences > 0:
                    scores[lang] += min(occurrences, 5)  # Cap at 5 to avoid bias
        
        # Check if we have a clear winner
        max_score = max(scores.values()) if scores else 0
        if max_score > 5:  # Arbitrary threshold
            best_langs = [lang for lang, score in scores.items() if score == max_score]
            if best_langs:
                return best_langs[0]
        
        return None
    
    @classmethod
    def detect_language(cls, content: str = None, file_path: str = None) -> Optional[str]:
        """
        Comprehensive language detection using both file extension and content.
        
        Args:
            content: Code content (optional)
            file_path: File path (optional)
            
        Returns:
            Detected language or None
        
        Note:
            At least one of content or file_path must be provided
        """
        if not content and not file_path:
            return None
            
        # First try file extension if available
        if file_path:
            lang = cls.detect_from_extension(file_path)
            if lang:
                return lang
                
        # Fall back to content analysis
        if content:
            return cls.detect_from_content(content)
            
        return None

class BaseScraper:
    """Base class for platform-specific scrapers."""
    
    def __init__(self, scraper_api_client: ScraperAPIClient, oxylabs_client: OxylabsClient, code_data: CodeData):
        self.scraper_api_client = scraper_api_client
        self.oxylabs_client = oxylabs_client
        self.code_data = code_data
        self.visited_urls = set()
        self.lock = Lock()
        self.api_selector = 0
    
    def _select_api(self) -> tuple:
        """Select the next API to use in a round-robin fashion."""
        with self.lock:
            self.api_selector = (self.api_selector + 1) % 2
            return (self.scraper_api_client, "ScraperAPI") if self.api_selector == 0 else (self.oxylabs_client, "Oxylabs")
    
    def is_url_visited(self, url: str) -> bool:
        """Check if URL has already been visited."""
        with self.lock:
            return url in self.visited_urls
    
    def mark_url_visited(self, url: str):
        """Mark URL as visited."""
        with self.lock:
            self.visited_urls.add(url)
    
    def extract_code_blocks(self, html_content: str) -> List[Tuple[str, Optional[str]]]:
        """
        Extract code blocks from HTML content.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        code_blocks = []
        
        for pre in soup.find_all('pre'):
            code = pre.find('code')
            if code:
                language = None
                if code.get('class'):
                    class_list = code.get('class')
                    lang_classes = [c for c in class_list if c.startswith(('language-', 'lang-'))]
                    if lang_classes:
                        lang_class = lang_classes[0]
                        detected_lang = lang_class.split('-', 1)[1]
                        language = next((l for l in LANGUAGES if l.lower() == detected_lang.lower()), None)
                
                if not language and code.text:
                    language = LanguageDetector.detect_from_content(code.text)
                
                code_blocks.append((code.text.strip(), language))
        
        for code in soup.find_all('code', class_=True):
            if code.parent.name != 'pre':
                class_list = code.get('class')
                language = None
                
                if class_list:
                    lang_classes = [c for c in class_list if c.startswith(('language-', 'lang-'))]
                    if lang_classes:
                        lang_class = lang_classes[0]
                        detected_lang = lang_class.split('-', 1)[1]
                        language = next((l for l in LANGUAGES if l.lower() == detected_lang.lower()), None)
                
                if not language and code.text:
                    language = LanguageDetector.detect_from_content(code.text)
                
                code_blocks.append((code.text.strip(), language))
        
        return code_blocks

class GitHubScraper(BaseScraper):
    """Scraper for GitHub repositories and snippets."""
    
    def search_repositories(self, language: str, max_pages: int = 10):
        """Search for repositories in a specific language."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for page in range(1, max_pages + 1):
                search_url = f"https://github.com/search?q=language%3A{language.lower()}&type=repositories&p={page}"
                api_client, api_name = self._select_api()
                futures.append(executor.submit(self._process_search_page, search_url, language, api_client, api_name))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing GitHub search page: {str(e)}")
    
    def _process_search_page(self, search_url: str, language: str, api_client, api_name: str):
        """Process a single search page."""
        response = api_client.get(search_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        repo_elements = soup.select('.repo-list-item')
        
        for repo_element in repo_elements:
            repo_link = repo_element.select_one('a[href^="/"]')
            if not repo_link:
                continue
            
            repo_url = urljoin("https://github.com", repo_link['href'])
            
            if self.is_url_visited(repo_url):
                continue
            
            description_elem = repo_element.select_one('p')
            description = description_elem.get_text().strip() if description_elem else ""
            
            metadata = {
                "name": repo_link.get_text().strip(),
                "description": description,
                "stars": 0,
                "forks": 0,
                "platform": "GitHub"
            }
            
            self.visit_repository(repo_url, language, metadata)
            self.mark_url_visited(repo_url)
            time.sleep(random.uniform(1.0, 3.0))
    
    def visit_repository(self, repo_url: str, language: str, metadata: Dict):
        """Visit a repository to extract code samples and additional metadata."""
        api_client, api_name = self._select_api()
        response = api_client.get(repo_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        try:
            stars_elem = soup.select_one('a[href$="/stargazers"]')
            if stars_elem:
                stars_text = stars_elem.get_text().strip().replace(',', '')
                metadata['stars'] = int(stars_text) if stars_text.isdigit() else 0
                
            forks_elem = soup.select_one('a[href$="/forks"]')
            if forks_elem:
                forks_text = forks_elem.get_text().strip().replace(',', '')
                metadata['forks'] = int(forks_text) if forks_text.isdigit() else 0
        except Exception as e:
            logger.error(f"Error extracting repo metadata: {str(e)}")
        
        self.code_data.add_item(
            language=language,
            item_type="codebase",
            content=f"GitHub repository: {metadata.get('name', 'Unknown')}",
            source_url=repo_url,
            metadata=metadata
        )
        
        self._explore_repo_files(repo_url, language)
    
    def _explore_repo_files(self, repo_url: str, primary_language: str, path: str = "", max_depth: int = 2, current_depth: int = 0):
        """Recursively explore repository files to extract code."""
        if current_depth > max_depth:
            return
        
        explore_url = repo_url if not path else f"{repo_url}/tree/master/{path}"
        api_client, api_name = self._select_api()
        response = api_client.get(explore_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        file_items = soup.select('a[role="row"]')
        
        for item in file_items:
            item_type = "file" if "blob" in str(item) else "directory"
            item_link = item.get('href')
            
            if not item_link:
                continue
                
            item_name = item_link.split("/")[-1]
            item_path = path + "/" + item_name if path else item_name
            item_url = urljoin("https://github.com", item_link)
            
            if self.is_url_visited(item_url):
                continue
            
            if item_type == "file":
                detected_language = LanguageDetector.detect_from_extension(item_name)
                if detected_language:
                    self._extract_file_content(item_url, detected_language)
            elif item_type == "directory" and current_depth < max_depth:
                self._explore_repo_files(repo_url, primary_language, item_path, max_depth, current_depth + 1)
            
            self.mark_url_visited(item_url)
            time.sleep(random.uniform(0.5, 1.5))
    
    def _extract_file_content(self, file_url: str, language: str):
        """Extract code content from a GitHub file."""
        api_client, api_name = self._select_api()
        response = api_client.get(file_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        code_element = soup.select_one('table.highlight')
        if not code_element:
            return
        
        code_lines = []
        for line in code_element.select('tr'):
            line_content = line.select_one('td.blob-code')
            if line_content:
                code_lines.append(line_content.get_text(strip=True))
                
        code_content = "\n".join(code_lines)
        
        if not code_content.strip():
            return
        
        filename = file_url.split("/")[-1]
        
        self.code_data.add_item(
            language=language,
            item_type="snippet",
            content=code_content,
            source_url=file_url,
            metadata={
                "filename": filename,
                "repo_url": "/".join(file_url.split("/")[:5]),
                "platform": "GitHub"
            }
        )

class StackOverflowScraper(BaseScraper):
    """Scraper for Stack Overflow code snippets."""
    
    def search_questions(self, language: str, max_pages: int = 10):
        """Search for questions related to a specific language."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for page in range(1, max_pages + 1):
                search_url = f"https://stackoverflow.com/questions/tagged/{language.lower()}?tab=votes&page={page}"
                api_client, api_name = self._select_api()
                futures.append(executor.submit(self._process_question_page, search_url, language, api_client, api_name))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing Stack Overflow page: {str(e)}")
    
    def _process_question_page(self, search_url: str, language: str, api_client, api_name: str):
        """Process a single question page."""
        response = api_client.get(search_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        question_summaries = soup.select('.s-post-summary')
        
        for summary in question_summaries:
            link_elem = summary.select_one('a.s-link')
            if not link_elem:
                continue
            
            question_url = urljoin("https://stackoverflow.com", link_elem['href'])
            
            if self.is_url_visited(question_url):
                continue
            
            title = link_elem.get_text().strip()
            self.extract_from_question(question_url, language, title)
            self.mark_url_visited(question_url)
            time.sleep(random.uniform(1.0, 3.0))
    
    def extract_from_question(self, question_url: str, language: str, title: str):
        """Extract code snippets from a question page."""
        api_client, api_name = self._select_api()
        response = api_client.get(question_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        post_elements = soup.select('.js-post-body')
        
        for post_idx, post in enumerate(post_elements):
            code_blocks = self.extract_code_blocks(str(post))
            
            for idx, (code, detected_lang) in enumerate(code_blocks):
                if not code.strip():
                    continue
                
                code_language = detected_lang if detected_lang else language
                if code_language not in LANGUAGES:
                    continue
                
                post_type = "question" if post_idx == 0 else "answer"
                
                self.code_data.add_item(
                    language=code_language,
                    item_type="snippet",
                    content=code,
                    source_url=question_url,
                    metadata={
                        "title": title,
                        "post_type": post_type,
                        "platform": "Stack Overflow"
                    }
                )

class RedditScraper(BaseScraper):
    """Scraper for Reddit code snippets."""
    
    def search_subreddits(self, language: str, max_pages: int = 5):
        """Search for code in programming subreddits."""
        language_subreddits = {
            "Python": ["Python", "learnpython", "pythontips"],
            "JavaScript": ["javascript", "learnjavascript", "reactjs"],
            "TypeScript": ["typescript", "angular"],
            "Ruby": ["ruby", "rails"],
            "C": ["C_Programming", "cprogramming"],
            "C++": ["cpp", "cpp_questions"],
            "C#": ["csharp", "dotnet"],
            "Swift": ["swift", "iOSProgramming"],
            "Objective-C": ["ObjectiveC", "iOSProgramming"],
            "Lua": ["lua", "gamedev"]
        }
        
        subreddits = language_subreddits.get(language, [language.lower()])
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for subreddit in subreddits:
                for sort in ["top", "hot"]:
                    search_url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit=25"
                    api_client, api_name = self._select_api()
                    futures.append(executor.submit(self._process_subreddit, search_url, language, api_client, api_name))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing Reddit subreddit: {str(e)}")
    
    def _process_subreddit(self, search_url: str, language: str, api_client, api_name: str):
        """Process a single subreddit."""
        headers = {"User-Agent": "CodeCrawler/1.0"}
        response = api_client.get(search_url)
        if not response:
            return
        
        try:
            data = response.json()
            posts = data.get("data", {}).get("children", [])
            
            for post in posts:
                post_data = post.get("data", {})
                permalink = post_data.get("permalink")
                
                if not permalink:
                    continue
                
                post_url = f"https://www.reddit.com{permalink}"
                
                if self.is_url_visited(post_url):
                    continue
                
                self.extract_from_post(post_url, language)
                self.mark_url_visited(post_url)
                time.sleep(random.uniform(1.0, 3.0))
                
        except Exception as e:
            logger.error(f"Error processing Reddit data: {str(e)}")
    
    def extract_from_post(self, post_url: str, language: str):
        """Extract code snippets from a Reddit post."""
        api_client, api_name = self._select_api()
        response = api_client.get(post_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        title_elem = soup.select_one('h1')
        title = title_elem.get_text().strip() if title_elem else "Unknown Title"
        
        post_elements = soup.select('.usertext-body')
        
        for post in post_elements:
            code_blocks = self.extract_code_blocks(str(post))
            
            for code, detected_lang in code_blocks:
                if not code.strip():
                    continue
                
                code_language = detected_lang if detected_lang else language
                if code_language not in LANGUAGES:
                    continue
                
                self.code_data.add_item(
                    language=code_language,
                    item_type="snippet",
                    content=code,
                    source_url=post_url,
                    metadata={
                        "title": title,
                        "platform": "Reddit"
                    }
                )

class PastebinScraper(BaseScraper):
    """Scraper for Pastebin code snippets."""
    
    def search_recent_pastes(self, language: str, max_pages: int = 5):
        """Search for code in recent public pastes."""
        language_map = {
            "Python": "python",
            "JavaScript": "javascript",
            "TypeScript": "typescript",
            "Ruby": "ruby",
            "C": "c",
            "C++": "cpp",
            "C#": "csharp",
            "Swift": "swift",
            "Objective-C": "objectivec",
            "Lua": "lua"
        }
        
        pastebin_lang = language_map.get(language, language.lower())
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for page in range(1, max_pages + 1):
                search_url = f"https://pastebin.com/archive/{pastebin_lang}?page={page}"
                api_client, api_name = self._select_api()
                futures.append(executor.submit(self._process_paste_page, search_url, language, pastebin_lang, api_client, api_name))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing Pastebin page: {str(e)}")
    
    def _process_paste_page(self, search_url: str, language: str, pastebin_lang: str, api_client, api_name: str):
        """Process a single Pastebin archive page."""
        response = api_client.get(search_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        paste_elements = soup.select('table.maintable tr')
        
        for paste in paste_elements[1:]:
            try:
                cells = paste.find_all('td')
                if len(cells) < 3:
                    continue
                
                link_elem = cells[0].find('a')
                paste_lang_elem = cells[2]
                
                if not link_elem or not paste_lang_elem:
                    continue
                
                paste_url = urljoin("https://pastebin.com", link_elem['href'])
                paste_lang = paste_lang_elem.get_text().strip().lower()
                
                if self.is_url_visited(paste_url):
                    continue
                
                if pastebin_lang in paste_lang:
                    self.extract_from_paste(paste_url, language)
                
                self.mark_url_visited(paste_url)
                time.sleep(random.uniform(1.0, 2.0))
                
            except Exception as e:
                logger.error(f"Error processing Pastebin element: {str(e)}")
    
    def extract_from_paste(self, paste_url: str, language: str):
        """Extract code from a Pastebin paste."""
        api_client, api_name = self._select_api()
        response = api_client.get(paste_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        title_elem = soup.select_one('.info-top')
        title = title_elem.get_text().strip() if title_elem else "Untitled Paste"
        
        code_elem = soup.select_one('.source') or soup.select_one('.text')
        if not code_elem:
            return
        
        code_content = code_elem.get_text().strip()
        if not code_content:
            return
        
        detected_lang = LanguageDetector.detect_from_content(code_content)
        code_language = detected_lang if detected_lang else language
        
        if code_language not in LANGUAGES:
            return
        
        self.code_data.add_item(
            language=code_language,
            item_type="snippet",
            content=code_content,
            source_url=paste_url,
            metadata={
                "title": title,
                "platform": "Pastebin"
            }
        )

class GitLabScraper(BaseScraper):
    """Scraper for GitLab repositories and snippets."""
    
    def search_repositories(self, language: str, max_pages: int = 10):
        """Search for repositories in a specific language."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for page in range(1, max_pages + 1):
                search_url = f"https://gitlab.com/explore/projects?language={language.lower()}&page={page}"
                api_client, api_name = self._select_api()
                futures.append(executor.submit(self._process_search_page, search_url, language, api_client, api_name))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing GitLab search page: {str(e)}")
    
    def _process_search_page(self, search_url: str, language: str, api_client, api_name: str):
        """Process a single search page."""
        response = api_client.get(search_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        repo_elements = soup.select('.project-row')
        
        for repo_element in repo_elements:
            repo_link = repo_element.select_one('a[href^="/"]')
            if not repo_link:
                continue
            
            repo_url = urljoin("https://gitlab.com", repo_link['href'])
            
            if self.is_url_visited(repo_url):
                continue
            
            description_elem = repo_element.select_one('.project-description')
            description = description_elem.get_text().strip() if description_elem else ""
            
            metadata = {
                "name": repo_link.get_text().strip(),
                "description": description,
                "stars": 0,
                "forks": 0,
                "platform": "GitLab"
            }
            
            self.visit_repository(repo_url, language, metadata)
            self.mark_url_visited(repo_url)
            time.sleep(random.uniform(1.0, 3.0))
    
    def visit_repository(self, repo_url: str, language: str, metadata: Dict):
        """Visit a repository to extract code samples and additional metadata."""
        api_client, api_name = self._select_api()
        response = api_client.get(repo_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        try:
            stars_elem = soup.select_one('.star-count')
            if stars_elem:
                stars_text = stars_elem.get_text().strip().replace(',', '')
                metadata['stars'] = int(stars_text) if stars_text.isdigit() else 0
                
            forks_elem = soup.select_one('.fork-count')
            if forks_elem:
                forks_text = forks_elem.get_text().strip().replace(',', '')
                metadata['forks'] = int(forks_text) if forks_text.isdigit() else 0
        except Exception as e:
            logger.error(f"Error extracting GitLab repo metadata: {str(e)}")
        
        self.code_data.add_item(
            language=language,
            item_type="codebase",
            content=f"GitLab repository: {metadata.get('name', 'Unknown')}",
            source_url=repo_url,
            metadata=metadata
        )
        
        self._explore_repo_files(repo_url, language)
    
    def _explore_repo_files(self, repo_url: str, primary_language: str, path: str = "", max_depth: int = 2, current_depth: int = 0):
        """Recursively explore repository files to extract code."""
        if current_depth > max_depth:
            return
        
        explore_url = repo_url if not path else f"{repo_url}/-/tree/master/{path}"
        api_client, api_name = self._select_api()
        response = api_client.get(explore_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        file_items = soup.select('.tree-item')
        for item in file_items:
            item_link = item.select_one('a')
            if not item_link:
                continue
            
            item_name = item_link.get_text().strip()
            item_url = urljoin("https://gitlab.com", item_link['href'])
            item_type = "file" if "/-/blob/" in item_url else "directory"
            item_path = path + "/" + item_name if path else item_name
            
            if self.is_url_visited(item_url):
                continue
            
            if item_type == "file":
                detected_language = LanguageDetector.detect_from_extension(item_name)
                if detected_language:
                    self._extract_file_content(item_url, detected_language)
            elif item_type == "directory" and current_depth < max_depth:
                self._explore_repo_files(repo_url, primary_language, item_path, max_depth, current_depth + 1)
            
            self.mark_url_visited(item_url)
            time.sleep(random.uniform(0.5, 1.5))
    
    def _extract_file_content(self, file_url: str, language: str):
        """Extract code content from a GitLab file."""
        api_client, api_name = self._select_api()
        response = api_client.get(file_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        code_element = soup.select_one('.file-content code')
        if not code_element:
            return
        
        code_content = code_element.get_text().strip()
        if not code_content:
            return
        
        filename = file_url.split("/")[-1]
        
        self.code_data.add_item(
            language=language,
            item_type="snippet",
            content=code_content,
            source_url=file_url,
            metadata={
                "filename": filename,
                "repo_url": "/".join(file_url.split("/")[:5]),
                "platform": "GitLab"
            }
        )

class BitbucketScraper(BaseScraper):
    """Scraper for Bitbucket repositories and snippets."""
    
    def search_repositories(self, language: str, max_pages: int = 10):
        """Search for repositories in a specific language."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for page in range(1, max_pages + 1):
                search_url = f"https://bitbucket.org/repo/all/{page}?language={language.lower()}"
                api_client, api_name = self._select_api()
                futures.append(executor.submit(self._process_search_page, search_url, language, api_client, api_name))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing Bitbucket search page: {str(e)}")
    
    def _process_search_page(self, search_url: str, language: str, api_client, api_name: str):
        """Process a single search page."""
        response = api_client.get(search_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        repo_elements = soup.select('.repo-list--repo')
        
        for repo_element in repo_elements:
            repo_link = repo_element.select_one('a[href^="/"]')
            if not repo_link:
                continue
            
            repo_url = urljoin("https://bitbucket.org", repo_link['href'])
            
            if self.is_url_visited(repo_url):
                continue
            
            description_elem = repo_element.select_one('.repo-description')
            description = description_elem.get_text().strip() if description_elem else ""
            
            metadata = {
                "name": repo_link.get_text().strip(),
                "description": description,
                "platform": "Bitbucket"
            }
            
            self.visit_repository(repo_url, language, metadata)
            self.mark_url_visited(repo_url)
            time.sleep(random.uniform(1.0, 3.0))
    
    def visit_repository(self, repo_url: str, language: str, metadata: Dict):
        """Visit a repository to extract code samples."""
        api_client, api_name = self._select_api()
        response = api_client.get(repo_url)
        if not response:
            return
        
        self.code_data.add_item(
            language=language,
            item_type="codebase",
            content=f"Bitbucket repository: {metadata.get('name', 'Unknown')}",
            source_url=repo_url,
            metadata=metadata
        )
        
        self._explore_repo_files(repo_url, language)
    
    def _explore_repo_files(self, repo_url: str, primary_language: str, path: str = "", max_depth: int = 2, current_depth: int = 0):
        """Recursively explore repository files to extract code."""
        if current_depth > max_depth:
            return
        
        explore_url = f"{repo_url}/src/master/{path}" if path else f"{repo_url}/src/master/"
        api_client, api_name = self._select_api()
        response = api_client.get(explore_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        file_items = soup.select('.source-table tbody tr')
        
        for item in file_items:
            item_link = item.select_one('a')
            if not item_link:
                continue
            
            item_name = item_link.get_text().strip()
            item_url = urljoin("https://bitbucket.org", item_link['href'])
            item_type = "file" if item.select_one('.file') else "directory"
            item_path = path + "/" + item_name if path else item_name
            
            if self.is_url_visited(item_url):
                continue
            
            if item_type == "file":
                detected_language = LanguageDetector.detect_from_extension(item_name)
                if detected_language:
                    self._extract_file_content(item_url, detected_language)
            elif item_type == "directory" and current_depth < max_depth:
                self._explore_repo_files(repo_url, primary_language, item_path, max_depth, current_depth + 1)
            
            self.mark_url_visited(item_url)
            time.sleep(random.uniform(0.5, 1.5))
    
    def _extract_file_content(self, file_url: str, language: str):
        """Extract code content from a Bitbucket file."""
        api_client, api_name = self._select_api()
        response = api_client.get(file_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        code_element = soup.select_one('.source-view')
        if not code_element:
            return
        
        code_content = code_element.get_text().strip()
        if not code_content:
            return
        
        filename = file_url.split("/")[-1]
        
        self.code_data.add_item(
            language=language,
            item_type="snippet",
            content=code_content,
            source_url=file_url,
            metadata={
                "filename": filename,
                "repo_url": "/".join(file_url.split("/")[:5]),
                "platform": "Bitbucket"
            }
        )

class CodePenScraper(BaseScraper):
    """Scraper for CodePen code snippets (primarily JavaScript/TypeScript)."""
    
    def search_pens(self, language: str, max_pages: int = 5):
        """Search for code pens in a specific language."""
        if language not in ["JavaScript", "TypeScript"]:
            return  # CodePen is primarily for web languages
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for page in range(1, max_pages + 1):
                search_url = f"https://codepen.io/search/pens?q={language.lower()}&page={page}"
                api_client, api_name = self._select_api()
                futures.append(executor.submit(self._process_search_page, search_url, language, api_client, api_name))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing CodePen search page: {str(e)}")
    
    def _process_search_page(self, search_url: str, language: str, api_client, api_name: str):
        """Process a single search page."""
        response = api_client.get(search_url, render=True)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        pen_elements = soup.select('.item-in-list-view')
        
        for pen_element in pen_elements:
            pen_link = pen_element.select_one('a[itemprop="url"]')
            if not pen_link:
                continue
            
            pen_url = urljoin("https://codepen.io", pen_link['href'])
            
            if self.is_url_visited(pen_url):
                continue
            
            title_elem = pen_element.select_one('h2')
            title = title_elem.get_text().strip() if title_elem else "Untitled Pen"
            
            self.extract_from_pen(pen_url, language, title)
            self.mark_url_visited(pen_url)
            time.sleep(random.uniform(1.0, 3.0))
    
    def extract_from_pen(self, pen_url: str, language: str, title: str):
        """Extract code from a CodePen."""
        api_client, api_name = self._select_api()
        response = api_client.get(pen_url, render=True)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        script_elem = soup.select_one('#code-javascript') or soup.select_one('#code-typescript')
        if not script_elem:
            return
        
        code_content = script_elem.get_text().strip()
        if not code_content:
            return
        
        detected_lang = LanguageDetector.detect_from_content(code_content)
        code_language = detected_lang if detected_lang else language
        
        if code_language not in LANGUAGES:
            return
        
        self.code_data.add_item(
            language=code_language,
            item_type="snippet",
            content=code_content,
            source_url=pen_url,
            metadata={
                "title": title,
                "platform": "CodePen"
            }
        )

class GistScraper(BaseScraper):
    """Scraper for GitHub Gists."""
    
    def search_gists(self, language: str, max_pages: int = 5):
        """Search for gists in a specific language."""
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            futures = []
            for page in range(1, max_pages + 1):
                search_url = f"https://gist.github.com/search?q=language%3A{language.lower()}&page={page}"
                api_client, api_name = self._select_api()
                futures.append(executor.submit(self._process_search_page, search_url, language, api_client, api_name))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error processing Gist search page: {str(e)}")
    
    def _process_search_page(self, search_url: str, language: str, api_client, api_name: str):
        """Process a single search page."""
        response = api_client.get(search_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        gist_elements = soup.select('.gist-snippet')
        
        for gist_element in gist_elements:
            gist_link = gist_element.select_one('a[href^="/"]')
            if not gist_link:
                continue
            
            gist_url = urljoin("https://gist.github.com", gist_link['href'])
            
            if self.is_url_visited(gist_url):
                continue
            
            title_elem = gist_element.select_one('.gist-snippet-title')
            title = title_elem.get_text().strip() if title_elem else "Untitled Gist"
            
            self.extract_from_gist(gist_url, language, title)
            self.mark_url_visited(gist_url)
            time.sleep(random.uniform(1.0, 3.0))
    
    def extract_from_gist(self, gist_url: str, language: str, title: str):
        """Extract code from a GitHub Gist."""
        api_client, api_name = self._select_api()
        response = api_client.get(gist_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        code_elements = soup.select('.file-box .blob-wrapper')
        
        for code_element in code_elements:
            code_content = code_element.get_text().strip()
            if not code_content:
                continue
            
            detected_lang = LanguageDetector.detect_from_content(code_content)
            code_language = detected_lang if detected_lang else language
            
            if code_language not in LANGUAGES:
                continue
            
            filename_elem = code_element.select_one('.file-header a')
            filename = filename_elem.get_text().strip() if filename_elem else "unknown"
            
            self.code_data.add_item(
                language=code_language,
                item_type="snippet",
                content=code_content,
                source_url=gist_url,
                metadata={
                    "title": title,
                    "filename": filename,
                    "platform": "GitHub Gist"
                }
            )

class CodeCrawler:
    """Main crawler class that coordinates the scraping process."""
    
    def __init__(self, scraper_api_key: str, oxylabs_username: str, oxylabs_password: str, data_dir: str):
        self.scraper_api_client = ScraperAPIClient(scraper_api_key)
        self.oxylabs_client = OxylabsClient(oxylabs_username, oxylabs_password)
        self.code_data = CodeData(data_dir)
        
        self.github_scraper = GitHubScraper(self.scraper_api_client, self.oxylabs_client, self.code_data)
        self.stackoverflow_scraper = StackOverflowScraper(self.scraper_api_client, self.oxylabs_client, self.code_data)
        self.reddit_scraper = RedditScraper(self.scraper_api_client, self.oxylabs_client, self.code_data)
        self.pastebin_scraper = PastebinScraper(self.scraper_api_client, self.oxylabs_client, self.code_data)
        self.gitlab_scraper = GitLabScraper(self.scraper_api_client, self.oxylabs_client, self.code_data)
        self.bitbucket_scraper = BitbucketScraper(self.scraper_api_client, self.oxylabs_client, self.code_data)
        self.codepen_scraper = CodePenScraper(self.scraper_api_client, self.oxylabs_client, self.code_data)
        self.gist_scraper = GistScraper(self.scraper_api_client, self.oxylabs_client, self.code_data)
    
    def crawl_for_language(self, language: str, max_items: int = ITEMS_PER_LANGUAGE):
        """
        Crawl various platforms for code in a specific language.
        """
        logger.info(f"Starting crawl for {language} (target: {max_items} items)")
        
        initial_count = len(self.code_data.current_data.get(language, []))
        
        crawl_steps = [
            ("GitHub", self.github_scraper.search_repositories, 0.3),
            ("Stack Overflow", self.stackoverflow_scraper.search_questions, 0.2),
            ("Reddit", self.reddit_scraper.search_subreddits, 0.1),
            ("Pastebin", self.pastebin_scraper.search_recent_pastes, 0.1),
            ("GitLab", self.gitlab_scraper.search_repositories, 0.2),
            ("Bitbucket", self.bitbucket_scraper.search_repositories, 0.05),
            ("CodePen", self.codepen_scraper.search_pens, 0.05),
            ("GitHub Gist", self.gist_scraper.search_gists, 0.1)
        ]
        
        platform_targets = {platform: int(max_items * weight) for platform, _, weight in crawl_steps}
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for platform, method, _ in crawl_steps:
                target = platform_targets[platform]
                logger.info(f"Crawling {platform} for {language} (target: {target} items)")
                futures.append(executor.submit(method, language))
            
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Error crawling platform: {str(e)}")
            
            self.code_data.save_data(language)
            current_count = len(self.code_data.current_data.get(language, []))
            new_items = current_count - initial_count
            logger.info(f"Collected {new_items} new items for {language}")
            
            if current_count >= max_items:
                logger.info(f"Reached target of {max_items} items for {language}")
    
    def crawl_all_languages(self, items_per_language: int = ITEMS_PER_LANGUAGE):
        """Crawl for all supported languages."""
        for language in LANGUAGES:
            self.crawl_for_language(language, items_per_language)
        
        self.code_data.save_data()
        self.code_data.export_dataset()
        self.generate_summary()
    
    def generate_summary(self):
        """Generate and save a summary of collected data."""
        summary = {
            "total_items": 0,
            "by_language": {},
            "by_type": {
                "snippet": 0,
                "codebase": 0,
                "dataset": 0,
                "documentation": 0
            },
            "by_platform": {}
        }
        
        for language in LANGUAGES:
            items = self.code_data.current_data.get(language, [])
            lang_count = len(items)
            summary["total_items"] += lang_count
            summary["by_language"][language] = lang_count
            
            for item in items:
                item_type = item.get("type", "unknown")
                summary["by_type"][item_type] = summary["by_type"].get(item_type, 0) + 1
                platform = item.get("metadata", {}).get("platform", "unknown")
                summary["by_platform"][platform] = summary["by_platform"].get(platform, 0) + 1
        
        summary_file = os.path.join(DATA_DIR, "crawl_summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Generated summary: collected {summary['total_items']} items across {len(LANGUAGES)} languages")
        
        print("\n" + "="*50)
        print("CRAWL SUMMARY")
        print("="*50)
        print(f"Total items collected: {summary['total_items']}")
        print("\nItems by language:")
        for lang, count in summary["by_language"].items():
            print(f"  {lang}: {count}")
        print("\nItems by type:")
        for item_type, count in summary["by_type"].items():
            print(f"  {item_type}: {count}")
        print("\nItems by platform:")
        for platform, count in summary["by_platform"].items():
            print(f"  {platform}: {count}")
        print("="*50 + "\n")


def main():
    """Main function to run the code crawler."""
    logger.info("Starting Code Crawler")
    
    try:
        crawler = CodeCrawler(SCRAPER_API_KEY, OXYLABS_USERNAME, OXYLABS_PASSWORD, DATA_DIR)
        crawler.crawl_all_languages(items_per_language=ITEMS_PER_LANGUAGE)
        logger.info("Code crawling completed")
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}")
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    main()