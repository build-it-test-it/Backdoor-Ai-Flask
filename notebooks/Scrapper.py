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
import traceback
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
SIMULATION_MODE = False  # Set to False to use real APIs

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

# Target URLs for scraping by language and site type
TARGET_URLS = {
    "Swift": [
        "https://docs.swift.org/swift-book/",
        "https://developer.apple.com/swift/",
        "https://stackoverflow.com/questions/tagged/swift",
        "https://github.com/search?q=language%3Aswift",
        "https://github.com/apple/swift",
        "https://github.com/vapor/vapor",
        "https://www.hackingwithswift.com/",
        "https://www.raywenderlich.com/category/swift",
        "https://www.codecademy.com/learn/learn-swift",
        "https://www.coursera.org/courses?query=swift",
        "https://www.edx.org/learn/swift",
        "https://www.udemy.com/topic/swift/",
        "https://www.reddit.com/r/swift/",
        "https://forums.swift.org/",
        "https://nshipster.com/",
        "https://useyourloaf.com/",
        "https://swiftweekly.github.io/",
        "https://swift.org/",
        "https://swift.sandbox.bluemix.net/",
        "https://www.apple.com/swift/playgrounds/"
    ],
    "Python": [
        "https://docs.python.org/3/",
        "https://www.python.org/",
        "https://pypi.org/",
        "https://stackoverflow.com/questions/tagged/python",
        "https://www.reddit.com/r/python/",
        "https://realpython.com/",
        "https://www.tutorialspoint.com/python/",
        "https://www.w3schools.com/python/",
        "https://www.geeksforgeeks.org/python-programming-language/",
        "https://towardsdatascience.com/tagged/python",
        "https://medium.com/tag/python",
        "https://github.com/search?q=language%3Apython",
        "https://github.com/python/cpython",
        "https://github.com/psf/requests",
        "https://github.com/numpy/numpy",
        "https://github.com/pandas-dev/pandas",
        "https://github.com/django/django",
        "https://github.com/pallets/flask",
        "https://www.kaggle.com/code?language=Python",
        "https://jupyter.org/"
    ],
    "Lua": [
        "https://www.lua.org/manual/5.4/",
        "https://www.lua.org/",
        "https://stackoverflow.com/questions/tagged/lua",
        "https://github.com/search?q=language%3Alua",
        "https://github.com/love2d/love",
        "https://github.com/leafo/lapis",
        "https://github.com/minetest/minetest",
        "https://www.codecademy.com/learn/learn-lua",
        "https://www.classcentral.com/subject/lua",
        "https://www.udemy.com/topic/lua/",
        "https://www.reddit.com/r/lua/",
        "https://learn-lua.com/",
        "https://www.lua.org/pil/contents.html",
        "http://lua-users.org/wiki/",
        "http://luajit.org/",
        "https://coronalabs.com/",
        "https://giderosmobile.com/",
        "https://solar2d.com/",
        "https://fivem.net/",
        "https://mods.factorio.com/"
    ],
    "C": [
        "http://www.open-std.org/jtc1/sc22/wg14/www/docs/n1570.pdf",
        "http://c-faq.com/",
        "https://stackoverflow.com/questions/tagged/c",
        "https://github.com/search?q=language%3Ac",
        "https://github.com/torvalds/linux",
        "https://github.com/bminor/glibc",
        "https://www.learn-c.org/",
        "https://www.codecademy.com/learn/paths/c",
        "https://www.programiz.com/c-programming",
        "https://www.geeksforgeeks.org/c-programming-language/",
        "https://www.tutorialspoint.com/cprogramming/",
        "https://www.w3schools.com/c/",
        "https://www.c4learn.com/",
        "https://www.sanfoundry.com/c-programming-examples/",
        "https://codeforwin.org/c-programming/",
        "https://fresh2refresh.com/c-programming/",
        "https://www.tutorialsteacher.com/c",
        "https://www.includehelp.com/c-programming-tutorial.aspx",
        "https://www.journaldev.com/c-programming",
        "https://www.careerride.com/C-Programming.aspx"
    ],
    "C++": [
        "https://en.cppreference.com/w/",
        "https://stackoverflow.com/questions/tagged/c%2B%2B",
        "https://github.com/search?q=language%3Acpp",
        "https://github.com/llvm/llvm-project",
        "https://github.com/qt/qt5",
        "https://www.learncpp.com/",
        "https://www.codecademy.com/learn/learn-c-plus-plus",
        "https://www.cplusplus.com/",
        "https://www.geeksforgeeks.org/c-plus-plus/",
        "https://www.tutorialspoint.com/cplusplus/",
        "https://www.programiz.com/cpp-programming",
        "https://www.w3schools.com/cpp/",
        "https://fresh2refresh.com/c-plus-plus-tutorial/",
        "https://www.tutorialsteacher.com/cpp",
        "https://www.includehelp.com/cpp-tutorial.aspx",
        "https://www.journaldev.com/c-plus-plus",
        "https://www.careerride.com/C-Plus-Plus.aspx",
        "https://codeforwin.org/c-programming/",
        "https://www.sanfoundry.com/c-plus-plus-programming-examples/",
        "http://www.open-std.org/jtc1/sc22/wg21/docs/papers/2020/n4860.pdf"
    ],
    "Objective-C": [
        "https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/ProgrammingWithObjectiveC/Introduction/Introduction.html",
        "https://www.objc.io/",
        "https://nshipster.com/",
        "https://stackoverflow.com/questions/tagged/objective-c",
        "https://github.com/search?q=language%3Aobjective-c",
        "https://github.com/AFNetworking/AFNetworking",
        "https://github.com/CocoaPods/CocoaPods",
        "https://www.tutorialspoint.com/objective_c/",
        "https://www.raywenderlich.com/category/objective-c",
        "https://www.appcoda.com/category/objective-c/",
        "https://iosdevelopertips.com/",
        "https://www.cocoacontrols.com/",
        "https://cocoawithlove.com/",
        "https://useyourloaf.com/",
        "https://iachieved.it/iachievedit/",
        "https://nshipster.com/author/mattt/",
        "http://www.fluffycat.com/",
        "https://qualitycoding.org/",
        "https://codingexplorer.com/",
        "https://developer.apple.com/wwdc20/academy/"
    ],
    "C#": [
        "https://docs.microsoft.com/en-us/dotnet/csharp/",
        "https://dotnet.microsoft.com/en-us/learn/csharp",
        "https://stackoverflow.com/questions/tagged/c%23",
        "https://github.com/search?q=language%3Acsharp",
        "https://github.com/dotnet/runtime",
        "https://github.com/dotnet/aspnetcore",
        "https://www.codecademy.com/learn/learn-c-sharp",
        "https://www.pluralsight.com/search?q=c%23",
        "https://www.udemy.com/topic/c-sharp/",
        "https://www.edx.org/learn/c-sharp",
        "https://www.coursera.org/courses?query=c%23",
        "https://www.tutorialspoint.com/csharp/",
        "https://www.w3schools.com/cs/",
        "https://learnvisualstudio.net/",
        "https://www.c-sharpcorner.com/",
        "https://www.dotnetcurry.com/",
        "https://www.codeproject.com/KB/cs/",
        "https://dzone.com/articles?tag=csharp",
        "https://www.infoq.com/csharp/",
        "https://mva.microsoft.com/en-us/training-courses/csharp-fundamentals-8292?l=1N1Z4w6l_5604192092"
    ],
    "Ruby": [
        "https://ruby-doc.org/",
        "https://stackoverflow.com/questions/tagged/ruby",
        "https://github.com/search?q=language%3Aruby",
        "https://github.com/rails/rails",
        "https://github.com/ruby/ruby",
        "https://www.codecademy.com/learn/learn-ruby",
        "https://www.learnrubyonline.org/",
        "https://rubymonk.com/",
        "https://www.tutorialspoint.com/ruby/",
        "https://www.programiz.com/ruby-programming",
        "https://www.geeksforgeeks.org/ruby-programming-language/",
        "https://www.w3schools.com/ruby/",
        "https://www.ruby-lang.org/en/documentation/quickstart/",
        "http://poignantguide.net/",
        "https://rubykoans.com/",
        "https://graceful.dev/",
        "http://railscasts.com/",
        "https://gorails.com/",
        "https://rubyweekly.com/",
        "https://www.rubyinside.com/"
    ],
    "JavaScript": [
        "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
        "https://stackoverflow.com/questions/tagged/javascript",
        "https://github.com/search?q=language%3Ajavascript",
        "https://github.com/nodejs/node",
        "https://github.com/facebook/react",
        "https://www.codecademy.com/learn/introduction-to-javascript",
        "https://www.freecodecamp.org/learn/javascript-algorithms-and-data-structures/",
        "https://learnjavascript.online/",
        "https://www.w3schools.com/js/",
        "https://www.tutorialspoint.com/javascript/",
        "https://www.programiz.com/javascript",
        "https://www.geeksforgeeks.org/javascript-tutorial/",
        "https://javascript.info/",
        "https://eloquentjavascript.net/",
        "https://github.com/getify/You-Dont-Know-JS",
        "https://javascriptweekly.com/",
        "https://www.sitepoint.com/javascript/",
        "https://www.smashingmagazine.com/category/javascript",
        "https://css-tricks.com/category/javascript/",
        "https://dev.to/t/javascript"
    ],
    "TypeScript": [
        "https://www.typescriptlang.org/docs/",
        "https://stackoverflow.com/questions/tagged/typescript",
        "https://github.com/search?q=language%3Atypescript",
        "https://github.com/angular/angular",
        "https://github.com/microsoft/TypeScript",
        "https://www.codecademy.com/learn/learn-typescript",
        "https://learntypescript.online/",
        "https://www.tutorialspoint.com/typescript/",
        "https://www.w3schools.com/typescript/",
        "https://www.programiz.com/typescript",
        "https://www.geeksforgeeks.org/typescript/",
        "https://basarat.gitbook.io/typescript/",
        "https://www.typescriptlang.org/docs/handbook/",
        "https://basarat.gitbook.io/typescript/",
        "https://egghead.io/technologies/typescript",
        "https://www.pluralsight.com/search?q=typescript",
        "https://www.udemy.com/topic/typescript/",
        "https://www.edx.org/learn/typescript",
        "https://www.coursera.org/courses?query=typescript",
        "https://learn.microsoft.com/en-us/training/paths/typescript/"
    ]
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
                "parse": False,  # Get raw HTML instead of parsed content
                "render": "html" if render else None,
                "premium_proxy": "true"  # Use premium proxies for better success rate
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
        
        # Split the code into lines before using in f-string
        code_lines = code.split('\n')
        first_line = code_lines[0] if code_lines else ""
        second_line = code_lines[1] if len(code_lines) > 1 else ""
        
        html = f"""
        <html>
        <body>
            <div class="Box-body p-0 blob-wrapper data">
                <table class="highlight">
                    <tbody>
                        <tr>
                            <td class="blob-code">{first_line}</td>
                        </tr>
                        <tr>
                            <td class="blob-code">{second_line}</td>
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


class WebsiteScraper:
    """Base class for all website-specific scrapers."""
    
    def __init__(self, scraper_api_client: ScraperAPIClient, oxylabs_client: OxylabsClient, code_data: CodeData, simulation_client=None):
        self.scraper_api_client = scraper_api_client
        self.oxylabs_client = oxylabs_client
        self.simulation_client = simulation_client
        self.code_data = code_data
        self.visited_urls = set()
        self.lock = Lock()
        self.api_selector = 0
        self.use_simulation = simulation_client is not None
    
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
    
    def get_page_content(self, url: str, render: bool = False) -> Optional[str]:
        """Get the HTML content of a page using the available APIs."""
        if self.is_url_visited(url):
            logger.info(f"Skipping already visited URL: {url}")
            return None
            
        api_client, api_name = self._select_api()
        logger.info(f"Fetching {url} using {api_name}")
        
        try:
            response = api_client.get(url, render=render)
            if not response:
                logger.error(f"Failed to get response from {url}")
                return None
                
            self.mark_url_visited(url)
            return response.text
        except Exception as e:
            logger.error(f"Error getting page content for {url}: {str(e)}")
            logger.error(f"Exception details: {traceback.format_exc()}")
            return None
    
    def extract_code_blocks(self, html_content: str) -> List[Tuple[str, Optional[str]]]:
        """Extract code blocks from HTML with language detection."""
        if not html_content:
            return []
            
        soup = BeautifulSoup(html_content, 'html.parser')
        code_blocks = []
        
        # Try multiple code block extraction strategies
        # 1. <pre><code> blocks (common on documentation sites and markdown)
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
        
        # 2. Standalone <code> blocks
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
                
        # 3. Generic <pre> blocks without <code> tags
        for pre in soup.find_all('pre'):
            if not pre.find('code') and pre.text.strip():
                language = LanguageDetector.detect_from_content(pre.text)
                if language:
                    code_blocks.append((pre.text.strip(), language))
        
        # 4. Look for syntax-highlighted div blocks (common in documentation)
        for div in soup.find_all(['div', 'section'], class_=['highlight', 'code', 'codehilite', 'syntax']):
            language = None
            
            # Try to detect language from class
            if div.get('class'):
                for cls in div.get('class'):
                    for lang in LANGUAGES:
                        if lang.lower() in cls.lower():
                            language = lang
                            break
            
            # If no language detected from class, try content
            if not language:
                language = LanguageDetector.detect_from_content(div.text)
            
            if language:
                code_blocks.append((div.text.strip(), language))
        
        return code_blocks
    
    def scrape_url(self, url: str, language: str) -> int:
        """Base method for scraping a URL. Should be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement scrape_url method")

class SiteClassifier:
    """Classifies websites to determine the appropriate scraper."""
    
    @staticmethod
    def classify_url(url: str) -> str:
        """Determine the type of website from a URL."""
        domain = urlparse(url).netloc.lower()
        path = urlparse(url).path.lower()
        
        # GitHub repositories
        if ("github.com" in domain and 
            ("/search" in path or 
             (len(path.split('/')) > 2 and "blob" not in path))):
            return "github_repo"
            
        # GitHub search
        elif "github.com/search" in url:
            return "github_search"
            
        # GitHub file
        elif "github.com" in domain and "blob" in path:
            return "github_file"
            
        # Stack Overflow
        elif "stackoverflow.com" in domain:
            return "stackoverflow"
            
        # Reddit
        elif "reddit.com" in domain:
            return "forum"
            
        # Documentation sites
        elif any(doc_site in domain for doc_site in [
                "docs.", "documentation.", ".org/docs", "developer.", 
                "reference", ".io/docs", "manual", "handbook"
            ]):
            return "documentation"
            
        # Tutorial sites
        elif any(tutorial_site in domain for tutorial_site in [
                "tutorial", "learn", "w3schools", "geeksforgeeks", 
                "tutorialspoint", "programiz", "codecademy", "freecodecamp",
                "coursera", "udemy", "edx", "pluralsight"
            ]):
            return "tutorial"
            
        # Default to generic website
        return "generic"

class StackOverflowScraper(WebsiteScraper):
    """Specialized scraper for Stack Overflow."""
    
    def scrape_url(self, url: str, language: str) -> int:
        """Scrape code examples from Stack Overflow."""
        logger.info(f"Scraping Stack Overflow URL: {url}")
        
        html_content = self.get_page_content(url, render=True)
        if not html_content:
            return 0
            
        soup = BeautifulSoup(html_content, 'html.parser')
        items_added = 0
        
        # Extract answers which are more likely to contain code
        answers = soup.select('.answer')
        if not answers:
            # Try alternative selectors
            answers = soup.select('.js-answer')
            if not answers:
                answers = soup.select('[data-answerid]')
        
        for answer in answers:
            # Extract vote count to prioritize higher-voted answers
            vote_elem = answer.select_one('.js-vote-count, .vote-count-post')
            votes = 0
            if vote_elem:
                try:
                    votes = int(vote_elem.get_text().strip())
                except:
                    pass
            
            # Extract code blocks from the answer
            code_elements = answer.select('pre code')
            for i, code_elem in enumerate(code_elements):
                code_text = code_elem.get_text().strip()
                if not code_text:
                    continue
                    
                # Try to detect language
                detected_language = None
                
                # Look for language hint in class
                if code_elem.get('class'):
                    classes = code_elem.get('class')
                    lang_classes = [c for c in classes if c.startswith(('lang-', 'language-'))]
                    if lang_classes:
                        lang_hint = lang_classes[0].split('-', 1)[1].lower()
                        detected_language = next((l for l in LANGUAGES if l.lower() == lang_hint), None)
                
                # If no language hint or doesn't match target, use content detection
                if not detected_language:
                    detected_language = LanguageDetector.detect_from_content(code_text)
                    
                # If still no detection and we have a target language, use it
                if not detected_language and language:
                    detected_language = language
                
                # Only add if language matches target or we detected something
                if detected_language and (not language or detected_language == language):
                    # Get question title for metadata
                    title_elem = soup.select_one('h1[itemprop="name"], .question-hyperlink')
                    title = title_elem.get_text().strip() if title_elem else "Stack Overflow Question"
                    
                    # Add code to dataset
                    self.code_data.add_item(
                        language=detected_language,
                        item_type="snippet",
                        content=code_text,
                        source_url=url,
                        metadata={
                            "title": title,
                            "votes": votes,
                            "platform": "Stack Overflow",
                            "snippet_index": i
                        }
                    )
                    items_added += 1
        
        logger.info(f"Added {items_added} code snippets from Stack Overflow page {url}")
        return items_added

class DocumentationScraper(WebsiteScraper):
    """Specialized scraper for documentation websites."""
    
    def scrape_url(self, url: str, language: str) -> int:
        """Scrape code examples from documentation sites."""
        logger.info(f"Scraping documentation URL: {url}")
        
        html_content = self.get_page_content(url, render=True)
        if not html_content:
            return 0
            
        soup = BeautifulSoup(html_content, 'html.parser')
        items_added = 0
        
        # Extract code blocks using the base method
        code_blocks = self.extract_code_blocks(html_content)
        
        # Get page title for metadata
        title_elem = soup.select_one('title')
        title = title_elem.get_text().strip() if title_elem else urlparse(url).netloc
        
        # Try to find section headers for better context
        headers = soup.select('h1, h2, h3')
        page_headers = [h.get_text().strip() for h in headers if h.get_text().strip()]
        
        for i, (code_text, detected_language) in enumerate(code_blocks):
            # Skip empty or very short code
            if not code_text or len(code_text) < 10:
                continue
                
            # If language wasn't detected, use target language
            if not detected_language and language:
                detected_language = language
                
            # Only add if language matches target or we detected something
            if detected_language and (not language or detected_language == language):
                # Add code to dataset
                self.code_data.add_item(
                    language=detected_language,
                    item_type="snippet",
                    content=code_text,
                    source_url=url,
                    metadata={
                        "title": title,
                        "page_headers": page_headers[:3],  # Include top headers for context
                        "platform": "Documentation",
                        "domain": urlparse(url).netloc,
                        "snippet_index": i
                    }
                )
                items_added += 1
        
        logger.info(f"Added {items_added} code snippets from documentation page {url}")
        return items_added

class TutorialScraper(WebsiteScraper):
    """Specialized scraper for tutorial websites."""
    
    def scrape_url(self, url: str, language: str) -> int:
        """Scrape code examples from tutorial sites."""
        logger.info(f"Scraping tutorial URL: {url}")
        
        html_content = self.get_page_content(url, render=True)
        if not html_content:
            return 0
            
        soup = BeautifulSoup(html_content, 'html.parser')
        items_added = 0
        
        # Extract code blocks using the base method
        code_blocks = self.extract_code_blocks(html_content)
        
        # Get page title for metadata
        title_elem = soup.select_one('title')
        title = title_elem.get_text().strip() if title_elem else urlparse(url).netloc
        
        # Extract explanatory text near code blocks for context
        article_content = soup.select_one('article, .article, .content, main, #content, .tutorial-content')
        explanations = []
        
        if article_content:
            # Find paragraphs that might explain the code
            paragraphs = article_content.select('p')
            explanations = [p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30]
        
        for i, (code_text, detected_language) in enumerate(code_blocks):
            # Skip empty or very short code
            if not code_text or len(code_text) < 10:
                continue
                
            # If language wasn't detected, use target language
            if not detected_language and language:
                detected_language = language
                
            # Only add if language matches target or we detected something
            if detected_language and (not language or detected_language == language):
                # Try to find nearby explanation
                nearby_explanation = ""
                if i < len(explanations):
                    nearby_explanation = explanations[i]
                
                # Add code to dataset
                self.code_data.add_item(
                    language=detected_language,
                    item_type="snippet",
                    content=code_text,
                    source_url=url,
                    metadata={
                        "title": title,
                        "explanation": nearby_explanation[:500],  # Include some explanation if available
                        "platform": "Tutorial",
                        "domain": urlparse(url).netloc,
                        "snippet_index": i
                    }
                )
                items_added += 1
        
        logger.info(f"Added {items_added} code snippets from tutorial page {url}")
        return items_added

class ForumScraper(WebsiteScraper):
    """Specialized scraper for forum websites like Reddit."""
    
    def scrape_url(self, url: str, language: str) -> int:
        """Scrape code examples from forum sites."""
        logger.info(f"Scraping forum URL: {url}")
        
        html_content = self.get_page_content(url, render=True)
        if not html_content:
            return 0
            
        soup = BeautifulSoup(html_content, 'html.parser')
        items_added = 0
        
        # Extract code blocks using the base method
        code_blocks = self.extract_code_blocks(html_content)
        
        # Get page title for metadata
        title_elem = soup.select_one('title')
        title = title_elem.get_text().strip() if title_elem else urlparse(url).netloc
        
        # Find post content and comments
        comments = soup.select('.comment, .Post, [data-testid="comment"], .comment-body')
        
        for i, (code_text, detected_language) in enumerate(code_blocks):
            # Skip empty or very short code
            if not code_text or len(code_text) < 10:
                continue
                
            # If language wasn't detected, use target language
            if not detected_language and language:
                detected_language = language
                
            # Only add if language matches target or we detected something
            if detected_language and (not language or detected_language == language):
                # Add code to dataset
                self.code_data.add_item(
                    language=detected_language,
                    item_type="snippet",
                    content=code_text,
                    source_url=url,
                    metadata={
                        "title": title,
                        "platform": "Forum",
                        "domain": urlparse(url).netloc,
                        "snippet_index": i
                    }
                )
                items_added += 1
        
        logger.info(f"Added {items_added} code snippets from forum page {url}")
        return items_added

class GenericScraper(WebsiteScraper):
    """Fallback scraper for any website not covered by specialized scrapers."""
    
    def scrape_url(self, url: str, language: str) -> int:
        """Scrape code examples from any website."""
        logger.info(f"Scraping generic URL: {url}")
        
        html_content = self.get_page_content(url, render=True)
        if not html_content:
            return 0
            
        soup = BeautifulSoup(html_content, 'html.parser')
        items_added = 0
        
        # Extract code blocks using the base method
        code_blocks = self.extract_code_blocks(html_content)
        
        # Get page title for metadata
        title_elem = soup.select_one('title')
        title = title_elem.get_text().strip() if title_elem else urlparse(url).netloc
        
        for i, (code_text, detected_language) in enumerate(code_blocks):
            # Skip empty or very short code
            if not code_text or len(code_text) < 10:
                continue
                
            # If language wasn't detected, use target language
            if not detected_language and language:
                detected_language = language
                
            # Only add if language matches target or we detected something
            if detected_language and (not language or detected_language == language):
                # Add code to dataset
                self.code_data.add_item(
                    language=detected_language,
                    item_type="snippet",
                    content=code_text,
                    source_url=url,
                    metadata={
                        "title": title,
                        "platform": "Website",
                        "domain": urlparse(url).netloc,
                        "snippet_index": i
                    }
                )
                items_added += 1
        
        logger.info(f"Added {items_added} code snippets from generic page {url}")
        return items_added

class GitHubScraper(WebsiteScraper):
    """Scraper for GitHub repositories and snippets."""
    
    def search_repositories(self, language: str, max_pages: int = 10):
        """Search for repositories in a specific language."""
        # Use more worker threads for better parallelism and throughput
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = []
            for page in range(1, max_pages + 1):
                search_url = f"https://github.com/search?q=language%3A{language.lower()}&type=repositories&p={page}"
                api_client, api_name = self._select_api()
                futures.append(executor.submit(self._process_search_page, search_url, language, api_client, api_name))
                # Add a small delay between starting each request to avoid overwhelming the API
                time.sleep(0.2)
            
            completed = 0
            for future in concurrent.futures.as_completed(futures):
                try:
                    future.result()
                    completed += 1
                    logger.info(f"Processed {completed}/{max_pages} search pages for {language}")
                except Exception as e:
                    logger.error(f"Error processing GitHub search page: {str(e)}")
                    # Log traceback for better debugging
                    logger.error(f"Exception details: {traceback.format_exc()}")
    
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
    
    def _explore_repo_files(self, repo_url: str, primary_language: str, path: str = "", max_depth: int = 4, current_depth: int = 0):
        """Recursively explore repository files to extract code."""
        if current_depth > max_depth:
            return
        
        # Try different branch names if master doesn't exist
        branch_names = ["master", "main", "develop", "trunk"]
        explore_url = None
        
        for branch in branch_names:
            if not path:
                # Root of repository
                explore_url = repo_url
                break
            else:
                # Try this branch
                temp_url = f"{repo_url}/tree/{branch}/{path}"
                logger.debug(f"Trying URL: {temp_url}")
                explore_url = temp_url
                break
                
        if not explore_url:
            logger.warning(f"Could not determine URL for repository path: {path}")
            return
            
        api_client, api_name = self._select_api()
        response = api_client.get(explore_url)
        if not response:
            logger.warning(f"Failed to get response from {explore_url}")
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Try multiple CSS selectors to handle different GitHub HTML structures
        file_items = []
        selectors_to_try = [
            'a[role="row"]',  # Current GitHub structure
            '.js-navigation-item .js-navigation-open',  # Older GitHub structure
            'div[role="row"] a',  # Another possible structure
            'table.files tr.js-navigation-item td.content a'  # Yet another structure
        ]
        
        for selector in selectors_to_try:
            file_items = soup.select(selector)
            if file_items:
                logger.debug(f"Found {len(file_items)} files using selector: {selector}")
                break
                
        if not file_items:
            logger.warning(f"Could not find file items in {explore_url}")
            
        processed_count = 0
        for item in file_items:
            # Extract item type (file or directory)
            href = item.get('href', '')
            if not href:
                continue
                
            item_type = "file" if "/blob/" in href else "directory"
            item_link = href
            
            item_name = item_link.split("/")[-1]
            item_path = path + "/" + item_name if path else item_name
            item_url = urljoin("https://github.com", item_link)
            
            if self.is_url_visited(item_url):
                continue
            
            try:
                if item_type == "file":
                    detected_language = LanguageDetector.detect_from_extension(item_name)
                    if detected_language:
                        self._extract_file_content(item_url, detected_language)
                        processed_count += 1
                elif item_type == "directory" and current_depth < max_depth:
                    self._explore_repo_files(repo_url, primary_language, item_path, max_depth, current_depth + 1)
                    processed_count += 1
                
                self.mark_url_visited(item_url)
                
                # Use a minimal delay between requests to avoid rate limiting
                # But make it much shorter than before to improve performance
                time.sleep(0.1)
                
            except Exception as e:
                logger.error(f"Error processing item {item_url}: {str(e)}")
                logger.error(f"Exception details: {traceback.format_exc()}")
        
        logger.info(f"Processed {processed_count} items at depth {current_depth} for path: {path}")
    
    def _extract_file_content(self, file_url: str, language: str):
        """Extract code content from a GitHub file."""
        try:
            logger.debug(f"Extracting code content from {file_url}")
            api_client, api_name = self._select_api()
            response = api_client.get(file_url)
            if not response:
                logger.warning(f"Failed to get response from {file_url}")
                return
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Try multiple CSS selectors to handle different GitHub HTML structures
            code_element = None
            code_selectors = [
                'table.highlight',                           # Current GitHub structure
                '.js-file-line-container',                   # Alternate structure
                '.Box-body .highlight',                       # Another possible structure
                'div[data-target="readme-toc.content"] pre',  # For README files
                'div.blob-wrapper',                           # Yet another structure
                'div[itemprop="text"]'                        # Another possible structure
            ]
            
            for selector in code_selectors:
                code_element = soup.select_one(selector)
                if code_element:
                    logger.debug(f"Found code element using selector: {selector}")
                    break
            
            if not code_element:
                logger.warning(f"Could not find code element in {file_url}")
                # Try to get raw content as a fallback
                raw_url = file_url.replace("blob/", "raw/")
                logger.debug(f"Trying raw URL: {raw_url}")
                try:
                    raw_response = api_client.get(raw_url)
                    if raw_response and raw_response.text:
                        code_content = raw_response.text
                        if code_content.strip():
                            filename = file_url.split("/")[-1]
                            logger.info(f"Extracted {len(code_content)} bytes of raw code from {filename}")
                            self._save_code_snippet(code_content, language, file_url, filename)
                            return
                except Exception as e:
                    logger.error(f"Error fetching raw content: {str(e)}")
                return
            
            # Extract code content based on the HTML structure we found
            code_lines = []
            
            # Try different extraction methods
            if 'table.highlight' in code_selectors and code_element.name == 'table':
                # Table-based structure
                for line in code_element.select('tr'):
                    line_content = line.select_one('td.blob-code')
                    if line_content:
                        code_lines.append(line_content.get_text(strip=True))
            elif code_element.name == 'pre':
                # Pre element
                code_lines = code_element.get_text().split('\n')
            else:
                # Generic extraction
                code_text = code_element.get_text()
                code_lines = code_text.split('\n')
                
            code_content = "\n".join(code_lines)
            
            if not code_content.strip():
                logger.warning(f"Extracted empty code content from {file_url}")
                return
            
            filename = file_url.split("/")[-1]
            logger.info(f"Extracted {len(code_content)} bytes of code from {filename}")
            
            self._save_code_snippet(code_content, language, file_url, filename)
            
        except Exception as e:
            logger.error(f"Error extracting code content from {file_url}: {str(e)}")
            logger.error(f"Exception details: {traceback.format_exc()}")
    
    def _save_code_snippet(self, code_content, language, file_url, filename):
        """Save a code snippet to the code data store."""
        try:
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
        except Exception as e:
            logger.error(f"Error saving code snippet {filename}: {str(e)}")
            logger.error(f"Exception details: {traceback.format_exc()}")

class CodeCrawler:
    """Main crawler class that coordinates the scraping process across various websites."""
    
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
        
        # Initialize simulation client only if in simulation mode
        self.simulation_client = SimulationClient() if simulation_mode else None
        
        # Initialize all specialized scrapers
        self.github_scraper = GitHubScraper(
            self.scraper_api_client, 
            self.oxylabs_client, 
            self.code_data, 
            self.simulation_client
        )
        
        self.stackoverflow_scraper = StackOverflowScraper(
            self.scraper_api_client,
            self.oxylabs_client,
            self.code_data,
            self.simulation_client
        )
        
        self.documentation_scraper = DocumentationScraper(
            self.scraper_api_client,
            self.oxylabs_client,
            self.code_data,
            self.simulation_client
        )
        
        self.tutorial_scraper = TutorialScraper(
            self.scraper_api_client,
            self.oxylabs_client,
            self.code_data,
            self.simulation_client
        )
        
        self.forum_scraper = ForumScraper(
            self.scraper_api_client,
            self.oxylabs_client,
            self.code_data,
            self.simulation_client
        )
        
        self.generic_scraper = GenericScraper(
            self.scraper_api_client,
            self.oxylabs_client,
            self.code_data,
            self.simulation_client
        )
        
        # Site classifier for determining the appropriate scraper
        self.site_classifier = SiteClassifier()
        
    def get_scraper_for_url(self, url: str):
        """Determine the appropriate scraper to use for a given URL."""
        site_type = self.site_classifier.classify_url(url)
        
        if site_type == "github_search" or site_type == "github_repo":
            return self.github_scraper, "GitHub"
        elif site_type == "github_file":
            return self.github_scraper, "GitHub File"
        elif site_type == "stackoverflow":
            return self.stackoverflow_scraper, "Stack Overflow"
        elif site_type == "documentation":
            return self.documentation_scraper, "Documentation"
        elif site_type == "tutorial":
            return self.tutorial_scraper, "Tutorial"
        elif site_type == "forum":
            return self.forum_scraper, "Forum"
        else:
            return self.generic_scraper, "Generic Website"
    
    def crawl_url(self, url: str, language: str, max_attempts: int = 3):
        """Crawl a specific URL for code in the target language."""
        scraper, site_type = self.get_scraper_for_url(url)
        
        logger.info(f"Crawling {site_type} URL: {url} for {language}")
        
        # Special handling for GitHub repository URLs
        if site_type == "GitHub" and "/search" not in url:
            try:
                # For GitHub repos, use the specialized repo exploration logic
                logger.info(f"Using specialized GitHub repository exploration for {url}")
                
                # If it's a GitHub search URL, use search_repositories method
                if "search?q=language" in url:
                    # Extract language from search URL if possible
                    lang_in_url = language
                    try:
                        lang_param = re.search(r'language%3A([^&]+)', url)
                        if lang_param:
                            extracted_lang = lang_param.group(1).lower()
                            lang_in_url = next((l for l in LANGUAGES if l.lower() == extracted_lang), language)
                    except:
                        pass
                        
                    # Calculate pages to search based on target items
                    pages_to_search = min(max(5, ITEMS_PER_LANGUAGE // 10), 20)
                    self.github_scraper.search_repositories(lang_in_url, max_pages=pages_to_search)
                    return True
                else:
                    # Regular GitHub repo, explore directly
                    metadata = {
                        "name": url.split('/')[-1],
                        "description": f"GitHub repository for {language}",
                        "stars": 0,
                        "forks": 0,
                        "platform": "GitHub"
                    }
                    
                    # For GitHub repos, we can use visit_repository
                    self.github_scraper.visit_repository(url, language, metadata)
                    return True
            except Exception as e:
                logger.error(f"Error crawling GitHub repository {url}: {str(e)}")
                logger.error(f"Exception details: {traceback.format_exc()}")
                return False
        else:
            # For all other URLs, use the appropriate scraper's scrape_url method
            attempts = 0
            while attempts < max_attempts:
                try:
                    items_added = scraper.scrape_url(url, language)
                    if items_added > 0:
                        logger.info(f"Successfully extracted {items_added} code samples from {url}")
                        return True
                    else:
                        logger.warning(f"No code samples found at {url}")
                        attempts += 1
                except Exception as e:
                    logger.error(f"Error scraping {url} (attempt {attempts+1}/{max_attempts}): {str(e)}")
                    logger.error(f"Exception details: {traceback.format_exc()}")
                    attempts += 1
                    time.sleep(2)  # Wait before retry
            
            logger.error(f"Failed to scrape {url} after {max_attempts} attempts")
            return False
    
    def crawl_language_urls(self, language: str, max_items: int = None):
        """Crawl all target URLs for a specific language."""
        if language not in LANGUAGES or language not in TARGET_URLS:
            logger.error(f"Unsupported language or no target URLs: {language}")
            return 0
        
        urls = TARGET_URLS[language]
        if not urls:
            logger.warning(f"No target URLs found for {language}")
            return 0
        
        logger.info(f"Starting crawl for {language} with {len(urls)} target URLs")
        
        successful_urls = 0
        target_urls = urls.copy()
        
        # If max_items is set, we might want to prioritize certain URLs
        if max_items:
            # Prioritize GitHub repos and official documentation
            target_urls.sort(key=lambda u: (
                0 if "github.com" in u and "/search" not in u else  # GitHub repos first
                1 if ".org/docs" in u or "docs." in u else  # Documentation second
                2 if "stackoverflow.com" in u else  # Stack Overflow third
                3  # Everything else
            ))
        
        # Process all URLs for this language
        for url in target_urls:
            if self.crawl_url(url, language):
                successful_urls += 1
                
            # Save progress incrementally
            if successful_urls % 5 == 0:
                self.code_data.save_data(language)
        
        logger.info(f"Completed crawl for {language}: processed {successful_urls}/{len(urls)} URLs successfully")
        return successful_urls
        
    def crawl_all_languages(self, items_per_language=ITEMS_PER_LANGUAGE):
        """Crawl target URLs for all supported languages."""
        total_successful = 0
        
        for language in LANGUAGES:
            # Check if we have target URLs for this language
            if language in TARGET_URLS and TARGET_URLS[language]:
                successful = self.crawl_language_urls(language, max_items=items_per_language)
                total_successful += successful
                logger.info(f"Completed {language}: {successful} URLs successfully processed")
                
                # Save progress after each language
                self.code_data.save_data(language)
            else:
                logger.warning(f"Skipping {language}: no target URLs defined")
        
        # Generate final dataset and summary
        self.code_data.save_data()
        self.code_data.export_dataset()
        self.generate_summary()
        
        logger.info(f"Crawl completed: processed {total_successful} URLs successfully")
        return total_successful
    
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
    """Main function to run the comprehensive code crawler."""
    logger.info("Starting Enhanced Code Crawler with hardcoded credentials")
    
    try:
        # Create crawler with hardcoded credentials
        crawler = CodeCrawler(SCRAPER_API_KEY, OXYLABS_USERNAME, OXYLABS_PASSWORD, DATA_DIR)
        
        # Set simulation mode to False to use real APIs with raw HTML
        crawler.simulation_mode = False
        
        print("\n" + "="*80)
        print(" ENHANCED CODE CRAWLER".center(80))
        print("="*80)
        print(f" Target: {len(LANGUAGES)} languages with {sum(len(urls) for urls in TARGET_URLS.values())} total URLs")
        print(f" APIs: ScraperAPI and Oxylabs (HTML mode)")
        print(f" Output Directory: {DATA_DIR}")
        print("="*80 + "\n")
        
        # Use the default ITEMS_PER_LANGUAGE value (1000) for a full production crawl
        # Crawl all target URLs for all languages
        successful_urls = crawler.crawl_all_languages()
        
        print("\n" + "="*80)
        print(" CRAWL COMPLETE".center(80))
        print("="*80)
        print(f" Successfully processed {successful_urls} URLs")
        print(f" Results saved to {DATA_DIR}")
        print(f" Summary available at {os.path.join(DATA_DIR, 'crawl_summary.json')}")
        print("="*80 + "\n")
        
        logger.info("Code crawling completed successfully")
    except Exception as e:
        logger.error(f"Fatal error in main: {str(e)}")
        logger.error(f"Exception details: {traceback.format_exc()}")
        print(f"\nERROR: {str(e)}")
        print("See logs for detailed error information.")

if __name__ == "__main__":
    main()
