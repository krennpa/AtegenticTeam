"""
Web scraping module with support for HTML, iframes, and PDFs.
"""

from .scraper import WebScraper, scrape_url, scrape_urls

__all__ = ['WebScraper', 'scrape_url', 'scrape_urls']
