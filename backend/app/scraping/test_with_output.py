#!/usr/bin/env python3
"""
Test scraper and save detailed results to files for observation.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from scraper import WebScraper, scrape_url


async def test_and_save_results():
    """Test scraping and save detailed results to JSON and TXT files."""
    
    print("🧪 TESTING WEB SCRAPER WITH FILE OUTPUT")
    print("=" * 60)
    
    test_urls = [
        "https://erstecampus.at/kantine-am-campus/",
        "https://www.enjoyhenry.com/menuplan-bdo/",
        "https://www.eurest.at/icon-menueplan/",
    ]
    
    scraper = WebScraper(headless=True)
    all_results = []
    
    # Scrape all URLs
    for i, url in enumerate(test_urls, 1):
        print(f"\n[{i}/{len(test_urls)}] Scraping: {url}")
        result = await scraper.scrape(url)
        
        if result['success']:
            print(f"✅ Success! {result['content_length']:,} chars in {result['duration']:.2f}s")
        else:
            print(f"❌ Failed: {result.get('error', 'Unknown error')}")
        
        all_results.append(result)
    
    # Create output directory
    output_dir = Path("scraping_results")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save JSON file with all metadata
    json_file = output_dir / f"results_{timestamp}.json"
    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    print(f"\n💾 Saved JSON results to: {json_file}")
    
    # Save detailed TXT file with readable format
    txt_file = output_dir / f"results_{timestamp}.txt"
    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("WEB SCRAPING TEST RESULTS\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("=" * 80 + "\n\n")
        
        for i, result in enumerate(all_results, 1):
            f.write(f"\n{'=' * 80}\n")
            f.write(f"RESULT #{i}\n")
            f.write(f"{'=' * 80}\n\n")
            
            f.write(f"URL: {result['url']}\n")
            f.write(f"Success: {result['success']}\n")
            f.write(f"Timestamp: {result['timestamp']}\n")
            
            if result['success']:
                f.write(f"Duration: {result['duration']:.2f}s\n")
                f.write(f"Status Code: {result.get('status_code', 'N/A')}\n")
                f.write(f"Content Length: {result['content_length']:,} characters\n")
                f.write(f"Word Count: {result['word_count']:,} words\n")
                f.write(f"\n{'-' * 80}\n")
                f.write("CONTENT:\n")
                f.write(f"{'-' * 80}\n\n")
                f.write(result['content'])
                f.write("\n\n")
            else:
                f.write(f"Error: {result.get('error', 'Unknown error')}\n\n")
    
    print(f"💾 Saved detailed TXT results to: {txt_file}")
    
    # Save individual content files for each URL
    for i, result in enumerate(all_results, 1):
        if result['success']:
            # Create safe filename from URL
            safe_name = result['url'].replace('https://', '').replace('http://', '')
            safe_name = safe_name.replace('/', '_').replace(':', '_')[:50]
            
            content_file = output_dir / f"content_{i}_{safe_name}_{timestamp}.md"
            with open(content_file, 'w', encoding='utf-8') as f:
                f.write(f"# Scraped Content\n\n")
                f.write(f"**URL:** {result['url']}\n\n")
                f.write(f"**Scraped:** {result['timestamp']}\n\n")
                f.write(f"**Duration:** {result['duration']:.2f}s\n\n")
                f.write(f"**Content Length:** {result['content_length']:,} chars\n\n")
                f.write(f"---\n\n")
                f.write(result['content'])
            
            print(f"💾 Saved individual content to: {content_file}")
    
    print(f"\n{'=' * 60}")
    print(f"✅ ALL RESULTS SAVED TO: {output_dir.absolute()}")
    print(f"{'=' * 60}")
    
    # Print summary
    print(f"\n📊 SUMMARY:")
    print(f"   Total URLs tested: {len(all_results)}")
    print(f"   Successful: {sum(1 for r in all_results if r['success'])}")
    print(f"   Failed: {sum(1 for r in all_results if not r['success'])}")
    print(f"   Total content: {sum(r.get('content_length', 0) for r in all_results):,} chars")


async def test_custom_config_with_output():
    """Test with custom configuration and save results."""
    
    print("\n\n🧪 TESTING CUSTOM CONFIGURATION")
    print("=" * 60)
    
    scraper = WebScraper(headless=True)
    
    # Test with CSS selector
    config = scraper.create_custom_config(
        css_selector="main, article, .content",
        wait_until="domcontentloaded",
        delay=2.0
    )
    
    url = "https://erstecampus.at/kantine-am-campus/"
    print(f"\n📍 Scraping with CSS selector: {url}")
    
    result = await scraper.scrape(url, custom_config=config)
    
    # Save custom config results
    output_dir = Path("scraping_results")
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    custom_file = output_dir / f"custom_config_{timestamp}.txt"
    with open(custom_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("CUSTOM CONFIGURATION TEST\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"URL: {url}\n")
        f.write(f"Configuration: CSS Selector extraction\n")
        f.write(f"Selector: main, article, .content\n")
        f.write(f"Wait: domcontentloaded\n")
        f.write(f"Delay: 2.0s\n\n")
        
        if result['success']:
            f.write(f"✅ Success!\n")
            f.write(f"Duration: {result['duration']:.2f}s\n")
            f.write(f"Content Length: {result['content_length']:,} chars\n\n")
            f.write("-" * 80 + "\n")
            f.write("EXTRACTED CONTENT:\n")
            f.write("-" * 80 + "\n\n")
            f.write(result['content'])
        else:
            f.write(f"❌ Failed: {result.get('error')}\n")
    
    print(f"💾 Saved custom config results to: {custom_file}")
    
    if result['success']:
        print(f"✅ Success! Extracted {result['content_length']:,} chars")


async def main():
    """Run all tests with file output."""
    await test_and_save_results()
    await test_custom_config_with_output()
    
    print("\n" + "=" * 60)
    print("✅ ALL TESTS COMPLETED")
    print("Check the 'scraping_results' folder for detailed output files")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
