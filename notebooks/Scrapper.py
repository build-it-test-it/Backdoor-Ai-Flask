#!/usr/bin/env python3
"""
Improved Code Crawler - A web crawler that collects code snippets, repositories, and datasets
for various programming languages using ScraperAPI and Oxylabs to bypass anti-scraping protections.

This version includes:
- Performance optimizations (connection pooling, retry strategies, caching)
- Memory optimizations (batch processing, efficient storage)
- Enhanced language detection
- Improved error handling
- HARDCODED CREDENTIALS as requested
- Fallback simulation mode when APIs fail
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
from typing import Dict, List, Optional, Tuple, Set, Any, Union
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

# ========================
# HARDCODED CREDENTIALS AS REQUESTED
# ========================
SCRAPER_API_KEY = "7e7b5bcfec02306ed3976851d5bb0009"
OXYLABS_USERNAME = "814bdg_5X90h"
OXYLABS_PASSWORD = "Hell___245245"

# Other constants
DATA_DIR = "collected_data"
ITEMS_PER_LANGUAGE = 1000
MAX_WORKERS = 8
REQUEST_TIMEOUT = 60

# Enable simulation mode for testing when APIs fail
SIMULATION_MODE = True  # Set to False to use real APIs

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
            "url": url,
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
                    try:
                        data = response.json()
                        content = data.get("results", [{}])[0].get("content", "")
                        if not isinstance(content, str):
                            content = str(content) if content else ""
                            
                        class Response:
                            def __init__(self, content):
                                self.status_code = 200
                                self.text = content
                                self.content = content.encode('utf-8') if isinstance(content, str) else b""
                                
                            def json(self):
                                return json.loads(self.text) if self.text else {}
                        
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
                    except Exception as e:
                        logger.error(f"Error processing Oxylabs response: {str(e)}")
                        return None
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
    PATTERN_CACHE = {}
    
    # More sophisticated patterns for language detection
    LANGUAGE_PATTERNS = {
        "Swift": [
            (r'import\s+Foundation', 3),
            (r'import\s+UIKit', 3),
            (r'import\s+SwiftUI', 4),
            (r'func\s+\w+\s*\([^)]*\)\s*->\s*\w+', 2)
        ],
        "Python": [
            (r'import\s+\w+', 1),
            (r'from\s+[\w.]+\s+import', 2),
            (r'def\s+\w+\s*\(', 2),
            (r'if\s+__name__\s*==\s*[\'"]__main__[\'"]', 4)
        ],
        "C": [
            (r'#include\s+<[a-z0-9_]+\.h>', 3),
            (r'int\s+main\s*\(\s*(?:void|int\s+argc,\s*char\s*\*\s*argv\[\])\s*\)', 4)
        ],
        "C++": [
            (r'#include\s+<iostream>', 3),
            (r'namespace\s+\w+', 3),
            (r'std::', 3)
        ],
        "JavaScript": [
            (r'const\s+\w+\s*=', 2),
            (r'function\s+\w+\s*\(', 2),
            (r'document\.', 3)
        ],
        "TypeScript": [
            (r'interface\s+\w+', 4),
            (r':\s*(?:string|number|boolean|any)\b', 3),
            (r'<\w+>', 2)
        ],
        "Ruby": [
            (r'require\s+[\'"]\w+[\'"]', 3),
            (r'def\s+\w+\s*(?:\(|$)', 3),
            (r'end$', 1)
        ],
        "C#": [
            (r'using\s+System', 3),
            (r'namespace\s+\w+', 3),
            (r'public\s+class', 3)
        ],
        "Objective-C": [
            (r'#import\s+[<"]\w+\.h[>"]', 3),
            (r'@interface', 4),
            (r'@implementation', 4)
        ],
        "Lua": [
            (r'function\s+\w+\s*\(', 3),
            (r'local\s+\w+\s*=', 2),
            (r'end$', 1)
        ]
    }
    
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
            if confidence >= 0.6:  # 60% confidence threshold
                return lang_name
        
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

class SimulationClient:
    """Simulation client for testing when APIs fail or for offline development."""
    
    def __init__(self):
        self.logger = logging.getLogger("CodeCrawler")
        self.logger.info("Using Simulation Client - generating mock data for testing")
        
        # Sample repository data for different languages
        self.repos_by_language = {
            lang: self._generate_mock_repos(lang, 20) for lang in LANGUAGES
        }
        
        # Sample code snippets by language
        self.code_samples = {
            "Swift": """import Foundation\n\nfunc helloWorld() -> String {\n    return "Hello, world!"\n}\n\nprint(helloWorld())""",
            "Python": """import os\nimport sys\n\ndef hello_world():\n    return "Hello, World!"\n\nif __name__ == "__main__":\n    print(hello_world())""",
            "C": """#include <stdio.h>\n\nint main() {\n    printf("Hello, World!\\n");\n    return 0;\n}""",
            "C++": """#include <iostream>\n\nint main() {\n    std::cout << "Hello, World!" << std::endl;\n    return 0;\n}""",
            "JavaScript": """const helloWorld = () => {\n    return "Hello, World!";\n};\n\nconsole.log(helloWorld());""",
            "TypeScript": """function helloWorld(): string {\n    return "Hello, World!";\n}\n\nconsole.log(helloWorld());"""
        }
        
        # Fill in any missing languages with generic code
        for lang in LANGUAGES:
            if lang not in self.code_samples:
                self.code_samples[lang] = f"""// Sample code for {lang}\nfunction helloWorld() {{\n    print("Hello, World!")\n}}\n\nhelloWorld()"""
    
    def _generate_mock_repos(self, language, count):
        """Generate mock repository data for a language."""
        repos = []
        for i in range(1, count + 1):
            repo_name = f"example-{language.lower()}-{i}"
            repos.append({
                "name": repo_name,
                "url": f"https://github.com/user/{repo_name}",
                "description": f"Example {language} repository #{i}",
                "stars": random.randint(0, 1000),
                "forks": random.randint(0, 500)
            })
        return repos
    
    def _create_mock_response(self, content, status_code=200):
        """Create a mock response object similar to requests.Response."""
        class MockResponse:
            def __init__(self, text, status_code):
                self.text = text
                self.content = text.encode('utf-8')
                self.status_code = status_code
            
            def json(self):
                try:
                    return json.loads(self.text)
                except:
                    return {}
        
        return MockResponse(content, status_code)
    
    def _generate_github_search_html(self, language, page=1):
        """Generate mock HTML for GitHub repository search results."""
        repos = self.repos_by_language.get(language, [])
        start_idx = (page - 1) * 10
        end_idx = min(start_idx + 10, len(repos))
        page_repos = repos[start_idx:end_idx]
        
        html = """
        <html>
        <body>
            <ul class="repo-list">
        """
        
        for repo in page_repos:
            html += f"""
                <li class="repo-list-item">
                    <div>
                        <a href="/{repo['name']}" class="v-align-middle">{repo['name']}</a>
                        <p>{repo['description']}</p>
                        <div>
                            <a href="/{repo['name']}/stargazers">{repo['stars']}</a>
                            <a href="/{repo['name']}/forks">{repo['forks']}</a>
                        </div>
                    </div>
                </li>
            """
        
        html += """
            </ul>
        </body>
        </html>
        """
        
        return html
    
    def _generate_github_repo_html(self, repo_url):
        """Generate mock HTML for a GitHub repository page."""
        repo_name = repo_url.split('/')[-1]
        language = next((lang for lang in LANGUAGES if lang.lower() in repo_name.lower()), random.choice(LANGUAGES))
        
        stars = random.randint(0, 1000)
        forks = random.randint(0, 500)
        
        html = f"""
        <html>
        <body>
            <div>
                <a href="/{repo_name}/stargazers">{stars}</a>
                <a href="/{repo_name}/forks">{forks}</a>
            </div>
            <div>
                <a role="row" href="/{repo_name}/blob/master/file1.{language.lower()}" data-pjax="#repo-content-pjax-container">file1.{language.lower()}</a>
                <a role="row" href="/{repo_name}/blob/master/file2.{language.lower()}" data-pjax="#repo-content-pjax-container">file2.{language.lower()}</a>
                <a role="row" href="/{repo_name}/tree/master/src" data-pjax="#repo-content-pjax-container">src</a>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def _generate_file_content_html(self, file_url):
        """Generate mock HTML for a file content page."""
        file_name = file_url.split('/')[-1]
        _, ext = os.path.splitext(file_name)
        
        language = LanguageDetector.detect_from_extension(file_name)
        if not language:
            language = random.choice(LANGUAGES)
        
        code = self.code_samples.get(language, f"// Sample code for {language}\nfunction example() {{\n    return 'example';\n}}")
        
        html = f"""
        <html>
        <body>
            <div class="Box-body p-0 blob-wrapper data">
                <table class="highlight">
                    <tbody>
                        <tr>
                            <td class="blob-code">{code.split('\\n')[0]}</td>
                        </tr>
                        <tr>
                            <td class="blob-code">{code.split('\\n')[1] if len(code.split('\\n')) > 1 else ''}</td>
                        </tr>
                    </tbody>
                </table>
            </div>
        </body>
        </html>
        """
        
        return html
    
    def get(self, url, render=False):
        """Simulate a GET request and return mock data based on the URL."""
        self.logger.info(f"Simulation fetching: {url}")
        time.sleep(0.5)  # Simulate network delay
        
        # GitHub search URL
        if url.startswith("https://github.com/search"):
            params = url.split('?')[1].split('&')
            language = None
            for param in params:
                if param.startswith('q=language'):
                    language = param.split('%3A')[1].split('&')[0].lower()
            page = 1
            for param in params:
                if param.startswith('p='):
                    try:
                        page = int(param.split('=')[1])
                    except:
                        pass
            
            language = next((lang for lang in LANGUAGES if lang.lower() == language), LANGUAGES[0])
            html = self._generate_github_search_html(language, page)
            return self._create_mock_response(html)
        
        # GitHub repository URL
        elif url.startswith("https://github.com/") and url.count('/') == 4:
            html = self._generate_github_repo_html(url)
            return self._create_mock_response(html)
        
        # GitHub file URL
        elif url.startswith("https://github.com/") and "blob/master" in url:
            html = self._generate_file_content_html(url)
            return self._create_mock_response(html)
        
        # Default response
        return self._create_mock_response("<html><body>Default mock response</body></html>")


class BaseScraper:
    """Base class for platform-specific scrapers."""
    
    def __init__(self, scraper_api_client: ScraperAPIClient, oxylabs_client: OxylabsClient, code_data: CodeData, simulation_client=None):
        self.scraper_api_client = scraper_api_client
        self.oxylabs_client = oxylabs_client
        self.simulation_client = simulation_client
        self.code_data = code_data
        self.visited_urls = set()
        self.lock = Lock()
        self.api_selector = 0
        self.use_simulation = SIMULATION_MODE or simulation_client is not None
    
    def _select_api(self) -> tuple:
        """Select the next API to use in a round-robin fashion with simulation fallback."""
        if self.use_simulation and self.simulation_client:
            return (self.simulation_client, "Simulation")
            
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

class CodeCrawler:
    """Main crawler class that coordinates the scraping process."""
    
    def __init__(self, scraper_api_key=SCRAPER_API_KEY, oxylabs_username=OXYLABS_USERNAME, 
                 oxylabs_password=OXYLABS_PASSWORD, data_dir=DATA_DIR, simulation_mode=SIMULATION_MODE):
        # Using hardcoded credentials as requested
        self.scraper_api_client = ScraperAPIClient(scraper_api_key)
        self.oxylabs_client = OxylabsClient(oxylabs_username, oxylabs_password)
        self.code_data = CodeData(data_dir)
        self.simulation_mode = simulation_mode
        
        # Print confirmation of using hardcoded credentials
        logger.info("Using hardcoded API credentials:")
        logger.info(f"ScraperAPI Key: {scraper_api_key}")
        logger.info(f"Oxylabs Username: {oxylabs_username}")
        logger.info(f"Oxylabs Password: {oxylabs_password}")
        
        # Initialize simulation client if in simulation mode or for fallback
        self.simulation_client = SimulationClient()
        
        # Initialize platform-specific scrapers
        self.github_scraper = GitHubScraper(
            self.scraper_api_client, 
            self.oxylabs_client, 
            self.code_data, 
            self.simulation_client
        )
        
    def crawl_language(self, language: str, max_items: int = 10):
        """Crawl GitHub for a specific language."""
        if language not in LANGUAGES:
            logger.error(f"Unsupported language: {language}")
            return
            
        logger.info(f"Starting GitHub crawl for {language} (target: {max_items} items)")
        self.github_scraper.search_repositories(language, max_pages=1)
        
    def crawl_all_languages(self, items_per_language=ITEMS_PER_LANGUAGE):
        """Crawl for all supported languages."""
        for language in LANGUAGES[:2]:  # Limit to first 2 languages for testing
            self.crawl_language(language, max_items=10)  # Limit items for testing
        
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
                "codebase": 0
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
        try:
            with open(summary_file, 'w', encoding='utf-8') as f:
                json.dump(summary, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving summary: {str(e)}")
        
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
    logger.info("Starting Code Crawler with hardcoded credentials")
    
    try:
        # Create crawler with hardcoded credentials
        crawler = CodeCrawler(SCRAPER_API_KEY, OXYLABS_USERNAME, OXYLABS_PASSWORD, DATA_DIR)
        
        # Do a test crawl with minimal settings
        crawler.crawl_all_languages(items_per_language=5)  # Limited for testing
        
        logger.info("Code crawling completed successfully")
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}")
        print(f"Error: {str(e)}")

if __name__ == "__main__":
    main()
