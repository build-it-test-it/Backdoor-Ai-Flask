#!/usr/bin/env python3
"""
Code Crawler - A web crawler that collects code snippets, repositories, and datasets
for various programming languages using ScraperAPI and Oxylabs to bypass anti-scraping protections.
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
import base64

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

# Constants
SCRAPER_API_KEY = "7e7b5bcfec02306ed3976851d5bb0009"
OXYLABS_USERNAME = "814bdg_5X90h"
OXYLABS_PASSWORD = "Hell___245245"
DATA_DIR = "collected_data"
ITEMS_PER_LANGUAGE = 1000
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
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("ScraperAPI key cannot be empty")
        self.api_key = api_key
        self.base_url = "http://api.scraperapi.com"
        self.session = requests.Session()
        self.request_count = 0
        self.last_request_time = time.time()
        self.lock = Lock()
    
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
    
    def get(self, url: str, render: bool = False, retry_count: int = 3, 
            backoff_factor: float = 2.0) -> Optional[requests.Response]:
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
            
            for attempt in range(retry_count):
                try:
                    logger.info(f"ScraperAPI fetching: {url}")
                    response = self.session.get(proxy_url, timeout=60)
                    self.request_count += 1
                    self.last_request_time = time.time()
                    
                    if response.status_code == 200:
                        return response
                    elif response.status_code in (429, 500, 502, 503):
                        wait_time = backoff_factor ** attempt
                        logger.warning(f"ScraperAPI request failed with status {response.status_code}. "
                                      f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"ScraperAPI request failed with status {response.status_code}: {response.text}")
                        return None
                except requests.RequestException as e:
                    wait_time = backoff_factor ** attempt
                    logger.error(f"ScraperAPI request error: {str(e)}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
            
            logger.error(f"ScraperAPI failed to fetch {url} after {retry_count} attempts")
            return None

class OxylabsClient:
    """Client for interacting with Oxylabs Realtime API."""
    
    def __init__(self, username: str, password: str):
        if not username or not password:
            raise ValueError("Oxylabs credentials cannot be empty")
        self.base_url = "https://realtime.oxylabs.io/v1/queries"
        self.auth = (username, password)
        self.session = requests.Session()
        self.request_count = 0
        self.last_request_time = time.time()
        self.lock = Lock()
    
    def get(self, url: str, render: bool = False, retry_count: int = 3, 
            backoff_factor: float = 2.0) -> Optional[requests.Response]:
        """
        Make a GET request through Oxylabs Realtime API with rate limiting and retries.
        """
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
            
            for attempt in range(retry_count):
                try:
                    logger.info(f"Oxylabs fetching: {url}")
                    response = self.session.post(
                        self.base_url,
                        auth=self.auth,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=60
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
                        
                        return Response(content)
                    elif response.status_code in (429, 500, 502, 503):
                        wait_time = backoff_factor ** attempt
                        logger.warning(f"Oxylabs request failed with status {response.status_code}. "
                                      f"Retrying in {wait_time} seconds...")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"Oxylabs request failed with status {response.status_code}: {response.text}")
                        return None
                except requests.RequestException as e:
                    wait_time = backoff_factor ** attempt
                    logger.error(f"Oxylabs request error: {str(e)}. Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
            
            logger.error(f"Oxylabs failed to fetch {url} after {retry_count} attempts")
            return None

class CodeData:
    """Class for managing and storing collected code data."""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.current_data = {}
        self.global_hashes = set()
        self.lock = Lock()
        self._load_existing_data()
    
    def _load_existing_data(self):
        """Load existing data from JSON files."""
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
                except json.JSONDecodeError:
                    logger.warning(f"Could not load existing data for {lang}, starting fresh")
                    self.current_data[lang] = []
            else:
                self.current_data[lang] = []
    
    def _generate_item_id(self, item: Dict) -> str:
        """Generate a unique ID for an item based on its content."""
        content = item.get('content', '')
        url = item.get('source_url', '')
        input_str = f"{content}{url}"
        return hashlib.md5(input_str.encode('utf-8')).hexdigest()
    
    def add_item(self, language: str, item_type: str, content: str, 
                source_url: str, metadata: Dict = None) -> bool:
        """
        Add a new code item to the dataset.
        """
        if language not in LANGUAGES:
            logger.warning(f"Skipping item with unsupported language: {language}")
            return False
        
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
        """Save collected data to JSON files."""
        languages_to_save = [language] if language else LANGUAGES
        
        for lang in languages_to_save:
            if lang in self.current_data:
                lang_file = os.path.join(self.data_dir, lang, f"{lang.lower()}_data.json")
                try:
                    with open(lang_file, 'w', encoding='utf-8') as f:
                        json.dump(self.current_data[lang], f, indent=2, ensure_ascii=False)
                    logger.info(f"Saved {len(self.current_data[lang])} items for {lang}")
                except Exception as e:
                    logger.error(f"Error saving data for {lang}: {str(e)}")
    
    def export_dataset(self):
        """Export all collected data into a single dataset file."""
        dataset = []
        for lang in LANGUAGES:
            if lang in self.current_data:
                for item in self.current_data[lang]:
                    dataset_item = {
                        "id": item["id"],
                        "language": item["language"],
                        "type": item["type"],
                        "content": item["content"],
                        "source_url": item["source_url"],
                        "timestamp": item["timestamp"],
                        "metadata": item["metadata"]
                    }
                    dataset.append(dataset_item)
        
        dataset_file = os.path.join(DATA_DIR, "code_dataset.json")
        with open(dataset_file, 'w', encoding='utf-8') as f:
            json.dump(dataset, f, indent=2, ensure_ascii=False)
        logger.info(f"Exported dataset with {len(dataset)} items to {dataset_file}")

class LanguageDetector:
    """Utility class to detect programming languages from code samples or file paths."""
    
    @staticmethod
    def detect_from_extension(file_path: str) -> Optional[str]:
        """Detect language based on file extension."""
        _, ext = os.path.splitext(file_path.lower())
        if not ext:
            return None
            
        for lang, extensions in LANGUAGE_FILE_EXTENSIONS.items():
            if ext in extensions:
                return lang
        return None
    
    @staticmethod
    def detect_from_content(content: str) -> Optional[str]:
        """
        Attempt to detect language based on content patterns.
        """
        patterns = {
            "Swift": [r'import\s+Foundation', r'func\s+\w+\s*\([^)]*\)\s*->\s*\w+'],
            "Python": [r'import\s+\w+', r'def\s+\w+\s*\(', r'if\s+__name__\s*==\s*[\'"]__main__[\'"]'],
            "C": [r'#include\s+<\w+\.h>', r'int\s+main\s*\(\s*(?:void|int\s+argc,\s*char\s*\*\s*argv\[\])\s*\)'],
            "C++": [r'#include\s+<iostream>', r'namespace\s+\w+', r'std::'],
            "JavaScript": [r'const\s+\w+\s*=', r'function\s+\w+\s*\(', r'addEventListener'],
            "TypeScript": [r'interface\s+\w+', r':\s*(?:string|number|boolean)', r'<\w+>'],
            "Ruby": [r'require\s+[\'"]\w+[\'"]', r'def\s+\w+\s*(?:\(|$)', r'end$'],
            "C#": [r'using\s+System', r'namespace\s+\w+', r'public\s+class'],
            "Objective-C": [r'#import\s+[<"]\w+\.h[>"]', r'@interface', r'@implementation'],
            "Lua": [r'function\s+\w+\s*\(', r'local\s+\w+\s*=', r'end$']
        }
        
        scores = {lang: 0 for lang in LANGUAGES}
        
        for lang, regex_list in patterns.items():
            for regex in regex_list:
                if re.search(regex, content):
                    scores[lang] += 1
        
        max_score = max(scores.values())
        if max_score > 0:
            best_matches = [lang for lang, score in scores.items() if score == max_score]
            return best_matches[0]
        
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
        
       名 for item in file_items:
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