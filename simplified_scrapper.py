#!/usr/bin/env python3
"""
Improved Code Crawler - A web crawler that collects code snippets, repositories, and datasets
for various programming languages using ScraperAPI and Oxylabs to bypass anti-scraping protections.

This version includes performance optimizations and uses hardcoded credentials as requested.
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
from typing import Dict, List, Optional, Tuple, Set, Any
from threading import Lock
from functools import lru_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("crawler_log.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("CodeCrawler")

# Constants - HARDCODED API CREDENTIALS AS REQUESTED
SCRAPER_API_KEY = "7e7b5bcfec02306ed3976851d5bb0009"
OXYLABS_USERNAME = "814bdg_5X90h"
OXYLABS_PASSWORD = "Hell___245245"
DATA_DIR = "collected_data"
ITEMS_PER_LANGUAGE = 1000
MAX_WORKERS = 8
REQUEST_TIMEOUT = 60

# Supported programming languages
LANGUAGES = ["Swift", "Python", "Lua", "C", "C++", "Objective-C", "C#", "Ruby", "JavaScript", "TypeScript"]
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
    """Client for interacting with ScraperAPI to bypass anti-scraping measures."""
    
    def __init__(self, api_key=SCRAPER_API_KEY):
        """Initialize with hardcoded API key."""
        if not api_key:
            raise ValueError("ScraperAPI key cannot be empty")
        self.api_key = api_key
        self.base_url = "http://api.scraperapi.com"
        
        # Create session with connection pooling and retry strategy
        self.session = self._create_session()
        
        self.request_count = 0
        self.last_request_time = time.time()
        self.lock = Lock()
    
    def _create_session(self):
        """Create a session with optimized connection pooling and retry strategy."""
        session = requests.Session()
        
        # Configure retry strategy with exponential backoff
        retry_strategy = Retry(
            total=5,
            backoff_factor=2.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        # Configure connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,
            pool_maxsize=50
        )
        
        # Mount adapter for both HTTP and HTTPS
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update({
            "User-Agent": "CodeCrawler/1.0",
            "Accept": "text/html,application/xhtml+xml,application/xml"
        })
        
        return session
    
    def _get_proxy_url(self, url: str, render: bool = False) -> str:
        """Create a ScraperAPI proxy URL for the target URL."""
        params = {
            "api_key": self.api_key,
            "url": quote_plus(url),
        }
        if render:
            params["render"] = "true"
        
        param_str = "&".join(f"{k}={quote_plus(str(v))}" for k, v in params.items())
        return f"{self.base_url}/?{param_str}"
    
    def get(self, url: str, render: bool = False) -> Optional[requests.Response]:
        """
        Make a GET request through ScraperAPI with rate limiting and retries.
        """
        with self.lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time
            if elapsed < 1.0 and self.request_count >= 60:
                sleep_time = 1.0 - elapsed
                logger.info(f"ScraperAPI rate limiting: sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
                self.request_count = 0
            
            proxy_url = self._get_proxy_url(url, render)
            
            try:
                logger.info(f"ScraperAPI fetching: {url}")
                response = self.session.get(proxy_url, timeout=REQUEST_TIMEOUT)
                self.request_count += 1
                self.last_request_time = time.time()
                
                if response.status_code == 200:
                    return response
                else:
                    logger.error(f"ScraperAPI request failed with status {response.status_code}")
                    return None
            except requests.RequestException as e:
                logger.error(f"ScraperAPI request error: {str(e)}")
                return None

class OxylabsClient:
    """Client for interacting with Oxylabs Realtime API."""
    
    def __init__(self, username=OXYLABS_USERNAME, password=OXYLABS_PASSWORD):
        """Initialize with hardcoded credentials."""
        if not username or not password:
            raise ValueError("Oxylabs credentials cannot be empty")
        self.base_url = "https://realtime.oxylabs.io/v1/queries"
        self.auth = (username, password)
        
        # Create session with optimized connection pooling
        self.session = self._create_session()
        
        self.request_count = 0
        self.last_request_time = time.time()
        self.lock = Lock()
        self.result_cache = {}
    
    def _create_session(self):
        """Create a session with optimized connection pooling and retry strategy."""
        session = requests.Session()
        
        # Configure retry strategy with exponential backoff
        retry_strategy = Retry(
            total=5,
            backoff_factor=2.0,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        # Configure connection pooling
        adapter = HTTPAdapter(
            max_retries=retry_strategy,
            pool_connections=20,
            pool_maxsize=50
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
    
    def get(self, url: str, render: bool = False) -> Optional[requests.Response]:
        """
        Make a GET request through Oxylabs Realtime API with rate limiting and retries.
        """
        # Check cache first
        cache_key = f"{url}:{render}"
        if cache_key in self.result_cache:
            logger.debug(f"Cache hit for {url}")
            return self.result_cache[cache_key]
        
        with self.lock:
            current_time = time.time()
            elapsed = current_time - self.last_request_time
            if elapsed < 1.0 and self.request_count >= 60:
                sleep_time = 1.0 - elapsed
                logger.info(f"Oxylabs rate limiting: sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
                self.request_count = 0
            
            payload = {
                "source": "universal",
                "url": url,
                "parse": True,
                "render": "html" if render else None
            }
            
            try:
                logger.info(f"Oxylabs fetching: {url}")
                response = self.session.post(
                    self.base_url,
                    auth=self.auth,
                    json=payload,
                    timeout=REQUEST_TIMEOUT
                )
                self.request_count += 1
                self.last_request_time = time.time()
                
                if response.status_code == 200:
                    data = response.json()
                    content = data.get("results", [{}])[0].get("content", "")
                    class Response:
                        def __init__(self, content):
                            self.status_code = 200
                            self.text = content
                            self.content = content.encode('utf-8')
                    
                    result = Response(content)
                    
                    # Cache the result
                    self.result_cache[cache_key] = result
                    
                    # Limit cache size
                    if len(self.result_cache) > 1000:
                        # Remove random 20% of entries to prevent memory issues
                        keys_to_remove = random.sample(list(self.result_cache.keys()), len(self.result_cache) // 5)
                        for key in keys_to_remove:
                            del self.result_cache[key]
                    
                    return result
                else:
                    logger.error(f"Oxylabs request failed with status {response.status_code}")
                    return None
            except Exception as e:
                logger.error(f"Oxylabs request error: {str(e)}")
                return None

class LanguageDetector:
    """Utility class to detect programming languages from code samples or file paths."""
    
    # Cache for better performance
    EXTENSION_CACHE = {}
    
    @classmethod
    @lru_cache(maxsize=1024)
    def detect_from_extension(cls, file_path: str) -> Optional[str]:
        """Detect language based on file extension with caching."""
        if not file_path:
            return None
            
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
                
        cls.EXTENSION_CACHE[ext] = None
        return None
    
    @classmethod
    @lru_cache(maxsize=128)
    def detect_from_content(cls, content: str) -> Optional[str]:
        """Detect programming language from code content with improved pattern matching."""
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
            
        # Enhanced patterns for better detection
        patterns = {
            "Swift": [r'import\s+Foundation', r'func\s+\w+\s*\([^)]*\)\s*->\s*\w+', r'class\s+\w+\s*:\s*\w+'],
            "Python": [r'import\s+\w+', r'def\s+\w+\s*\(', r'if\s+__name__\s*==\s*[\'"]__main__[\'"]'],
            "C": [r'#include\s+<\w+\.h>', r'int\s+main\s*\(\s*(?:void|int\s+argc,\s*char\s*\*\s*argv\[\])\s*\)'],
            "C++": [r'#include\s+<iostream>', r'namespace\s+\w+', r'std::'],
            "JavaScript": [r'const\s+\w+\s*=', r'function\s+\w+\s*\(', r'document\.'],
            "TypeScript": [r'interface\s+\w+', r':\s*(?:string|number|boolean)', r'<\w+>'],
            "Ruby": [r'require\s+[\'"]\w+[\'"]', r'def\s+\w+\s*(?:\(|$)', r'end$'],
            "C#": [r'using\s+System', r'namespace\s+\w+', r'public\s+class'],
            "Objective-C": [r'#import\s+[<"]\w+\.h[>"]', r'@interface', r'@implementation'],
            "Lua": [r'function\s+\w+\s*\(', r'local\s+\w+\s*=', r'end$']
        }
        
        scores = {lang: 0 for lang in LANGUAGES}
        
        for lang, regex_list in patterns.items():
            for regex in regex_list:
                if re.search(regex, sample, re.MULTILINE):
                    scores[lang] += 1
        
        max_score = max(scores.values()) if scores else 0
        if max_score > 0:
            best_matches = [lang for lang, score in scores.items() if score == max_score]
            return best_matches[0]
        
        return None

class CodeData:
    """Class for managing and storing collected code data."""
    
    def __init__(self, data_dir: str = DATA_DIR):
        self.data_dir = data_dir
        self.current_data = {}
        self.global_hashes = set()
        self.lock = Lock()
        self._load_existing_data()
    
    def _load_existing_data(self):
        """Load existing data from JSON files with improved error handling."""
        for lang in LANGUAGES:
            lang_dir = os.path.join(self.data_dir, lang)
            os.makedirs(lang_dir, exist_ok=True)
            
            data_file = os.path.join(lang_dir, f"{lang.lower()}_data.json")
            if os.path.exists(data_file):
                try:
                    with open(data_file, 'r', encoding='utf-8') as f:
                        self.current_data[lang] = json.load(f)
                        for item in self.current_data[lang]:
                            self.global_hashes.add(item["id"])
                        logger.info(f"Loaded {len(self.current_data[lang])} existing items for {lang}")
                except (json.JSONDecodeError, IOError) as e:
                    logger.warning(f"Could not load existing data for {lang}: {str(e)}")
                    self.current_data[lang] = []
            else:
                self.current_data[lang] = []
    
    def _generate_item_id(self, item: Dict) -> str:
        """Generate a unique ID for an item based on its content."""
        content = item.get('content', '')
        url = item.get('source_url', '')
        lang = item.get('language', '')
        input_str = f"{content}{url}{lang}"
        return hashlib.sha256(input_str.encode('utf-8')).hexdigest()
    
    def add_item(self, language: str, item_type: str, content: str, 
                source_url: str, metadata: Dict = None) -> bool:
        """
        Add a new code item to the dataset with improved validation.
        """
        if language not in LANGUAGES:
            logger.warning(f"Skipping item with unsupported language: {language}")
            return False
        
        # Validate and sanitize content
        if not content or not content.strip():
            logger.warning("Skipping empty content")
            return False
            
        # Remove control characters
        content = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', content)
        
        if language not in self.current_data:
            self.current_data[language] = []
        
        item = {
            "type": item_type,
            "language": language,
            "content": content,
            "source_url": source_url,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "metadata": metadata or {}
        }
        
        item_id = self._generate_item_id(item)
        item["id"] = item_id
        
        with self.lock:
            if item_id in self.global_hashes:
                logger.debug(f"Skipping duplicate item with ID {item_id}")
                return False
            
            self.global_hashes.add(item_id)
            self.current_data[language].append(item)
            logger.info(f"Added new {item_type} for {language} from {source_url[:50]}...")
            
            if len(self.current_data[language]) % 10 == 0:
                self.save_data(language)
                
        return True
    
    def save_data(self, language: str = None):
        """Save collected data to JSON files with atomic write operations."""
        languages_to_save = [language] if language else LANGUAGES
        
        for lang in languages_to_save:
            if lang in self.current_data:
                lang_dir = os.path.join(self.data_dir, lang)
                lang_file = os.path.join(lang_dir, f"{lang.lower()}_data.json")
                temp_file = f"{lang_file}.tmp"
                
                try:
                    # Write to temp file first for atomic operation
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        json.dump(self.current_data[lang], f, ensure_ascii=False)
                    
                    # Atomic rename
                    os.replace(temp_file, lang_file)
                    
                    logger.info(f"Saved {len(self.current_data[lang])} items for {lang}")
                except Exception as e:
                    logger.error(f"Error saving data for {lang}: {str(e)}")
    
    def export_dataset(self):
        """Export all collected data into a single dataset file."""
        dataset = []
        for lang in LANGUAGES:
            if lang in self.current_data:
                dataset.extend(self.current_data[lang])
        
        dataset_file = os.path.join(DATA_DIR, "code_dataset.json")
        
        try:
            # Write to temp file first for atomic operation
            temp_file = f"{dataset_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(dataset, f, ensure_ascii=False)
            
            # Atomic rename
            os.replace(temp_file, dataset_file)
            
            logger.info(f"Exported dataset with {len(dataset)} items to {dataset_file}")
        except Exception as e:
            logger.error(f"Error exporting dataset: {str(e)}")

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
        Extract code blocks from HTML content with improved language detection.
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        code_blocks = []
        
        # Extract from <pre><code> blocks
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
        
        # Extract from standalone <code> blocks
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

class CodeCrawler:
    """Main crawler class that coordinates the scraping process."""
    
    def __init__(self, scraper_api_key=SCRAPER_API_KEY, oxylabs_username=OXYLABS_USERNAME, 
                 oxylabs_password=OXYLABS_PASSWORD, data_dir=DATA_DIR):
        # Using hardcoded credentials as requested
        self.scraper_api_client = ScraperAPIClient(scraper_api_key)
        self.oxylabs_client = OxylabsClient(oxylabs_username, oxylabs_password)
        self.code_data = CodeData(data_dir)
        
        # Print confirmation of using hardcoded credentials
        logger.info("Using hardcoded API credentials:")
        logger.info(f"ScraperAPI Key: {scraper_api_key}")
        logger.info(f"Oxylabs Username: {oxylabs_username}")
        logger.info(f"Oxylabs Password: {oxylabs_password}")
        
        # Initialize platform-specific scrapers
        # Placeholder - actual scrapers would be initialized here
        
    def crawl_all_languages(self, items_per_language=ITEMS_PER_LANGUAGE):
        """Crawl for all supported languages."""
        logger.info(f"Starting crawl for {len(LANGUAGES)} languages")
        logger.info(f"Target items per language: {items_per_language}")
        
        # Placeholder for actual crawling code
        
        logger.info("Crawl completed")
        self.code_data.export_dataset()

def main():
    """Main function to run the code crawler."""
    logger.info("Starting Code Crawler with hardcoded credentials")
    
    try:
        # Create crawler with hardcoded credentials
        crawler = CodeCrawler()
        
        # Just simulate the crawl for now
        logger.info("This is a simplified version to demonstrate hardcoded credentials")
        logger.info("For actual crawling, use the full implementation")
        
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}")
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
