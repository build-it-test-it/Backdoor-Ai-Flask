#!/usr/bin/env python3
"""
Code Crawler - A web crawler that collects code snippets, repositories, and datasets
for various programming languages using ScraperAPI to bypass anti-scraping protections.
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
DATA_DIR = "collected_data"
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
        self.api_key = api_key
        self.base_url = "http://api.scraperapi.com"
        self.session = requests.Session()
        self.request_count = 0
        self.last_request_time = time.time()
    
    def _get_proxy_url(self, url: str, render: bool = False) -> str:
        """Create a ScraperAPI proxy URL for the target URL."""
        params = {
            "api_key": self.api_key,
            "url": url,
        }
        if render:
            params["render"] = "true"
        
        param_str = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.base_url}/?{param_str}"
    
    def get(self, url: str, render: bool = False, retry_count: int = 3, 
            backoff_factor: float = 2.0) -> Optional[requests.Response]:
        """
        Make a GET request through ScraperAPI with rate limiting and retries.
        """
        # Implement rate limiting (max 60 requests per minute)
        current_time = time.time()
        elapsed = current_time - self.last_request_time
        if elapsed < 1.0 and self.request_count >= 60:
            sleep_time = 1.0 - elapsed
            logger.info(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
            self.request_count = 0
        
        proxy_url = self._get_proxy_url(url, render)
        
        for attempt in range(retry_count):
            try:
                logger.info(f"Fetching: {url}")
                response = self.session.get(proxy_url, timeout=60)
                self.request_count += 1
                self.last_request_time = time.time()
                
                if response.status_code == 200:
                    return response
                elif response.status_code in (429, 500, 502, 503):
                    wait_time = backoff_factor ** attempt
                    logger.warning(f"Request failed with status {response.status_code}. "
                                  f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Request failed with status {response.status_code}: {response.text}")
                    return None
            except requests.RequestException as e:
                wait_time = backoff_factor ** attempt
                logger.error(f"Request error: {str(e)}. Retrying in {wait_time} seconds...")
                time.sleep(wait_time)
        
        logger.error(f"Failed to fetch {url} after {retry_count} attempts")
        return None

class CodeData:
    """Class for managing and storing collected code data."""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.current_data = {}
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
        
        Args:
            language: Programming language of the code
            item_type: Type of item (snippet, codebase, dataset, documentation)
            content: The code or description content
            source_url: URL where the content was found
            metadata: Additional metadata
            
        Returns:
            Boolean indicating whether item was added (True) or was duplicate (False)
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
        
        # Generate ID and check for duplicates
        item_id = self._generate_item_id(item)
        item["id"] = item_id
        
        # Check if this item already exists
        for existing_item in self.current_data[language]:
            if existing_item.get("id") == item_id:
                logger.debug(f"Skipping duplicate item with ID {item_id}")
                return False
        
        self.current_data[language].append(item)
        logger.info(f"Added new {item_type} for {language} from {source_url[:50]}...")
        
        # Save periodically (every 10 items)
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
        This is a simplified implementation - real-world usage would
        benefit from more sophisticated language detection.
        """
        # Language-specific patterns
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
        
        # Find language with highest score
        max_score = max(scores.values())
        if max_score > 0:
            best_matches = [lang for lang, score in scores.items() if score == max_score]
            return best_matches[0]
        
        return None

class BaseScraper:
    """Base class for platform-specific scrapers."""
    
    def __init__(self, api_client: ScraperAPIClient, code_data: CodeData):
        self.api_client = api_client
        self.code_data = code_data
        self.visited_urls = set()
    
    def is_url_visited(self, url: str) -> bool:
        """Check if URL has already been visited."""
        return url in self.visited_urls
    
    def mark_url_visited(self, url: str):
        """Mark URL as visited."""
        self.visited_urls.add(url)
    
    def extract_code_blocks(self, html_content: str) -> List[Tuple[str, Optional[str]]]:
        """
        Extract code blocks from HTML content.
        Returns a list of tuples (code_content, language)
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        code_blocks = []
        
        # Look for <pre><code> or <code> elements
        for pre in soup.find_all('pre'):
            code = pre.find('code')
            if code:
                # Try to determine language from class
                language = None
                if code.get('class'):
                    class_list = code.get('class')
                    lang_classes = [c for c in class_list if c.startswith(('language-', 'lang-'))]
                    if lang_classes:
                        lang_class = lang_classes[0]
                        detected_lang = lang_class.split('-', 1)[1]
                        language = next((l for l in LANGUAGES if l.lower() == detected_lang.lower()), None)
                
                # If language not determined from class, try content analysis
                if not language and code.text:
                    language = LanguageDetector.detect_from_content(code.text)
                
                code_blocks.append((code.text.strip(), language))
        
        # Also find standalone <code> blocks that might contain snippets
        for code in soup.find_all('code', class_=True):
            if code.parent.name != 'pre':  # Skip those already processed
                class_list = code.get('class')
                language = None
                
                # Try to determine language from class
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
    
    def search_repositories(self, language: str, max_pages: int = 5):
        """Search for repositories in a specific language."""
        for page in range(1, max_pages + 1):
            search_url = f"https://github.com/search?q=language%3A{language.lower()}&type=repositories&p={page}"
            response = self.api_client.get(search_url)
            
            if not response:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            repo_elements = soup.select('.repo-list-item')
            
            for repo_element in repo_elements:
                # Extract repository URL
                repo_link = repo_element.select_one('a[href^="/"]')
                if not repo_link:
                    continue
                
                repo_url = urljoin("https://github.com", repo_link['href'])
                
                # Skip if already visited
                if self.is_url_visited(repo_url):
                    continue
                
                # Extract repository description
                description_elem = repo_element.select_one('p')
                description = description_elem.get_text().strip() if description_elem else ""
                
                # Get repository metadata
                metadata = {
                    "name": repo_link.get_text().strip(),
                    "description": description,
                    "stars": 0,  # Will be updated when we visit the repo
                    "forks": 0   # Will be updated when we visit the repo
                }
                
                # Visit repository to get more details
                self.visit_repository(repo_url, language, metadata)
                
                # Mark as visited
                self.mark_url_visited(repo_url)
                
                # Small delay to avoid hitting rate limits
                time.sleep(random.uniform(1.0, 3.0))
    
    def visit_repository(self, repo_url: str, language: str, metadata: Dict):
        """Visit a repository to extract code samples and additional metadata."""
        response = self.api_client.get(repo_url)
        if not response:
            return
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Update metadata with stars and forks
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
        
        # Save repository info
        self.code_data.add_item(
            language=language,
            item_type="codebase",
            content=f"GitHub repository: {metadata.get('name', 'Unknown')}",
            source_url=repo_url,
            metadata=metadata
        )
        
        # Explore repository structure to find code files
        self._explore_repo_files(repo_url, language)
    
    def _explore_repo_files(self, repo_url: str, primary_language: str, path: str = "", max_depth: int = 2, current_depth: int = 0):
        """Recursively explore repository files to extract code."""
        if current_depth > max_depth:
            return
            
        # Construct URL for the current path
        explore_url = repo_url
        if path:
            explore_url = f"{repo_url}/tree/master/{path}"
            
        response = self.api_client.get(explore_url)
        if not response:
            return
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find file and directory links
        file_items = soup.select('a[role="row"]')
        
        for item in file_items:
            item_type = "file" if "file" in str(item) else "directory"
            item_link = item.get('href')
            
            if not item_link:
                continue
                
            item_name = item_link.split("/")[-1]
            item_path = path + "/" + item_name if path else item_name
            item_url = urljoin("https://github.com", item_link)
            
            # Skip if already visited
            if self.is_url_visited(item_url):
                continue
                
            # Skip non-code files
            if item_type == "file":
                detected_language = LanguageDetector.detect_from_extension(item_name)
                
                # Skip files that aren't in our target languages
                if not detected_language:
                    continue
                    
                # Extract code from file
                self._extract_file_content(item_url, detected_language)
            elif item_type == "directory" and current_depth < max_depth:
                # Recursively explore subdirectories
                self._explore_repo_files(repo_url, primary_language, item_path, max_depth, current_depth + 1)
                
            # Mark as visited
            self.mark_url_visited(item_url)
            
            # Small delay
            time.sleep(random.uniform(0.5, 1.5))
    
    def _extract_file_content(self, file_url: str, language: str):
        """Extract code content from a GitHub file."""
        response = self.api_client.get(file_url)
        if not response:
            return
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find the code content
        code_element = soup.select_one('table.highlight')
        if not code_element:
            return
            
        # Extract code lines
        code_lines = []
        for line in code_element.select('tr'):
            line_content = line.select_one('td.blob-code')
            if line_content:
                code_lines.append(line_content.get_text(strip=True))
                
        code_content = "\n".join(code_lines)
        
        if not code_content.strip():
            return
            
        # Extract filename from URL
        filename = file_url.split("/")[-1]
        
        # Add to database
        self.code_data.add_item(
            language=language,
            item_type="snippet",
            content=code_content,
            source_url=file_url,
            metadata={
                "filename": filename,
                "repo_url": "/".join(file_url.split("/")[:5])  # Extract base repo URL
            }
        )

class StackOverflowScraper(BaseScraper):
    """Scraper for Stack Overflow code snippets."""
    
    def search_questions(self, language: str, max_pages: int = 5):
        """Search for questions related to a specific language."""
        for page in range(1, max_pages + 1):
            search_url = f"https://stackoverflow.com/questions/tagged/{language.lower()}?tab=votes&page={page}"
            response = self.api_client.get(search_url)
            
            if not response:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            question_summaries = soup.select('.s-post-summary')
            
            for summary in question_summaries:
                # Extract question link
                link_elem = summary.select_one('a.s-link')
                if not link_elem:
                    continue
                    
                question_url = urljoin("https://stackoverflow.com", link_elem['href'])
                
                # Skip if already visited
                if self.is_url_visited(question_url):
                    continue
                
                # Extract title
                title = link_elem.get_text().strip()
                
                # Visit question page to extract code snippets
                self.extract_from_question(question_url, language, title)
                
                # Mark as visited
                self.mark_url_visited(question_url)
                
                # Small delay
                time.sleep(random.uniform(1.0, 3.0))
    
    def extract_from_question(self, question_url: str, language: str, title: str):
        """Extract code snippets from a question page."""
        response = self.api_client.get(question_url)
        if not response:
            return
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Process question and answers
        post_elements = soup.select('.js-post-body')
        
        for post_idx, post in enumerate(post_elements):
            # Extract code blocks
            code_blocks = self.extract_code_blocks(str(post))
            
            for idx, (code, detected_lang) in enumerate(code_blocks):
                if not code.strip():
                    continue
                
                # Use provided language if detected_lang is None
                code_language = detected_lang if detected_lang else language
                
                # Skip if not in our target languages
                if code_language not in LANGUAGES:
                    continue
                
                # Add metadata about post type
                post_type = "question" if post_idx == 0 else "answer"
                
                # Add to database
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
    
    def search_subreddits(self, language: str, max_pages: int = 3):
        """Search for code in programming subreddits."""
        # Define relevant subreddits for each language
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
        
        for subreddit in subreddits:
            for sort in ["top", "hot"]:
                search_url = f"https://www.reddit.com/r/{subreddit}/{sort}.json?limit=25"
                
                # Reddit requires User-Agent header
                headers = {
                    "User-Agent": "CodeCrawler/1.0"
                }
                
                # Use ScraperAPI to get the data
                response = self.api_client.get(search_url)
                
                if not response:
                    continue
                    
                try:
                    data = response.json()
                    posts = data.get("data", {}).get("children", [])
                    
                    for post in posts:
                        post_data = post.get("data", {})
                        permalink = post_data.get("permalink")
                        
                        if not permalink:
                            continue
                            
                        post_url = f"https://www.reddit.com{permalink}"
                        
                        # Skip if already visited
                        if self.is_url_visited(post_url):
                            continue
                        
                        # Visit post to extract code
                        self.extract_from_post(post_url, language)
                        
                        # Mark as visited
                        self.mark_url_visited(post_url)
                        
                        # Small delay
                        time.sleep(random.uniform(1.0, 3.0))
                        
                except Exception as e:
                    logger.error(f"Error processing Reddit data: {str(e)}")
    
    def extract_from_post(self, post_url: str, language: str):
        """Extract code snippets from a Reddit post."""
        response = self.api_client.get(post_url)
        if not response:
            return
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract title
        title_elem = soup.select_one('h1')
        title = title_elem.get_text().strip() if title_elem else "Unknown Title"
        
        # Process post text and comments for code blocks
        post_elements = soup.select('.usertext-body')
        
        for post in post_elements:
            # Extract code blocks
            code_blocks = self.extract_code_blocks(str(post))
            
            for code, detected_lang in code_blocks:
                if not code.strip():
                    continue
                
                # Use provided language if detected_lang is None
                code_language = detected_lang if detected_lang else language
                
                # Skip if not in our target languages
                if code_language not in LANGUAGES:
                    continue
                
                # Add to database
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
    
    def search_recent_pastes(self, language: str, max_pages: int = 2):
        """Search for code in recent public pastes."""
        # Map our language names to Pastebin syntax highlighting options
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
        
        # Search recent pastes
        for page in range(1, max_pages + 1):
            search_url = f"https://pastebin.com/archive/{page}"
            response = self.api_client.get(search_url)
            
            if not response:
                continue
                
            soup = BeautifulSoup(response.text, 'html.parser')
            paste_elements = soup.select('table.maintable tr')
            
            for paste in paste_elements[1:]:  # Skip header row
                try:
                    # Extract paste link and language
                    cells = paste.find_all('td')
                    if len(cells) < 3:
                        continue
                        
                    link_elem = cells[0].find('a')
                    paste_lang_elem = cells[2]
                    
                    if not link_elem or not paste_lang_elem:
                        continue
                        
                    paste_url = urljoin("https://pastebin.com", link_elem['href'])
                    paste_lang = paste_lang_elem.get_text().strip().lower()
                    
                    # Skip if already visited
                    if self.is_url_visited(paste_url):
                        continue
                    
                    # Check if this paste is for our target language
                    if pastebin_lang in paste_lang:
                        self.extract_from_paste(paste_url, language)
                    
                    # Mark as visited
                    self.mark_url_visited(paste_url)
                    
                    # Small delay
                    time.sleep(random.uniform(1.0, 2.0))
                    
                except Exception as e:
                    logger.error(f"Error processing Pastebin element: {str(e)}")
    
    def extract_from_paste(self, paste_url: str, language: str):
        """Extract code from a Pastebin paste."""
        response = self.api_client.get(paste_url)
        if not response:
            return
            
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract paste title
        title_elem = soup.select_one('.info-top')
        title = title_elem.get_text().strip() if title_elem else "Untitled Paste"
        
        # Extract code content
        code_elem = soup.select_one('.source')
        if not code_elem:
            code_elem = soup.select_one('.text')
            
        if not code_elem:
            return
            
        code_content = code_elem.get_text().strip()
        
        if not code_content:
            return
            
        # Verify language by content if needed
        detected_lang = LanguageDetector.detect_from_content(code_content)
        
        # Use detected language if available, otherwise use provided language
        code_language = detected_lang if detected_lang else language
        
        # Skip if not in our target languages
        if code_language not in LANGUAGES:
            return
            
        # Add to database
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

class CodeCrawler:
    """Main crawler class that coordinates the scraping process."""
    
    def __init__(self, api_key: str, data_dir: str):
        self.api_client = ScraperAPIClient(api_key)
        self.code_data = CodeData(data_dir)
        
        # Initialize platform-specific scrapers
        self.github_scraper = GitHubScraper(self.api_client, self.code_data)
        self.stackoverflow_scraper = StackOverflowScraper(self.api_client, self.code_data)
        self.reddit_scraper = RedditScraper(self.api_client, self.code_data)
        self.pastebin_scraper = PastebinScraper(self.api_client, self.code_data)
    
    def crawl_for_language(self, language: str, max_items: int = 100):
        """
        Crawl various platforms for code in a specific language.
        
        Args:
            language: The programming language to search for
            max_items: Maximum number of items to collect
        """
        logger.info(f"Starting crawl for {language} (target: {max_items} items)")
        
        # Keep track of items collected
        initial_count = len(self.code_data.current_data.get(language, []))
        
        # Define crawling steps with weights
        crawl_steps = [
            # (platform, method, weight)
            ("GitHub", self.github_scraper.search_repositories, 0.4),
            ("Stack Overflow", self.stackoverflow_scraper.search_questions, 0.3),
            ("Reddit", self.reddit_scraper.search_subreddits, 0.2),
            ("Pastebin", self.pastebin_scraper.search_recent_pastes, 0.1)
        ]
        
        # Calculate items to collect from each platform
        platform_targets = {}
        for platform, _, weight in crawl_steps:
            platform_targets[platform] = int(max_items * weight)
        
        # Crawl each platform
        for platform, method, _ in crawl_steps:
            target = platform_targets[platform]
            logger.info(f"Crawling {platform} for {language} (target: {target} items)")
            
            try:
                method(language)
            except Exception as e:
                logger.error(f"Error crawling {platform} for {language}: {str(e)}")
            
            # Save data after each platform
            self.code_data.save_data(language)
            
            # Check if we've collected enough items
            current_count = len(self.code_data.current_data.get(language, []))
            new_items = current_count - initial_count
            logger.info(f"Collected {new_items} new items for {language} from {platform}")
            
            if current_count >= max_items:
                logger.info(f"Reached target of {max_items} items for {language}")
                break
    
    def crawl_all_languages(self, items_per_language: int = 100):
        """Crawl for all supported languages."""
        for language in LANGUAGES:
            self.crawl_for_language(language, items_per_language)
            
        # Final save of all data
        self.code_data.save_data()
        
        # Generate summary
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
        
        # Calculate statistics
        for language in LANGUAGES:
            items = self.code_data.current_data.get(language, [])
            lang_count = len(items)
            summary["total_items"] += lang_count
            summary["by_language"][language] = lang_count
            
            # Count by type
            for item in items:
                item_type = item.get("type", "unknown")
                summary["by_type"][item_type] = summary["by_type"].get(item_type, 0) + 1
                
                # Count by platform
                platform = item.get("metadata", {}).get("platform", "unknown")
                summary["by_platform"][platform] = summary["by_platform"].get(platform, 0) + 1
        
        # Save summary to file
        summary_file = os.path.join(DATA_DIR, "crawl_summary.json")
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
            
        logger.info(f"Generated summary: collected {summary['total_items']} items across {len(LANGUAGES)} languages")
        
        # Print summary to console
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
        print("="*50 + "\n")

def main():
    """Main function to run the code crawler."""
    logger.info("Starting Code Crawler")
    
    # Create crawler
    crawler = CodeCrawler(SCRAPER_API_KEY, DATA_DIR)
    
    # Let user select languages or crawl all
    print("Available languages:")
    for i, lang in enumerate(LANGUAGES, 1):
        print(f"{i}. {lang}")
    print(f"{len(LANGUAGES) + 1}. All languages")
    
    choice = input("\nSelect language(s) to crawl (comma-separated numbers or 'all'): ")
    
    items_per_language = int(input("How many items to collect per language: ") or "100")
    
    if choice.lower() == 'all':
        selected_languages = LANGUAGES
    else:
        try:
            indices = [int(x.strip()) - 1 for x in choice.split(',')]
            selected_languages = [LANGUAGES[i] for i in indices if 0 <= i < len(LANGUAGES)]
        except ValueError:
            logger.error("Invalid selection, defaulting to all languages")
            selected_languages = LANGUAGES
    
    # Crawl selected languages
    for language in selected_languages:
        crawler.crawl_for_language(language, items_per_language)
    
    # Generate summary
    crawler.generate_summary()
    
    logger.info("Code crawling completed")

if __name__ == "__main__":
    main()
