#!/usr/bin/env python3
"""
Test script for Scrapper.py to verify code quality and functionality.
"""

import os
import logging
from notebooks.Scrapper import (
    LanguageDetector, 
    CodeData,
    ScraperAPIClient,
    OxylabsClient,
    CodeCrawler
)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestScrapper")

def test_language_detector():
    """Test the LanguageDetector class."""
    logger.info("Testing LanguageDetector...")
    
    # Test file extension detection
    python_file = "test.py"
    detected = LanguageDetector.detect_from_extension(python_file)
    logger.info(f"Detected language for {python_file}: {detected}")
    
    # Test content detection
    python_code = """
import os
import sys

def main():
    print("Hello, world!")
    
if __name__ == "__main__":
    main()
"""
    detected = LanguageDetector.detect_from_content(python_code)
    logger.info(f"Detected language from content: {detected}")
    
    # Test combined method
    detected = LanguageDetector.detect_language(content=python_code, file_path=python_file)
    logger.info(f"Detected language using combined method: {detected}")
    
    return detected == "Python"

def test_code_data():
    """Test the CodeData class."""
    logger.info("Testing CodeData...")
    
    # Create a temporary test directory
    test_dir = "test_data"
    if not os.path.exists(test_dir):
        os.makedirs(test_dir)
    
    # Initialize CodeData
    code_data = CodeData(test_dir, use_compression=False)
    
    # Test adding an item
    result = code_data.add_item(
        language="Python",
        item_type="snippet",
        content="print('Hello, world!')",
        source_url="https://example.com/test",
        metadata={"test": True}
    )
    
    # Save data
    code_data.save_data("Python")
    
    # Check if file was created
    data_file = os.path.join(test_dir, "Python", "python_data.json")
    file_exists = os.path.exists(data_file)
    logger.info(f"Data file created: {file_exists}")
    
    return result and file_exists

def test_api_clients():
    """Test creating API clients (no actual API calls)."""
    logger.info("Testing API clients...")
    
    # Create ScraperAPI client
    scraper_client = ScraperAPIClient("test_key")
    logger.info(f"ScraperAPI client created: {scraper_client is not None}")
    
    # Create Oxylabs client
    oxylabs_client = OxylabsClient("test_user", "test_pass")
    logger.info(f"Oxylabs client created: {oxylabs_client is not None}")
    
    return scraper_client is not None and oxylabs_client is not None

def test_code_crawler():
    """Test CodeCrawler initialization (no actual crawling)."""
    logger.info("Testing CodeCrawler...")
    
    # Create CodeCrawler
    crawler = CodeCrawler("test_key", "test_user", "test_pass", "test_data")
    logger.info(f"CodeCrawler created: {crawler is not None}")
    
    # Check if scrapers were initialized
    has_github = hasattr(crawler, "github_scraper")
    has_stackoverflow = hasattr(crawler, "stackoverflow_scraper")
    logger.info(f"GitHub scraper: {has_github}, StackOverflow scraper: {has_stackoverflow}")
    
    return crawler is not None and has_github and has_stackoverflow

def main():
    """Run all tests."""
    logger.info("Starting Scrapper.py tests...")
    
    tests = [
        ("LanguageDetector", test_language_detector),
        ("CodeData", test_code_data),
        ("API Clients", test_api_clients),
        ("CodeCrawler", test_code_crawler)
    ]
    
    results = {}
    for name, test_func in tests:
        try:
            result = test_func()
            results[name] = "PASS" if result else "FAIL"
        except Exception as e:
            logger.error(f"Error testing {name}: {str(e)}")
            results[name] = f"ERROR: {str(e)}"
    
    # Print results
    logger.info("\n--- TEST RESULTS ---")
    for name, result in results.items():
        logger.info(f"{name}: {result}")
    
    # Clean up
    logger.info("Cleaning up test files...")
    import shutil
    if os.path.exists("test_data"):
        shutil.rmtree("test_data")
    
    logger.info("Tests completed.")

if __name__ == "__main__":
    main()
