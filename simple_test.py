#!/usr/bin/env python3
"""
Simplified test of key components from Scrapper.py
"""

import os
import logging
import json
import re
import hashlib
from typing import Dict, Optional
from functools import lru_cache
from threading import Lock

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SimpleTest")

# Constants
LANGUAGES = ["Python", "JavaScript", "TypeScript", "C", "C++"]
LANGUAGE_FILE_EXTENSIONS = {
    "Python": [".py", ".ipynb"],
    "JavaScript": [".js", ".jsx", ".mjs"],
    "TypeScript": [".ts", ".tsx"],
    "C": [".c", ".h"],
    "C++": [".cpp", ".hpp", ".cc"]
}

class LanguageDetector:
    """Simplified version of LanguageDetector"""
    
    EXTENSION_CACHE = {}
    
    @classmethod
    @lru_cache(maxsize=1024)
    def detect_from_extension(cls, file_path: str) -> Optional[str]:
        """Detect language based on file extension."""
        if not file_path:
            return None
            
        _, ext = os.path.splitext(file_path.lower())
        if not ext:
            return None
            
        if ext in cls.EXTENSION_CACHE:
            return cls.EXTENSION_CACHE[ext]
            
        for lang, extensions in LANGUAGE_FILE_EXTENSIONS.items():
            if ext in extensions:
                cls.EXTENSION_CACHE[ext] = lang
                return lang
                
        cls.EXTENSION_CACHE[ext] = None
        return None

    @classmethod
    def detect_from_content(cls, content: str) -> Optional[str]:
        """Simple content-based detection."""
        if not content or len(content) < 10:
            return None
            
        patterns = {
            "Python": [r'import\s+\w+', r'def\s+\w+', r'if\s+__name__'],
            "JavaScript": [r'const\s+\w+', r'function\s+\w+', r'document\.'],
            "TypeScript": [r'interface\s+\w+', r':\s*string', r'<\w+>'],
            "C": [r'#include', r'int\s+main', r'printf'],
            "C++": [r'namespace', r'std::', r'class\s+\w+']
        }
        
        scores = {lang: 0 for lang in patterns}
        
        for lang, regexes in patterns.items():
            for regex in regexes:
                if re.search(regex, content):
                    scores[lang] += 1
                    
        if not scores:
            return None
            
        max_score = max(scores.values())
        if max_score > 0:
            candidates = [lang for lang, score in scores.items() if score == max_score]
            return candidates[0]
            
        return None

class SimpleCodeData:
    """Simplified version of CodeData for testing"""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        self.data = {}
        self.hashes = set()
        self.lock = Lock()
        os.makedirs(data_dir, exist_ok=True)
        
    def _generate_id(self, content: str, url: str) -> str:
        """Generate a unique ID for an item."""
        input_str = f"{content}{url}"
        return hashlib.md5(input_str.encode('utf-8')).hexdigest()
        
    def add_item(self, language: str, content: str, url: str, metadata: Dict = None) -> bool:
        """Add a new code item."""
        if language not in LANGUAGES:
            return False
            
        if language not in self.data:
            self.data[language] = []
            
        item_id = self._generate_id(content, url)
        
        with self.lock:
            if item_id in self.hashes:
                return False
                
            item = {
                "id": item_id,
                "language": language,
                "content": content,
                "url": url,
                "metadata": metadata or {}
            }
            
            self.data[language].append(item)
            self.hashes.add(item_id)
            
        return True
        
    def save(self, language: str = None):
        """Save data to a file."""
        languages = [language] if language else list(self.data.keys())
        
        for lang in languages:
            if lang in self.data:
                lang_dir = os.path.join(self.data_dir, lang)
                os.makedirs(lang_dir, exist_ok=True)
                
                file_path = os.path.join(lang_dir, f"{lang.lower()}_data.json")
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(self.data[lang], f)
                    
                logger.info(f"Saved {len(self.data[lang])} items for {lang}")

def test_language_detector():
    """Test the LanguageDetector."""
    logger.info("Testing LanguageDetector...")
    
    # Test file extension detection
    python_file = "test.py"
    js_file = "script.js"
    
    py_detected = LanguageDetector.detect_from_extension(python_file)
    js_detected = LanguageDetector.detect_from_extension(js_file)
    
    logger.info(f"Python file detected as: {py_detected}")
    logger.info(f"JavaScript file detected as: {js_detected}")
    
    # Test content detection
    python_code = """
import os
import sys

def main():
    print("Hello, world!")
    
if __name__ == "__main__":
    main()
"""
    
    js_code = """
const greeting = "Hello, world!";
function displayGreeting() {
    document.getElementById("greeting").innerText = greeting;
}
"""
    
    py_content_detected = LanguageDetector.detect_from_content(python_code)
    js_content_detected = LanguageDetector.detect_from_content(js_code)
    
    logger.info(f"Python content detected as: {py_content_detected}")
    logger.info(f"JavaScript content detected as: {js_content_detected}")
    
    return py_detected == "Python" and js_detected == "JavaScript"

def test_code_data():
    """Test the SimpleCodeData."""
    logger.info("Testing CodeData...")
    
    # Create a temporary directory
    test_dir = "simple_test_data"
    os.makedirs(test_dir, exist_ok=True)
    
    # Initialize data store
    code_data = SimpleCodeData(test_dir)
    
    # Add items
    python_added = code_data.add_item(
        language="Python",
        content="print('Hello, world!')",
        url="https://example.com/py",
        metadata={"type": "snippet"}
    )
    
    js_added = code_data.add_item(
        language="JavaScript",
        content="console.log('Hello, world!');",
        url="https://example.com/js",
        metadata={"type": "snippet"}
    )
    
    # Save data
    code_data.save()
    
    # Check if files exist
    py_file = os.path.join(test_dir, "Python", "python_data.json")
    js_file = os.path.join(test_dir, "JavaScript", "javascript_data.json")
    
    py_exists = os.path.exists(py_file)
    js_exists = os.path.exists(js_file)
    
    logger.info(f"Python data file exists: {py_exists}")
    logger.info(f"JavaScript data file exists: {js_exists}")
    
    return python_added and js_added and py_exists and js_exists

def main():
    """Run the tests."""
    logger.info("Running simplified tests...")
    
    tests = [
        ("LanguageDetector", test_language_detector),
        ("CodeData", test_code_data)
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            result = test_func()
            results[name] = "PASS" if result else "FAIL"
        except Exception as e:
            logger.error(f"Error in {name}: {str(e)}")
            results[name] = f"ERROR: {str(e)}"
    
    # Print results
    logger.info("\n--- TEST RESULTS ---")
    for name, result in results.items():
        logger.info(f"{name}: {result}")
    
    # Clean up
    import shutil
    if os.path.exists("simple_test_data"):
        shutil.rmtree("simple_test_data")
        
    logger.info("Tests completed.")

if __name__ == "__main__":
    main()
