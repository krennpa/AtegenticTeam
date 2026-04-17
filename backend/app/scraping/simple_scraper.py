#!/usr/bin/env python3
"""
Simple HTTP-based scraper as fallback for Windows Playwright issues.
Uses httpx + BeautifulSoup for basic HTML scraping.
"""

import time
import httpx
from typing import Dict, Any
from bs4 import BeautifulSoup


async def scrape_url_simple(url: str, timeout: int = 30) -> Dict[str, Any]:
    """Simple HTTP scraper without browser automation.
    
    Args:
        url: URL to scrape
        timeout: Request timeout in seconds
        
    Returns:
        Dict with content, metadata
    """
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            follow_redirects=True,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script, style, and other non-content elements
            for script in soup(["script", "style", "noscript"]):
                script.decompose()
            
            # Extract raw text with proper spacing
            text_content = soup.get_text(separator='\n', strip=True)
            
            # Clean up excessive whitespace while preserving structure
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            text_content = '\n'.join(lines)
            
            duration = time.time() - start_time
            
            return {
                'success': True,
                'url': url,
                'content': text_content,
                'content_length': len(text_content),
                'word_count': len(text_content.split()) if text_content else 0,
                'duration': duration,
                'status_code': response.status_code,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'scraper_type': 'simple_http'
            }
            
    except Exception as e:
        return {
            'success': False,
            'url': url,
            'error': str(e),
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'scraper_type': 'simple_http'
        }
