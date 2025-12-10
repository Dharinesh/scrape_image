import time
import json
import random
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

class AmazonRufusScraper:
    """
    Scraper for extracting Rufus questions and customer insights from Amazon product pages.
    Handles login detection and waits for user to complete login if needed.
    """
    def __init__(self, headless=False):
        self.options = Options()
        if headless:
            self.options.add_argument('--headless')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)
        self.options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        self.driver = None
        self.wait = None

    # --- Driver Management ---
    def start_driver(self):
        try:
            self.driver = webdriver.Chrome(options=self.options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 20)
            print("✅ Chrome driver started successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to start Chrome driver: {e}")
            return False

    def close(self):
        if self.driver:
            self.driver.quit()
            print("🔒 Browser closed")

    # --- Navigation & Login ---
    def handle_login_if_required(self):
        """If login is required, prompt user to log in and auto-detect when login is complete."""
        try:
            current_url = self.driver.current_url
            signin_selectors = [
                'a[href*="ap/signin"] .a-button-text',
                'a[href*="ap/signin"]',
                'a.a-button-text[href*="signin"]',
                '.nav-signin-tooltip a',
                '#nav-link-accountList'
            ]
            for selector in signin_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed() and el.is_enabled():
                        text = el.get_attribute('textContent') or el.text or ""
                        if any(k in text.lower() for k in ['sign in', 'sign-in', 'login', 'hello']):
                            self.driver.execute_script("arguments[0].click();", el)
                            time.sleep(5)
                            break
            current_url = self.driver.current_url
            if "ap/signin" in current_url or "ap/register" in current_url:
                print("🔑 Please complete login in the browser. Script will auto-detect when login is complete.")
                return self.wait_for_login_completion()
            return True
        except Exception as e:
            print(f"❌ Error handling login: {e}")
            return False

    def wait_for_login_completion(self):
        """Wait for user to complete login (auto-detect by URL or nav element)."""
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                current_url = self.driver.current_url
                if ("ap/" not in current_url and "amazon.in" in current_url) or self.check_logged_in_elements():
                    print("✅ Login completed. Proceeding...")
                    time.sleep(2)
                    return True
                time.sleep(2)
            except Exception:
                time.sleep(2)
        print("⚠️ Login detection timeout. Attempting to continue anyway...")
        return True

    def check_logged_in_elements(self):
        """Check for elements that indicate user is logged in."""
        selectors = [
            '#nav-link-accountList[aria-label*="Hello"]',
            '.nav-line-1[dir="ltr"]',
            '#nav-tools a[href*="your-account"]',
        ]
        for selector in selectors:
            elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            for el in elements:
                if el.is_displayed():
                    text = el.get_attribute('textContent') or el.text or ""
                    if "hello" in text.lower() and len(text.strip()) > 10:
                        return True
        return False

    def navigate_to_product(self, product_url):
        """Navigate to the product page, handle login if needed, and ensure product page is loaded."""
        try:
            print(f"🔍 Navigating to product: {product_url}")
            self.driver.get(product_url)
            time.sleep(random.uniform(3, 6))
            if not self.handle_login_if_required():
                return False
            current_url = self.driver.current_url
            if product_url not in current_url and "ap/" not in current_url:
                self.driver.get(product_url)
                time.sleep(random.uniform(3, 6))
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2)
            print("✅ Product page loaded")
            return True
        except Exception as e:
            print(f"❌ Failed to navigate to product: {e}")
            return False

    # --- Extraction Methods ---
    def extract_rufus_questions(self):
        """Extract Rufus questions from the current product page."""
        try:
            print("🔍 Extracting Rufus questions...")
            questions = []
            selectors = [
                ".dpx-rex-nile-inline-pill-carousel-element .a-button-text",
                ".dpx-rex-nile-inline-pill-carousel-element button",
                ".dpx-rex-nile-inline-pill-carousel-element input[type='submit']",
                "[data-dpx-rex-nile-inline-pill-clicked] .a-button-text",
                "[data-blue-metrics='PILL_CLICK'] .a-button-text"
            ]
            for selector in selectors:
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".dpx-rex-nile-inline-pill-carousel")))
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for i, el in enumerate(elements, 1):
                        text = (el.get_attribute('textContent') or el.get_attribute('value') or el.text).strip()
                        if text and '?' in text:
                            questions.append({'question_number': i, 'question_text': text, 'selector_used': selector})
                    if questions:
                        break
                except Exception:
                    continue
            if not questions:
                all_elements = self.driver.find_elements(By.CSS_SELECTOR, "button, input[type='submit'], .a-button-text")
                for el in all_elements:
                    text = (el.get_attribute('value') or el.get_attribute('textContent') or el.text)
                    if text and '?' in text and 10 < len(text.strip()) < 200:
                        if not any(skip in text.lower() for skip in ['sign in', 'add to cart', 'buy now', 'search']):
                            questions.append({'question_number': len(questions) + 1, 'question_text': text.strip(), 'selector_used': 'fallback'})
            print(f"✅ Found {len(questions)} Rufus questions" if questions else "⚠️  No Rufus questions found")
            return questions
        except Exception as e:
            print(f"❌ Error extracting Rufus questions: {e}")
            return []

    def extract_customer_insights(self):
        """Extract 'Customers say' section and aspect buttons."""
        insights = {'customers_say_summary': '', 'aspects': []}
        try:
            print("🔍 Extracting customer insights...")
            summary_selectors = [
                '#cr-product-insights-cards #product-summary p:first-of-type',
                '[data-hook="cr-insights-widget-summary"] p:first-of-type',
                '#product-summary .a-spacing-small:first-of-type'
            ]
            for selector in summary_selectors:
                try:
                    summary_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if summary_element and summary_element.text.strip():
                        insights['customers_say_summary'] = summary_element.text.strip()
                        break
                except Exception:
                    continue
            aspect_selectors = [
                '[data-hook="cr-insights-aspect-link"]',
                '.a-section[role="tablist"] a[role="tab"]',
                '._Y3Itc_aspect-link_TtdmS'
            ]
            for selector in aspect_selectors:
                try:
                    aspect_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for i, element in enumerate(aspect_elements, 1):
                        aspect_text = element.text.strip()
                        if aspect_text and len(aspect_text) > 2:
                            is_positive = True
                            try:
                                svg_path = element.find_element(By.CSS_SELECTOR, 'svg path')
                                if svg_path:
                                    fill_color = svg_path.get_attribute('fill')
                                    if fill_color and '#DE7921' in fill_color:
                                        is_positive = False
                            except Exception:
                                pass
                            aria_label = element.get_attribute('aria-label') or ''
                            aspect_info = {
                                'aspect_number': i,
                                'aspect_text': aspect_text,
                                'sentiment': 'positive' if is_positive else 'negative',
                                'aria_label': aria_label,
                                'selector_used': selector
                            }
                            insights['aspects'].append(aspect_info)
                    if insights['aspects']:
                        break
                except Exception:
                    continue
            print(f"✅ Found customer insights: Summary={'✓' if insights['customers_say_summary'] else '✗'}, Aspects={len(insights['aspects'])}")
            return insights
        except Exception as e:
            print(f"❌ Error extracting customer insights: {e}")
            return insights

    # --- Main Scraping Workflow ---
    def scrape_product_data(self, product_url):
        """Complete workflow: start driver, navigate, handle login, extract questions and insights."""
        results = {
            'product_url': product_url,
            'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            'rufus_questions': [],
            'customer_insights': {},
            'data_sources_found': [],
            'success': False
        }
        try:
            if not self.start_driver():
                return results
            if not self.navigate_to_product(product_url):
                return results
            wait_time = random.uniform(5, 10)
            print(f"⏳ Waiting {wait_time:.1f} seconds for content to load...")
            time.sleep(wait_time)
            print("\n" + "="*50)
            print("EXTRACTING ALL AVAILABLE DATA")
            print("="*50)
            questions = self.extract_rufus_questions()
            if questions:
                results['rufus_questions'] = questions
                results['data_sources_found'].append('rufus_questions')
            insights = self.extract_customer_insights()
            if insights['customers_say_summary'] or insights['aspects']:
                results['customer_insights'] = insights
                results['data_sources_found'].append('customer_insights')
            if results['data_sources_found']:
                results['success'] = True
                print(f"\n✅ Successfully extracted data from: {', '.join(results['data_sources_found'])}")
            else:
                print("\n⚠️  No data found from any source")
            return results
        except Exception as e:
            print(f"❌ Scraping failed: {e}")
            results['error'] = str(e)
            return results
        finally:
            pass

    # --- Save Results ---
    def save_to_txt(self, results, product_id=None, save_dir=None):
        try:
            filename = f"amazon_complete_data_{product_id or int(time.time())}.txt"
            if save_dir:
                os.makedirs(save_dir, exist_ok=True)
                filepath = os.path.join(save_dir, filename)
            else:
                filepath = filename
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write("AMAZON PRODUCT DATA EXTRACTION RESULTS\n")
                f.write("="*80 + "\n\n")
                if results.get('rufus_questions'):
                    f.write("="*50 + "\n")
                    f.write(f"RUFUS QUESTIONS ({len(results['rufus_questions'])} found)\n")
                    f.write("="*50 + "\n\n")
                    for i, question in enumerate(results['rufus_questions'], 1):
                        f.write(f"{i}. {question['question_text']}\n")
                if results.get('customer_insights'):
                    insights = results['customer_insights']
                    f.write("="*50 + "\n")
                    f.write("CUSTOMER INSIGHTS\n")
                    f.write("="*50 + "\n\n")
                    if insights.get('customers_say_summary'):
                        f.write("CUSTOMERS SAY SUMMARY:\n")
                        f.write("-" * 25 + "\n")
                        f.write(f"{insights['customers_say_summary']}\n\n")
                    if insights.get('aspects'):
                        f.write(f"CUSTOMER ASPECTS ({len(insights['aspects'])} found):\n")
                        f.write("-" * 30 + "\n")
                        for aspect in insights['aspects']:
                            sentiment_symbol = "👍 [POSITIVE]" if aspect['sentiment'] == 'positive' else "👎 [NEGATIVE]"
                            f.write(f"{aspect['aspect_text']}\n")
                f.write("="*50 + "\n")
                if 'error' in results:
                    f.write(f"\nError Details: {results['error']}\n")
                f.write("\n" + "="*80 + "\n")
                f.write("END OF REPORT\n")
                f.write("="*80 + "\n")
            print(f"💾 Results saved to: {filepath}")
            return filepath
        except Exception as e:
            print(f"❌ Error saving to TXT: {e}")
            return None

# --- Main Entry Point ---
def main():
    scraper = None
    try:
        product_url = input("Enter Amazon product URL: ").strip()
        if not product_url:
            product_url = "https://www.amazon.in/dp/B08N5WRWNW"
            print(f"Using example product: {product_url}")
        product_id = None
        if "/dp/" in product_url:
            product_id = product_url.split("/dp/")[1].split("/")[0].split("?")[0]
        elif "/gp/product/" in product_url:
            product_id = product_url.split("/gp/product/")[1].split("/")[0].split("?")[0]
        save_dir = f"amazon_data/{product_id}" if product_id else None
        scraper = AmazonRufusScraper(headless=False)
        print("\n" + "="*60)
        print("SCRAPING COMPLETE AMAZON PRODUCT DATA")
        print("="*60)
        results = scraper.scrape_product_data(product_url)
        print("\n" + "="*60)
        print("SCRAPING RESULTS")
        print("="*60)
        if results['success']:
            print(f"✅ Successfully scraped data from: {', '.join(results['data_sources_found'])}")
            print(f"📅 Timestamp: {results['timestamp']}")
            print(f"🔗 Product URL: {results['product_url']}")
            if 'rufus_questions' in results['data_sources_found'] and results['rufus_questions']:
                print(f"\n❓ RUFUS QUESTIONS ({len(results['rufus_questions'])} found):")
                for q in results['rufus_questions']:
                    selector_info = f" (via {q.get('selector_used', 'unknown')})" if 'selector_used' in q else ""
                    print(f"  {q['question_number']}. {q['question_text']}{selector_info}")
            if 'customer_insights' in results['data_sources_found']:
                insights = results['customer_insights']
                if insights.get('customers_say_summary'):
                    print(f"\n💬 CUSTOMERS SAY SUMMARY:")
                    print(f"  {insights['customers_say_summary']}")
                if insights.get('aspects'):
                    print(f"\n🏷️  CUSTOMER ASPECTS ({len(insights['aspects'])} found):")
                    for aspect in insights['aspects']:
                        sentiment_emoji = "👍" if aspect['sentiment'] == 'positive' else "👎"
                        selector_info = f" (via {aspect.get('selector_used', 'unknown')})" if 'selector_used' in aspect else ""
                        print(f"  {aspect['aspect_number']}. {sentiment_emoji} {aspect['aspect_text']}{selector_info}")
                        if aspect.get('aria_label'):
                            print(f"      └─ {aspect['aria_label']}")
            print(f"\n📊 DATA SUMMARY:")
            print(f"  • Rufus Questions: {len(results.get('rufus_questions', []))}")
            print(f"  • Customer Summary: {'✓' if results.get('customer_insights', {}).get('customers_say_summary') else '✗'}")
            print(f"  • Customer Aspects: {len(results.get('customer_insights', {}).get('aspects', []))}")
            scraper.save_to_txt(results, product_id, save_dir)
        else:
            print("❌ Scraping failed - no data found")
            if 'error' in results:
                print(f"Error: {results['error']}")
            print("\n💡 Troubleshooting tips:")
            print("   - Make sure you're logged into Amazon")
            print("   - Try a different product")
            print("   - Check if the product page has loaded completely")
            print("   - Rufus or customer insights might not be available for this product")
        try:
            choice = input("\nKeep browser open for inspection? (y/n): ").lower().strip()
            if choice != 'y':
                scraper.close()
            else:
                print("🌐 Browser kept open. Close manually when done.")
        except KeyboardInterrupt:
            print("\n🔒 Closing browser...")
            scraper.close()
    except KeyboardInterrupt:
        print("\n⚠️  Scraping interrupted by user")
        if scraper:
            scraper.close()
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        if scraper:
            scraper.close()
    finally:
        pass

if __name__ == "__main__":
    main()