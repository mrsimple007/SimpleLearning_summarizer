import logging
import aiohttp
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
import asyncio
from typing import Optional, Tuple
import re

logger = logging.getLogger(__name__)

class WebContentExtractor:
    def __init__(self):
        self.chrome_options = Options()
        self.chrome_options.add_argument('--headless')
        self.chrome_options.add_argument('--no-sandbox')
        self.chrome_options.add_argument('--disable-dev-shm-usage')
        self.chrome_options.add_argument('--disable-gpu')
        self.chrome_options.add_argument('--window-size=1920,1080')
        self.chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')

    def is_robot_check(self, text: str) -> bool:
        robot_phrases = [
            "please confirm that you are not a robot",
            "we're sorry, but it looks like requests sent from your device are automated",
            "captcha",
            "verify you are human",
            "robot check",
            "automated request"
        ]
        return any(phrase.lower() in text.lower() for phrase in robot_phrases)

    def clean_text(self, text: str) -> str:
        # Remove robot check messages
        text = re.sub(r'Please confirm that you and not a robot.*?Why might th\.\.\.', '', text, flags=re.DOTALL)
        text = re.sub(r"We're sorry, but it looks like requests sent from your device are automated.*?Why might th\.\.\.", '', text, flags=re.DOTALL)
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text

    async def extract_with_selenium(self, url: str) -> Tuple[bool, str]:
        try:
            driver = webdriver.Chrome(options=self.chrome_options)
            driver.get(url)
            
            # Wait for content to load
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Get the page source
            html = driver.page_source
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            
            # Remove unwanted elements
            for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside', 'ads', 'iframe']):
                element.decompose()
            
            # Try to find main content
            main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content') or soup
            
            # Extract text
            text = main_content.get_text(separator='\n')
            
            # Clean up text
            text = self.clean_text(text)
            
            # Check for robot verification
            if self.is_robot_check(text):
                return False, "Robot verification required"
            
            driver.quit()
            return True, text
        except Exception as e:
            logger.error(f"Selenium extraction failed for {url}: {e}")
            if 'driver' in locals():
                driver.quit()
            return False, str(e)

    async def extract_with_scrapy(self, url: str) -> Tuple[bool, str]:
        try:
            class WebSpider(scrapy.Spider):
                name = 'web_spider'
                start_urls = [url]
                
                def parse(self, response):
                    # Remove unwanted elements
                    for selector in ['script', 'style', 'header', 'footer', 'nav', 'aside', 'ads', 'iframe']:
                        response.css(selector).drop()
                    
                    # Try to find main content
                    main_content = response.css('main, article, div.content').get() or response.body.decode()
                    
                    # Extract text
                    text = ' '.join(main_content.split())
                    return {'text': text}

            process = CrawlerProcess(get_project_settings())
            process.crawl(WebSpider)
            process.start()
            
            # Get the result from the spider
            result = process.crawler.stats.get_value('item_scraped_count', 0)
            if result > 0:
                text = process.crawler.stats.get_value('text', '')
                text = self.clean_text(text)
                
                if self.is_robot_check(text):
                    return False, "Robot verification required"
                    
                return True, text
            return False, "No content found"
        except Exception as e:
            logger.error(f"Scrapy extraction failed for {url}: {e}")
            return False, str(e)

    async def extract_with_requests(self, url: str) -> Tuple[bool, str]:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
                'TE': 'Trailers'
            }
            
            timeout = aiohttp.ClientTimeout(total=30)
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, 
                    headers=headers, 
                    timeout=timeout, 
                    allow_redirects=True,
                    ssl=False
                ) as response:
                    if response.status == 200:
                        html = await response.text()
                        soup = BeautifulSoup(html, 'html.parser')
                        
                        for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside', 'ads', 'iframe']):
                            element.decompose()
                        
                        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_='content') or soup
                        
                        text = main_content.get_text(separator='\n')
                        text = self.clean_text(text)
                        
                        if self.is_robot_check(text):
                            return False, "Robot verification required"
                        
                        return True, text
                    else:
                        return False, f"Error: Could not access the website (Status code: {response.status})"
        except Exception as e:
            logger.error(f"Requests extraction failed for {url}: {e}")
            return False, str(e)

async def extract_text_from_url(url: str) -> str:
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url

    extractor = WebContentExtractor()
    
    # Try each method in sequence
    methods = [
        extractor.extract_with_selenium,
        extractor.extract_with_scrapy,
        extractor.extract_with_requests
    ]
    
    for method in methods:
        success, result = await method(url)
        if success and result and len(result) > 100:
            return result
    
    # If all methods fail, return the last error message
    return f"Error: Could not extract content from URL. All methods failed. Last error: {result}" 