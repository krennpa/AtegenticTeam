#!/usr/bin/env python3
"""
Production-ready web scraper supporting HTML pages, iframes, and embedded PDFs.
Handles cookie consent, popups, and dynamic content automatically.

Supported PDF Types:
- Direct PDF URLs (*.pdf)
- Content-type based PDFs (URLs returning application/pdf)
- Embedded PDFs in HTML pages
- PDFs in iframes and embed tags
- Downloadable PDFs

Features:
- Automatic content-type detection
- Network request monitoring
- Comprehensive DOM scanning
- Retry logic with exponential backoff
- Robust error handling
- Production-grade logging
"""

import asyncio
import time
import tempfile
import os
import sys
import httpx
import re
import logging
from typing import Dict, Any, Optional, List, Set, Callable, Awaitable
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode
from crawl4ai.processors.pdf import PDFCrawlerStrategy, PDFContentScrapingStrategy

# Configure logging
logger = logging.getLogger(__name__)


class WebScraper:
    """Generic web scraper using crawl4ai for any website."""
    
    def __init__(self, headless: bool = True, timeout: int = 30, max_retries: int = 3):
        """Initialize web scraper.
        
        Args:
            headless: Run browser in headless mode
            timeout: Page timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.timeout = timeout * 1000
        self.max_retries = max_retries
        self.browser_config = BrowserConfig(
            headless=headless,
            verbose=False,
            browser_type="chromium",
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        
        self.default_run_config = CrawlerRunConfig(
            cache_mode=CacheMode.BYPASS,
            wait_until="networkidle",
            page_timeout=self.timeout,
            delay_before_return_html=20.0,  # Increased to 20 seconds for iframe-heavy pages
            remove_overlay_elements=True,
            simulate_user=True,
            scan_full_page=True,
            process_iframes=True,
            excluded_tags=["script", "style", "noscript"],
            excluded_selector=".cookie-banner, .gdpr-notice, [class*='cookie'], [class*='popup'], [data-elementor-type='popup']",
            verbose=True  # Enable verbose mode to see what's happening
        )
        
        self._found_pdf_urls = []
        self._pdf_network_requests = []
        self._iframe_urls = []
    
    async def _before_retrieve_html_hook(self, page, context=None, **kwargs):
        """Hook that runs RIGHT BEFORE HTML extraction - handles multiple popups."""
        # Store PDF URLs found in the page for later extraction
        self._found_pdf_urls = []
        self._pdf_network_requests = []
        self._captured_html = None  # Store captured HTML for dynamic content
        
        try:
            print("🔧 Running before_retrieve_html hook...")
            
            # STEP 0: Wait for any delayed popups (like Elementor with page_load_delay)
            print("   Step 0: Waiting for delayed popups to appear...")
            await asyncio.sleep(3)  # Wait for popups with delays to show up
            
            # STEP 1: Handle cookie consent popup
            print("   Step 1: Looking for cookie consent...")
            cookie_selectors = [
                'button:has-text("Alle akzeptieren")',
                'button:has-text("Accept all")',
                'a:has-text("Alle akzeptieren")',
                '.cky-btn-accept',
                '[class*="accept-all"]',
                'button[class*="cookie"][class*="accept"]',
            ]
            
            clicked_cookie = False
            for selector in cookie_selectors:
                try:
                    button = page.locator(selector).first
                    if await button.is_visible(timeout=500):
                        await button.click(timeout=1000)
                        print(f"   ✓ Clicked cookie button: {selector}")
                        clicked_cookie = True
                        await asyncio.sleep(2)
                        break
                except:
                    continue
            
            if not clicked_cookie:
                print("   ⚠️ No cookie consent button found")
            
            # STEP 2: Look for and close ANY other popups/modals/overlays
            print("   Step 2: Looking for additional popups...")
            
            # Common close button patterns
            close_selectors = [
                'button:has-text("×")',
                'button:has-text("Close")',
                'button:has-text("Schließen")',
                '[aria-label="Close"]',
                '[aria-label="Schließen"]',
                '.modal-close',
                '.popup-close',
                '.close-button',
                '[class*="close"]',
                '[id*="close"]',
                'button[class*="dismiss"]',
            ]
            
            closed_popups = 0
            for selector in close_selectors:
                try:
                    buttons = await page.locator(selector).all()
                    for button in buttons:
                        if await button.is_visible(timeout=300):
                            await button.click(timeout=1000)
                            print(f"   ✓ Closed popup: {selector}")
                            closed_popups += 1
                            await asyncio.sleep(1)
                except:
                    continue
            
            if closed_popups > 0:
                print(f"   ✓ Closed {closed_popups} additional popup(s)")
            else:
                print("   ℹ️ No additional popups found")
            
            # STEP 3: Press ESC key to close any remaining modals
            print("   Step 3: Pressing ESC to close any remaining modals...")
            try:
                await page.keyboard.press('Escape')
                await asyncio.sleep(0.5)
                await page.keyboard.press('Escape')
                await asyncio.sleep(0.5)
                print("   ✓ Pressed ESC twice")
            except:
                pass
            
            # STEP 4: Remove all popup/modal/overlay elements from DOM
            print("   Step 4: Cleaning up DOM...")
            try:
                removed = await page.evaluate("""
                    () => {
                        let count = 0;
                        
                        // Selectors for popups, modals, overlays (including Elementor)
                        const selectors = [
                            '[data-elementor-type="popup"]',  // Elementor popups
                            '.elementor-popup-modal',
                            '[class*="cookie"]',
                            '[id*="cookie"]',
                            '[class*="modal"]',
                            '[id*="modal"]',
                            '[class*="popup"]',
                            '[id*="popup"]',
                            '[class*="overlay"]',
                            '[id*="overlay"]',
                            '[class*="gdpr"]',
                            '[class*="consent"]',
                            '.cky-consent-container',
                            '#cookie-law-info-bar',
                            '[role="dialog"]',
                            '[aria-modal="true"]'
                        ];
                        
                        selectors.forEach(sel => {
                            document.querySelectorAll(sel).forEach(el => {
                                const style = window.getComputedStyle(el);
                                // Remove if it's positioned as overlay or has high z-index
                                if (style.position === 'fixed' || 
                                    style.position === 'absolute' ||
                                    parseInt(style.zIndex) > 100) {
                                    el.remove();
                                    count++;
                                }
                            });
                        });
                        
                        // Also remove backdrop/overlay elements
                        document.querySelectorAll('[class*="backdrop"], [class*="overlay"], .dialog-lightbox-close-button').forEach(el => {
                            el.remove();
                            count++;
                        });
                        
                        return count;
                    }
                """)
                print(f"   ✓ Removed {removed} overlay elements from DOM")
            except Exception as e:
                print(f"   ✗ DOM cleanup failed: {e}")
            
            # STEP 5: Check for iframes and wait for them to load - EXTENDED WAIT
            print("   Step 5: Checking for iframes and dynamic content...")
            try:
                # First, let's see what's actually in the page
                page_content = await page.content()
                print(f"   📄 Raw page HTML length: {len(page_content)} chars")
                
                # Check if page has any meaningful content
                body_text = await page.evaluate('() => document.body ? document.body.innerText.length : 0')
                print(f"   📄 Body text length: {body_text} chars")
                
                # Special handling for The Eventery platform (erstecampus.at)
                if 'eventery' in page.url.lower() or 'erstecampus' in page.url.lower():
                    print("   🎯 Detected Eventery platform - using specialized wait strategy")
                    # Wait for menu content to load - Eventery uses dynamic widgets
                    try:
                        # Wait for KANTINE logo/containers to appear (visible in the menu)
                        print("   ⏳ Waiting for KANTINE menu containers to load...")
                        
                        # Try to wait for images with KANTINE logo or menu item containers
                        kantine_selectors = [
                            'img[alt*="KANTINE"]',
                            'img[alt*="Kantine"]',
                            'img[src*="kantine"]',
                            'div:has-text("HAUPTSPEISE")',  # Main dishes section
                            'div:has-text("€")',  # Price indicators
                            'div:has-text("Knuspriges")',  # Specific menu item
                        ]
                        
                        found_content = False
                        for selector in kantine_selectors:
                            try:
                                await page.wait_for_selector(selector, timeout=15000, state='visible')
                                print(f"   ✓ Found KANTINE content with selector: {selector}")
                                found_content = True
                                break
                            except:
                                continue
                        
                        if not found_content:
                            print("   ⚠️ No KANTINE selectors found, trying generic wait...")
                            # Fallback: just wait longer
                            await asyncio.sleep(10)
                        else:
                            # Additional wait for all menu items to fully load
                            print("   ⏳ Waiting for all menu items to load...")
                            await asyncio.sleep(10)
                        
                        # Scroll to trigger any lazy-loaded content
                        try:
                            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                            await asyncio.sleep(2)
                            await page.evaluate('window.scrollTo(0, 0)')
                            await asyncio.sleep(2)
                        except:
                            pass
                        
                        # Check body text again after waiting
                        body_text_after = await page.evaluate('() => document.body ? document.body.innerText.length : 0')
                        print(f"   📄 Body text after wait: {body_text_after} chars (was {body_text} chars)")
                        
                        # Get a sample of the content to verify
                        sample_text = await page.evaluate('() => document.body ? document.body.innerText.substring(0, 200) : ""')
                        print(f"   📄 Content sample: {sample_text[:100]}...")
                        
                        # CRITICAL: Capture the full HTML now before crawl4ai strips it
                        print("   💾 Capturing full page HTML for Eventery content...")
                        self._captured_html = await page.content()
                        print(f"   ✓ Captured {len(self._captured_html)} chars of HTML")
                    except Exception as e:
                        print(f"   ⚠️ Eventery-specific wait failed: {e}")
                
                # Wait longer for dynamic iframes to appear
                await asyncio.sleep(5)
                
                iframe_count = await page.locator('iframe').count()
                if iframe_count > 0:
                    print(f"   ✓ Found {iframe_count} iframe(s)")
                    
                    # Store iframe URLs for later extraction
                    self._iframe_urls = []
                    
                    # Try to get iframe content and URLs
                    for i in range(iframe_count):
                        try:
                            iframe = page.locator('iframe').nth(i)
                            src = await iframe.get_attribute('src')
                            if src and not src.startswith('about:') and not src.startswith('blob:'):
                                print(f"   ✓ Iframe {i+1}: {src}")
                                # Make absolute URL if relative
                                if not src.startswith('http'):
                                    from urllib.parse import urljoin
                                    src = urljoin(page.url, src)
                                self._iframe_urls.append(src)
                        except Exception as e:
                            print(f"   ⚠️ Failed to get iframe {i+1}: {e}")
                    
                    # Wait additional time for iframe content to load
                    await asyncio.sleep(5)
                else:
                    print("   ℹ️ No iframes found initially, waiting and rechecking...")
                    # Wait and check again - some iframes load very late
                    await asyncio.sleep(5)
                    iframe_count = await page.locator('iframe').count()
                    if iframe_count > 0:
                        print(f"   ✓ Found {iframe_count} iframe(s) after waiting")
                        self._iframe_urls = []
                        for i in range(iframe_count):
                            try:
                                iframe = page.locator('iframe').nth(i)
                                src = await iframe.get_attribute('src')
                                if src and not src.startswith('about:') and not src.startswith('blob:'):
                                    print(f"   ✓ Iframe {i+1}: {src}")
                                    if not src.startswith('http'):
                                        from urllib.parse import urljoin
                                        src = urljoin(page.url, src)
                                    self._iframe_urls.append(src)
                            except Exception as e:
                                print(f"   ⚠️ Failed to get iframe {i+1}: {e}")
                    else:
                        print("   ℹ️ Still no iframes found")
            except Exception as e:
                print(f"   ✗ Iframe check failed: {e}")
            
            # STEP 5.5: Enhanced PDF detection with network monitoring
            print("   Step 5.5: Enhanced PDF detection...")
            try:
                # Set up comprehensive network monitoring
                def capture_all_requests(request):
                    url = request.url.lower()
                    # Capture PDF requests and responses
                    if '.pdf' in url or 'pdf' in url:
                        self._pdf_network_requests.append(request.url)
                        print(f"   📄 Network PDF request: {request.url}")
                
                def capture_responses(response):
                    # Check content-type for PDFs
                    try:
                        content_type = response.headers.get('content-type', '').lower()
                        if 'application/pdf' in content_type:
                            self._pdf_network_requests.append(response.url)
                            print(f"   📄 PDF response detected: {response.url}")
                    except:
                        pass
                
                page.on('request', capture_all_requests)
                page.on('response', capture_responses)
                
                # Wait for dynamic content and network requests - LONGER WAIT
                print("   ⏳ Waiting for dynamic PDF content to load...")
                await asyncio.sleep(10)  # Increased from 5 to 10 seconds
                
                # Try to trigger any lazy-loaded content by scrolling
                try:
                    await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                    await asyncio.sleep(2)
                    await page.evaluate('window.scrollTo(0, 0)')
                    await asyncio.sleep(2)
                except:
                    pass
                
                # Comprehensive PDF URL extraction from DOM
                pdf_urls_found = await page.evaluate("""
                    () => {
                        const urls = new Set();
                        
                        // 1. Check all <a> links
                        document.querySelectorAll('a[href]').forEach(a => {
                            if (a.href && a.href.toLowerCase().includes('.pdf')) {
                                urls.add(a.href);
                            }
                        });
                        
                        // 2. Check embed/object/iframe elements
                        document.querySelectorAll('embed, object, iframe').forEach(el => {
                            const src = el.src || el.data || el.getAttribute('src') || el.getAttribute('data');
                            if (src && !src.includes('about:blank') && !src.startsWith('blob:')) {
                                if (src.toLowerCase().includes('.pdf')) {
                                    const absolute = src.startsWith('http') ? src : new URL(src, window.location.href).href;
                                    urls.add(absolute);
                                }
                            }
                        });
                        
                        // 3. Search all script tags for PDF URLs (including inline JS)
                        document.querySelectorAll('script').forEach(script => {
                            const content = script.textContent || script.innerHTML;
                            // Match various PDF URL patterns
                            const patterns = [
                                /https?:\\/\\/[^\\s"'<>]+\\.pdf/gi,
                                /["']([^"']*\\.pdf[^"']*)["']/gi,
                                /url[:\\s]*["']([^"']*\\.pdf[^"']*)["']/gi
                            ];
                            patterns.forEach(regex => {
                                const matches = content.match(regex);
                                if (matches) {
                                    matches.forEach(match => {
                                        // Clean up the match
                                        let url = match.replace(/["']/g, '').replace(/^url:/i, '').trim();
                                        if (url.startsWith('http')) {
                                            urls.add(url);
                                        }
                                    });
                                }
                            });
                        });
                        
                        // 4. Check all data-* attributes
                        document.querySelectorAll('[data-src], [data-url], [data-pdf], [data-file], [data-href]').forEach(el => {
                            ['data-src', 'data-url', 'data-pdf', 'data-file', 'data-href'].forEach(attr => {
                                const val = el.getAttribute(attr);
                                if (val && val.toLowerCase().includes('.pdf')) {
                                    const absolute = val.startsWith('http') ? val : new URL(val, window.location.href).href;
                                    urls.add(absolute);
                                }
                            });
                        });
                        
                        // 5. Check window/global variables for PDF URLs
                        try {
                            const pageSource = document.documentElement.outerHTML;
                            const regex = /https?:\\/\\/[^\\s"'<>]+\\.pdf/gi;
                            const matches = pageSource.match(regex);
                            if (matches) {
                                matches.forEach(url => urls.add(url));
                            }
                        } catch (e) {}
                        
                        return Array.from(urls).filter(url => url && url.startsWith('http'));
                    }
                """)
                
                # Collect all unique PDF URLs
                if self._pdf_network_requests:
                    print(f"   ✓ Captured {len(self._pdf_network_requests)} PDF(s) from network")
                    for url in self._pdf_network_requests:
                        self._found_pdf_urls.append(url)
                
                if pdf_urls_found and len(pdf_urls_found) > 0:
                    print(f"   ✓ Found {len(pdf_urls_found)} PDF URL(s) in DOM")
                    for url in pdf_urls_found:
                        print(f"   📄 PDF URL: {url}")
                        self._found_pdf_urls.append(url)
                
                if not self._pdf_network_requests and not pdf_urls_found:
                    print("   ℹ️ No PDF URLs found")
                
                # Try multiple times to find PDFs (they might load slowly)
                pdf_info = None
                for attempt in range(3):
                    pdf_info = await page.evaluate("""
                        () => {
                            const pdfs = {
                                links: [],
                                embeds: [],
                                iframes: []
                            };
                            
                            // Check <a> tags
                            document.querySelectorAll('a[href]').forEach(a => {
                                if (a.href && (a.href.toLowerCase().includes('.pdf') || a.href.toLowerCase().includes('pdf'))) {
                                    pdfs.links.push({
                                        href: a.href,
                                        text: a.textContent.trim()
                                    });
                                }
                            });
                            
                            // Check <embed> and <object> tags (more thorough)
                            document.querySelectorAll('embed, object').forEach(el => {
                                let src = el.src || el.data || el.getAttribute('src') || el.getAttribute('data');
                                
                                // Skip invalid sources
                                if (!src || src === 'about:blank' || src.startsWith('blob:')) {
                                    return;
                                }
                                
                                // Check if it's a PDF by extension or type
                                const isPdf = src.toLowerCase().includes('.pdf') || 
                                              el.type === 'application/pdf' ||
                                              el.getAttribute('type') === 'application/pdf';
                                
                                if (isPdf) {
                                    // Make absolute URL
                                    try {
                                        const absoluteUrl = src.startsWith('http') ? src : new URL(src, window.location.href).href;
                                        if (absoluteUrl && absoluteUrl !== 'about:blank') {
                                            pdfs.embeds.push(absoluteUrl);
                                        }
                                    } catch (e) {
                                        console.log('Failed to parse URL:', src);
                                    }
                                }
                            });
                            
                            // Check iframes for PDF
                            document.querySelectorAll('iframe').forEach(iframe => {
                                const src = iframe.src || iframe.getAttribute('src');
                                if (src && src !== 'about:blank' && !src.startsWith('blob:') && src.toLowerCase().includes('.pdf')) {
                                    // Make absolute URL
                                    const absoluteUrl = src.startsWith('http') ? src : new URL(src, window.location.href).href;
                                    pdfs.iframes.push(absoluteUrl);
                                }
                            });
                            
                            return pdfs;
                        }
                    """)
                    
                    total_found = len(pdf_info['links']) + len(pdf_info['embeds']) + len(pdf_info['iframes'])
                    if total_found > 0:
                        print(f"   ✓ Found PDFs on attempt {attempt + 1}")
                        break
                    
                    if attempt < 2:
                        print(f"   ⏳ No PDFs yet, waiting... (attempt {attempt + 1}/3)")
                        await asyncio.sleep(3)
                
                
                total_pdfs = len(pdf_info['links']) + len(pdf_info['embeds']) + len(pdf_info['iframes'])
                
                if total_pdfs > 0:
                    print(f"   ✓ Found {total_pdfs} PDF(s)")
                    
                    # Store all PDF URLs for later extraction (filter out invalid ones)
                    for link in pdf_info['links']:
                        url = link['href']
                        if url and url != 'about:blank' and not url.startswith('blob:'):
                            self._found_pdf_urls.append(url)
                            print(f"   ✓ PDF link: {link['text'][:50]} - {url}")
                    
                    for embed in pdf_info['embeds']:
                        if embed and embed != 'about:blank' and not embed.startswith('blob:'):
                            self._found_pdf_urls.append(embed)
                            print(f"   ✓ Embedded PDF: {embed}")
                    
                    for iframe in pdf_info['iframes']:
                        if iframe and iframe != 'about:blank' and not iframe.startswith('blob:'):
                            self._found_pdf_urls.append(iframe)
                            print(f"   ✓ Iframe PDF: {iframe}")
                else:
                    print("   ℹ️ No PDF links found")
                    
                return page
                
            except Exception as e:
                print(f"   ✗ PDF check failed: {e}")
                return page
            
            # STEP 6: Scroll to trigger lazy content
            print("   Step 6: Scrolling to load content...")
            try:
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight / 2)')
                await asyncio.sleep(0.5)
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                await asyncio.sleep(0.5)
                await page.evaluate('window.scrollTo(0, 0)')  # Back to top
                await asyncio.sleep(0.3)
                print("   ✓ Scrolling complete")
            except:
                pass
            
            print("   ✅ Hook complete!\n")
            return page
            
        except Exception as e:
            print(f"   ❌ Hook error: {e}")
            return page
    
    
    async def _extract_pdf_content(self, pdf_url: str, retry_count: int = 0) -> Dict[str, Any]:
        """Extract PDF content using crawl4ai's recommended PDF strategies with retry logic.
        
        Uses PDFCrawlerStrategy + PDFContentScrapingStrategy as per crawl4ai docs.
        This is the most elegant and integrated approach.
        
        Args:
            pdf_url: URL of the PDF to extract
            retry_count: Current retry attempt number
            
        Returns:
            Dict with success status, extracted text, and metadata
        """
        print(f"   🔄 Processing PDF: {pdf_url}")
        logger.info(f"Extracting PDF content from: {pdf_url} (attempt {retry_count + 1}/{self.max_retries})")
        
        try:
            # Validate URL
            if not pdf_url or not pdf_url.startswith('http'):
                logger.error(f"Invalid PDF URL: {pdf_url}")
                return {'success': False, 'text': '', 'metadata': {}, 'error': 'Invalid URL'}
            
            # Use crawl4ai's recommended PDF processing pattern
            pdf_crawler_strategy = PDFCrawlerStrategy()
            pdf_scraping_strategy = PDFContentScrapingStrategy(
                extract_images=False,  # Don't extract images for menu PDFs
                batch_size=5  # Process 5 pages at a time
            )
            run_config = CrawlerRunConfig(scraping_strategy=pdf_scraping_strategy)
            
            async with AsyncWebCrawler(crawler_strategy=pdf_crawler_strategy) as crawler:
                result = await crawler.arun(url=pdf_url, config=run_config)
                
                if result.success:
                    # Extract text content from markdown
                    text_content = ""
                    if result.markdown and hasattr(result.markdown, 'raw_markdown'):
                        text_content = result.markdown.raw_markdown
                    elif hasattr(result, 'markdown_v2') and result.markdown_v2:
                        text_content = result.markdown_v2.raw_markdown if hasattr(result.markdown_v2, 'raw_markdown') else str(result.markdown_v2)
                    
                    if text_content:
                        print(f"   ✅ Extracted {len(text_content)} chars from PDF")
                        logger.info(f"Successfully extracted {len(text_content)} chars from PDF: {pdf_url}")
                        return {
                            'success': True,
                            'text': text_content,
                            'metadata': result.metadata or {}
                        }
                    else:
                        print("   ⚠️ PDF processed but no text content found")
                        logger.warning(f"PDF processed but no text extracted: {pdf_url}")
                        return {'success': False, 'text': '', 'metadata': result.metadata or {}, 'error': 'No text content'}
                else:
                    error_msg = result.error_message if hasattr(result, 'error_message') else 'Unknown error'
                    print(f"   ❌ PDF processing failed: {error_msg}")
                    logger.error(f"PDF processing failed for {pdf_url}: {error_msg}")
                    
                    # Retry logic
                    if retry_count < self.max_retries - 1:
                        wait_time = 2 ** retry_count  # Exponential backoff
                        print(f"   🔄 Retrying in {wait_time}s...")
                        await asyncio.sleep(wait_time)
                        return await self._extract_pdf_content(pdf_url, retry_count + 1)
                    
                    return {'success': False, 'text': '', 'metadata': {}, 'error': error_msg}
                    
        except asyncio.TimeoutError:
            logger.error(f"Timeout extracting PDF: {pdf_url}")
            if retry_count < self.max_retries - 1:
                wait_time = 2 ** retry_count
                print(f"   ⏱️ Timeout, retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                return await self._extract_pdf_content(pdf_url, retry_count + 1)
            return {'success': False, 'text': '', 'metadata': {}, 'error': 'Timeout'}
        except Exception as e:
            logger.exception(f"Exception extracting PDF {pdf_url}: {e}")
            print(f"   ❌ PDF extraction error: {e}")
            
            # Retry on certain errors
            if retry_count < self.max_retries - 1 and not isinstance(e, (ValueError, TypeError)):
                wait_time = 2 ** retry_count
                print(f"   🔄 Retrying in {wait_time}s...")
                await asyncio.sleep(wait_time)
                return await self._extract_pdf_content(pdf_url, retry_count + 1)
            
            return {'success': False, 'text': '', 'metadata': {}, 'error': str(e)}
    
    async def scrape(self, url: str, custom_config: Optional[CrawlerRunConfig] = None, use_hooks: bool = True) -> Dict[str, Any]:
        """Scrape content from URL (HTML, iframes, embedded PDFs).
        
        Args:
            url: URL to scrape
            custom_config: Optional custom configuration
            use_hooks: Enable cookie consent & popup handling
            
        Returns:
            Dict with content, metadata, and PDF info
        """
        # STRATEGY 1: Check if URL returns PDF content-type (handles downloadable PDFs)
        try:
            logger.info(f"Checking content-type for URL: {url}")
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                # Use GET with stream to check content-type without downloading everything
                async with client.stream('GET', url, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,application/pdf,*/*;q=0.8'
                }) as response:
                    content_type = response.headers.get('content-type', '').lower()
                    
                    if 'application/pdf' in content_type:
                        print(f"🔍 Detected PDF content-type for: {url}")
                        logger.info(f"URL returns PDF content-type: {url}")
                        # Close the stream, we'll download it properly with PDF extractor
                        start_time = time.time()
                        pdf_result = await self._extract_pdf_content(url)
                        duration = time.time() - start_time
                        
                        result = {
                            'success': pdf_result['success'],
                            'url': url,
                            'content': pdf_result.get('text', ''),
                            'content_length': len(pdf_result.get('text', '')),
                            'word_count': len(pdf_result.get('text', '').split()) if pdf_result.get('text') else 0,
                            'duration': duration,
                            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                            'pdf_count': 1 if pdf_result['success'] else 0,
                            'pdf_urls': [url] if pdf_result['success'] else [],
                            'pdf_metadata': [pdf_result.get('metadata', {})] if pdf_result['success'] else [],
                            'scrape_type': 'pdf_content_type'
                        }
                        
                        if not pdf_result['success'] and 'error' in pdf_result:
                            result['error'] = pdf_result['error']
                        
                        return result
        except httpx.TimeoutException:
            logger.warning(f"Timeout checking content-type for {url}, continuing with normal scrape")
            print(f"⚠️ Content-type check timeout, continuing with normal scrape")
        except Exception as e:
            logger.warning(f"Content-type check failed for {url}: {e}, continuing with normal scrape")
            print(f"⚠️ Content-type check failed, continuing with normal scrape: {e}")
        
        # STRATEGY 2: Handle direct PDF URLs by extension
        if url.lower().endswith('.pdf'):
            print(f"🔍 Detected PDF extension in URL: {url}")
            logger.info(f"URL has .pdf extension: {url}")
            start_time = time.time()
            pdf_result = await self._extract_pdf_content(url)
            duration = time.time() - start_time
            
            result = {
                'success': pdf_result['success'],
                'url': url,
                'content': pdf_result.get('text', ''),
                'content_length': len(pdf_result.get('text', '')),
                'word_count': len(pdf_result.get('text', '').split()) if pdf_result.get('text') else 0,
                'duration': duration,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                'pdf_count': 1 if pdf_result['success'] else 0,
                'pdf_urls': [url] if pdf_result['success'] else [],
                'pdf_metadata': [pdf_result.get('metadata', {})] if pdf_result['success'] else [],
                'scrape_type': 'pdf_extension'
            }
            
            if not pdf_result['success'] and 'error' in pdf_result:
                result['error'] = pdf_result['error']
            
            return result
        
        config = custom_config or self.default_run_config
        
        try:
            async with AsyncWebCrawler(config=self.browser_config) as crawler:
                start_time = time.time()
                
                # Set up hooks using the crawler strategy
                if use_hooks:
                    crawler.crawler_strategy.set_hook('before_retrieve_html', self._before_retrieve_html_hook)
                
                result = await crawler.arun(url=url, config=config)
                duration = time.time() - start_time
                
                # Extract text from HTML - simple and direct
                from bs4 import BeautifulSoup
                text_content = ""
                
                # PRIORITY: Use captured HTML from hook if available (for dynamic content like Eventery)
                if hasattr(self, '_captured_html') and self._captured_html:
                    html_source = self._captured_html
                    print(f"\n📊 Using captured HTML from hook: {len(html_source)} chars")
                else:
                    # Get HTML from result (try cleaned_html first, then html)
                    html_source = getattr(result, 'cleaned_html', None) or getattr(result, 'html', None)
                    print(f"\n📊 Using crawl4ai HTML: {len(html_source) if html_source else 0} chars")
                
                print(f"📊 Result success: {result.success}")
                if hasattr(result, 'markdown'):
                    print(f"📊 Markdown length: {len(result.markdown) if result.markdown else 0} chars")
                
                if html_source:
                    soup = BeautifulSoup(html_source, 'html.parser')
                    # Remove non-content elements
                    for tag in soup(['script', 'style', 'noscript']):
                        tag.decompose()
                    # Extract text
                    text_content = soup.get_text(separator='\n', strip=True)
                    # Basic cleanup
                    lines = [line.strip() for line in text_content.split('\n') if line.strip()]
                    text_content = '\n'.join(lines)
                    print(f"✓ Extracted {len(text_content)} chars, {len(text_content.split())} words")
                else:
                    print("⚠ No HTML available")
                
                # Extract iframe content if any were found
                iframe_contents = []
                if hasattr(self, '_iframe_urls') and self._iframe_urls:
                    print(f"\n🔍 Extracting content from {len(self._iframe_urls)} iframe(s)...")
                    for idx, iframe_url in enumerate(self._iframe_urls, 1):
                        try:
                            print(f"   📄 Scraping iframe {idx}: {iframe_url}")
                            # Recursively scrape iframe content (without hooks to avoid infinite loops)
                            iframe_result = await self.scrape(iframe_url, use_hooks=False)
                            if iframe_result['success'] and iframe_result.get('content'):
                                iframe_text = iframe_result['content']
                                if len(iframe_text) > 100:  # Only include if substantial content
                                    iframe_contents.append(f"\n\n=== IFRAME CONTENT {idx}: {iframe_url} ===\n\n{iframe_text}")
                                    print(f"   ✓ Extracted {len(iframe_text)} chars from iframe {idx}")
                                else:
                                    print(f"   ⚠️ Iframe {idx} content too short ({len(iframe_text)} chars)")
                            else:
                                print(f"   ⚠️ Failed to extract iframe {idx}: {iframe_result.get('error', 'Unknown error')}")
                        except Exception as e:
                            print(f"   ❌ Error scraping iframe {idx}: {e}")
                            logger.exception(f"Error scraping iframe {iframe_url}: {e}")
                
                # Extract PDF content using hybrid approach
                pdf_content = []
                pdf_metadata = []
                pdf_urls: Set[str] = set()
                
                # Collect all unique PDF URLs from network and DOM
                if hasattr(self, '_found_pdf_urls') and self._found_pdf_urls:
                    # Deduplicate and filter valid URLs
                    for pdf_url in self._found_pdf_urls:
                        if pdf_url and pdf_url.startswith('http') and pdf_url not in pdf_urls:
                            pdf_urls.add(pdf_url)
                    
                    print(f"\n📄 Total unique PDF URLs to process: {len(pdf_urls)}")
                
                # STRATEGY 3: Process embedded PDFs found in page (limit to 5 PDFs to avoid timeout)
                for idx, pdf_url in enumerate(list(pdf_urls)[:5], 1):
                    print(f"\n📄 Processing embedded PDF {idx}/{min(len(pdf_urls), 5)}: {pdf_url}")
                    logger.info(f"Processing embedded PDF {idx}: {pdf_url}")
                    try:
                        pdf_result = await self._extract_pdf_content(pdf_url)
                        if pdf_result['success'] and pdf_result['text']:
                            pdf_content.append(f"\n\n=== PDF {idx}: {pdf_url} ===\n\n{pdf_result['text']}")
                            pdf_metadata.append(pdf_result['metadata'])
                            logger.info(f"Successfully extracted embedded PDF {idx}: {len(pdf_result['text'])} chars")
                        else:
                            error_msg = pdf_result.get('error', 'Unknown error')
                            print(f"   ⚠️ No content extracted from PDF: {error_msg}")
                            logger.warning(f"Failed to extract embedded PDF {idx} ({pdf_url}): {error_msg}")
                    except Exception as e:
                        logger.exception(f"Exception processing embedded PDF {idx} ({pdf_url}): {e}")
                        print(f"   ❌ PDF processing failed: {e}")
                
                # Combine text content, iframe content, and PDF content
                full_content = text_content
                if iframe_contents:
                    full_content += "\n\n" + "\n\n".join(iframe_contents)
                    print(f"✓ Added {len(iframe_contents)} iframe content section(s)")
                if pdf_content:
                    full_content += "\n\n" + "\n\n".join(pdf_content)
                
                scrape_result = {
                    'success': result.success,
                    'url': url,
                    'content': full_content,
                    'content_length': len(full_content),
                    'word_count': len(full_content.split()) if full_content else 0,
                    'duration': duration,
                    'status_code': getattr(result, 'status_code', None),
                    'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
                    'pdf_count': len(pdf_content),
                    'pdf_urls': list(pdf_urls),
                    'pdf_metadata': pdf_metadata,
                    'scrape_type': 'html_with_embedded_pdfs' if pdf_content else 'html_only'
                }
                
                logger.info(f"Scrape complete for {url}: {scrape_result['content_length']} chars, {scrape_result['pdf_count']} PDFs")
                return scrape_result
                
        except asyncio.TimeoutError:
            logger.error(f"Timeout scraping {url}")
            print(f"\n❌ Scraper timeout for: {url}")
            return {
                'success': False,
                'url': url,
                'error': 'Request timeout',
                'error_type': 'TimeoutError',
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            logger.exception(f"Exception scraping {url}: {e}")
            print(f"\n❌ Scraper error: {e}")
            import traceback
            traceback.print_exc()
            return {
                'success': False,
                'url': url,
                'error': str(e),
                'error_type': type(e).__name__,
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
            }
    
    async def scrape_many(self, urls: List[str], delay: float = 1.0) -> Dict[str, Dict[str, Any]]:
        """Scrape multiple URLs sequentially.
        
        Args:
            urls: List of URLs to scrape
            delay: Delay between requests in seconds
            
        Returns:
            Dictionary mapping URLs to their scrape results
        """
        results = {}
        
        for url in urls:
            result = await self.scrape(url)
            results[url] = result
            
            if delay > 0:
                await asyncio.sleep(delay)
        
        return results
    
    def create_custom_config(
        self,
        css_selector: Optional[str] = None,
        wait_until: str = "networkidle",
        delay: float = 3.0,
        remove_popups: bool = True,
        custom_js: Optional[str] = None,
        **kwargs
    ) -> CrawlerRunConfig:
        """Create a custom crawl configuration.
        
        Args:
            css_selector: CSS selector to extract specific content
            wait_until: Wait condition ('networkidle', 'load', 'domcontentloaded')
            delay: Delay before returning HTML in seconds
            remove_popups: Whether to remove overlay elements
            custom_js: Custom JavaScript to execute
            **kwargs: Additional CrawlerRunConfig parameters
            
        Returns:
            Custom CrawlerRunConfig
        """
        config_dict = {
            'cache_mode': kwargs.get('cache_mode', CacheMode.BYPASS),
            'wait_until': wait_until,
            'page_timeout': kwargs.get('page_timeout', self.timeout),
            'delay_before_return_html': delay,
            'remove_overlay_elements': remove_popups,
            'simulate_user': kwargs.get('simulate_user', True),
            'scan_full_page': kwargs.get('scan_full_page', True),
            'excluded_tags': kwargs.get('excluded_tags', ["script", "style", "noscript"]),
            'verbose': kwargs.get('verbose', False)
        }
        
        if css_selector:
            config_dict['css_selector'] = css_selector
        
        if custom_js:
            config_dict['js_code'] = custom_js
        
        return CrawlerRunConfig(**config_dict)


async def _scrape_with_browser_strategy(url: str, headless: bool = True) -> Dict[str, Any]:
    """Primary crawl4ai browser strategy."""
    try:
        scraper = WebScraper(headless=headless)
        return await scraper.scrape(url)
    except (NotImplementedError, RuntimeError, OSError) as e:
        return {
            'success': False,
            'url': url,
            'error': f"Browser strategy failed: {type(e).__name__}",
            'scraper_type': 'browser_strategy'
        }
    except Exception as e:
        return {
            'success': False,
            'url': url,
            'error': f"Browser strategy failed: {e}",
            'scraper_type': 'browser_strategy'
        }


async def _scrape_with_simple_http_strategy(url: str, headless: bool = True) -> Dict[str, Any]:
    """Simple HTTP fallback strategy (headless arg kept for unified signature)."""
    from .simple_scraper import scrape_url_simple
    return await scrape_url_simple(url)


SCRAPE_STRATEGIES: List[Callable[[str, bool], Awaitable[Dict[str, Any]]]] = [
    _scrape_with_browser_strategy,
    _scrape_with_simple_http_strategy,
]


async def scrape_url(url: str, headless: bool = True) -> Dict[str, Any]:
    """Convenience function to scrape a single URL with ordered strategies.

    Args:
        url: URL to scrape
        headless: Whether to run in headless mode

    Returns:
        Scrape result dictionary
    """
    last_result: Dict[str, Any] = {
        'success': False,
        'url': url,
        'error': 'No scrape strategy executed',
    }

    for strategy in SCRAPE_STRATEGIES:
        result = await strategy(url, headless)
        if result.get('success'):
            return result
        last_result = result
        print(f"[scraper] Strategy failed ({strategy.__name__}) for {url}: {result.get('error', 'unknown error')}")

    return last_result


async def scrape_urls(urls: List[str], headless: bool = True, delay: float = 1.0) -> Dict[str, Dict[str, Any]]:
    """Convenience function to scrape multiple URLs.
    
    Args:
        urls: List of URLs to scrape
        headless: Whether to run in headless mode
        delay: Delay between requests in seconds
        
    Returns:
        Dictionary mapping URLs to scrape results
    """
    scraper = WebScraper(headless=headless)
    return await scraper.scrape_many(urls, delay=delay)


if __name__ == "__main__":
    print("WebScraper: Generic web scraper using crawl4ai")
    print("Usage:")
    print("  from scraper import scrape_url")
    print("  result = await scrape_url('https://example.com')")
