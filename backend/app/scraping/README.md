# Web Scraping Module

Generic web scraper using **crawl4ai** for extracting content from any website.

## Features

- ✅ **Simple & Generic**: Works for most websites out of the box
- ✅ **Dynamic Content**: Handles JavaScript-heavy sites automatically
- ✅ **Cookie Consent**: Automatically handles cookie banners
- ✅ **Lazy Loading**: Triggers lazy-loaded content
- ✅ **Customizable**: Easy to configure for specific needs
- ✅ **Async**: Built on asyncio for efficient scraping

## Quick Start

### Basic Usage

```python
import asyncio
from scraper import scrape_url

async def main():
    result = await scrape_url("https://example.com")
    
    if result['success']:
        print(result['content'])
        print(f"Length: {result['content_length']} chars")
    else:
        print(f"Error: {result['error']}")

asyncio.run(main())
```

### Using the WebScraper Class

```python
from scraper import WebScraper

async def main():
    scraper = WebScraper(headless=True, timeout=30)
    result = await scraper.scrape("https://example.com")
    print(result['content'])

asyncio.run(main())
```

### Custom Configuration

```python
from scraper import WebScraper

async def main():
    scraper = WebScraper(headless=True)
    
    # Create custom config

asyncio.run(main())
```

## API

### WebScraper(headless=True, timeout=30)
- `headless`: Run browser in headless mode
- `timeout`: Page timeout in seconds

### scrape(url, custom_config=None, use_hooks=True)
- `url`: URL to scrape
- `custom_config`: Optional CrawlerRunConfig
- `use_hooks`: Enable cookie/popup handling

Returns dict with: `success`, `url`, `content`, `content_length`, `word_count`, `duration`, `timestamp`, `pdf_count`, `pdf_metadata`

## Dependencies

- crawl4ai
- playwright
- httpx
- pdfplumber

## Testing

Run the test suite:

```bash
cd backend/app/scraping
python test_scraper.py
```

## Tips

1. **For static sites**: Use shorter delays (1-2s)
2. **For dynamic sites**: Use longer delays (3-5s) and "networkidle"
3. **For specific content**: Use `css_selector` to target elements
4. **For debugging**: Set `headless=False` to see the browser

## Examples

See `test_scraper.py` for complete examples including:
- Basic scraping
- Custom configuration
- CSS selector extraction
- Multiple URL scraping
