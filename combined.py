#combined.py
import time
import json
import csv
import random
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# --- Rufus & Insights Scraper ---
class AmazonRufusScraper:
    """
    Scraper for extracting Rufus questions and customer insights from Amazon product pages.
    Handles login detection and waits for user to complete login if needed.
    """
    def __init__(self, headless=False, user_data_dir: str = None, profile_dir: str = None):
        self.options = Options()
        self.user_data_dir = user_data_dir
        self.profile_dir = profile_dir
        if headless:
            self.options.add_argument('--headless')
        # If a user data dir or profile dir is provided, use it so we can reuse a logged-in Chrome profile
        if self.user_data_dir:
            # Chrome requires a full path for user-data-dir
            self.options.add_argument(f"--user-data-dir={self.user_data_dir}")
        if self.profile_dir:
            self.options.add_argument(f"--profile-directory={self.profile_dir}")
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)
        self.options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        self.driver = None
        self.wait = None

    def start_driver(self):
        try:
            self.driver = webdriver.Chrome(options=self.options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 60)
            print("✅ Chrome driver started successfully")
            return True
        except Exception as e:
            print(f"❌ Failed to start Chrome driver: {e}")
            return False

    def close(self):
        if self.driver:
            self.driver.quit()
            print("🔒 Browser closed")

    def handle_login_if_required(self):
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

    def extract_rufus_questions(self):
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

    def scrape_product_data(self, product_url):
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

# --- Reviews Scraper ---
class AmazonReviewsScraper:
    def __init__(self, headless=True, user_data_dir: str = None, profile_dir: str = None):
        self.options = Options()
        self.user_data_dir = user_data_dir
        self.profile_dir = profile_dir
        if headless:
            self.options.add_argument('--headless')
        if self.user_data_dir:
            self.options.add_argument(f"--user-data-dir={self.user_data_dir}")
        if self.profile_dir:
            self.options.add_argument(f"--profile-directory={self.profile_dir}")
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)
        self.options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        self.driver = None
        self.wait = None
    def start_driver(self):
        try:
            self.driver = webdriver.Chrome(options=self.options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            # Increase wait time to be more tolerant of slower loads / redirects
            self.wait = WebDriverWait(self.driver, 20)
            print("Driver started successfully")
        except Exception as e:
            print(f"Error starting driver: {e}")
            raise
    def get_reviews_url(self, product_id, is_my_product=True):
        if is_my_product:
            return f"https://www.amazon.in/product-reviews/{product_id}/ref=cm_cr_arp_d_viewopt_sr?ie=UTF8&reviewerType=all_reviews&filterByStar=positive&pageNumber=1"
        else:
            return f"https://www.amazon.in/product-reviews/{product_id}/ref=cm_cr_arp_d_viewopt_sr?ie=UTF8&reviewerType=all_reviews&filterByStar=critical&pageNumber=1"
    def scrape_reviews(self, product_id, is_my_product=True, max_pages=10):
        if not self.driver:
            self.start_driver()
        reviews_url = self.get_reviews_url(product_id, is_my_product)
        reviews_data = []
        product_type = "My Product" if is_my_product else "Competitor"
        review_type = "positive" if is_my_product else "critical"
        try:
            print(f"Navigating to reviews page for {product_type} ({review_type} reviews): {reviews_url}")
            self.driver.get(reviews_url)
            time.sleep(random.uniform(40, 60))
            for page in range(1, max_pages + 1):
                print(f"Scraping page {page} for {product_type}...")
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-hook="review"]')))
                except TimeoutException:
                    print("No reviews found on this page")
                    break
                review_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-hook="review"]')
                for review_element in review_elements:
                    try:
                        review_data = self.extract_review_data(review_element)
                        if review_data:
                            reviews_data.append(review_data)
                    except Exception as e:
                        print(f"Error extracting review: {e}")
                        continue
                if page < max_pages:
                    if not self.go_to_next_page():
                        print("No more pages available")
                        break
                time.sleep(random.uniform(2, 5))
            print(f"Successfully scraped {len(reviews_data)} {review_type} reviews for {product_type}")
            return reviews_data
        except Exception as e:
            print(f"Error scraping reviews for {product_type}: {e}")
            return reviews_data
    def extract_review_data(self, review_element):
        try:
            review_data = {}
            try:
                title_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="review-title"]')
                review_data['title'] = title_element.text.strip()
            except NoSuchElementException:
                review_data['title'] = "N/A"
            try:
                rating_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="review-star-rating"]')
                rating_text = rating_element.get_attribute('class')
                rating = rating_text.split('a-star-')[1].split()[0] if 'a-star-' in rating_text else "N/A"
                review_data['rating'] = rating
            except NoSuchElementException:
                review_data['rating'] = "N/A"
            try:
                text_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="review-body"]')
                review_data['text'] = text_element.text.strip()
            except NoSuchElementException:
                review_data['text'] = "N/A"
            try:
                author_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="genome-widget"] a')
                review_data['author'] = author_element.text.strip()
            except NoSuchElementException:
                review_data['author'] = "N/A"
            try:
                date_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="review-date"]')
                review_data['date'] = date_element.text.strip()
            except NoSuchElementException:
                review_data['date'] = "N/A"
            try:
                verified_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="avp-badge"]')
                review_data['verified_purchase'] = "Yes" if verified_element else "No"
            except NoSuchElementException:
                review_data['verified_purchase'] = "No"
            try:
                helpful_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="helpful-vote-statement"]')
                review_data['helpful_votes'] = helpful_element.text.strip()
            except NoSuchElementException:
                review_data['helpful_votes'] = "0"
            return review_data
        except Exception as e:
            print(f"Error extracting review data: {e}")
            return None
    def go_to_next_page(self):
        try:
            next_button = self.driver.find_element(By.CSS_SELECTOR, 'li.a-last a')
            if next_button.is_enabled():
                next_button.click()
                time.sleep(random.uniform(2, 4))
                return True
            else:
                return False
        except NoSuchElementException:
            return False
    def save_to_csv(self, reviews_data, product_id, is_my_product=True, save_dir=None):
        if not reviews_data:
            print("No data to save")
            return
        fieldnames = ['title', 'rating', 'text', 'author', 'date', 'verified_purchase', 'helpful_votes']
        if is_my_product:
            filename = f"my_product_positive_reviews_{product_id}.csv"
        else:
            filename = f"competitor_critical_reviews_{product_id}.csv"
        if save_dir:
            os.makedirs(save_dir, exist_ok=True)
            filepath = os.path.join(save_dir, filename)
        else:
            filepath = filename
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(reviews_data)
        print(f"Data saved to {filepath}")
    def close_driver(self):
        if self.driver:
            self.driver.quit()
            print("Driver closed")

# --- Unified Main Function ---
def main():
    print("\n" + "="*60)
    print("AMAZON SCRAPER: Rufus, Insights, and Reviews")
    print("="*60)
    print("Select an option:")
    print("1. Scrape Rufus questions & customer insights")
    print("2. Scrape reviews (positive/critical)")
    print("3. Scrape both")
    print("0. Exit")
    choice = input("Enter your choice: ").strip()
    if choice == '1':
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
        results = scraper.scrape_product_data(product_url)
        if results['success']:
            scraper.save_to_txt(results, product_id, save_dir)
        scraper.close()
    elif choice == '2':
        my_product_id = input("Enter your product ID: ").strip()
        competitor_product_id = input("Enter competitor product ID: ").strip()
        max_pages = int(input("Enter max pages to scrape: "))
        save_dir = f"amazon_data/{my_product_id}" if my_product_id else None
        scraper = AmazonReviewsScraper(headless=False)
        my_reviews = scraper.scrape_reviews(my_product_id, is_my_product=True, max_pages=max_pages)
        if my_reviews:
            scraper.save_to_csv(my_reviews, my_product_id, is_my_product=True, save_dir=save_dir)
        competitor_reviews = scraper.scrape_reviews(competitor_product_id, is_my_product=False, max_pages=max_pages)
        if competitor_reviews:
            scraper.save_to_csv(competitor_reviews, competitor_product_id, is_my_product=False, save_dir=save_dir)
        scraper.close_driver()
    elif choice == '3':
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
        rufus_scraper = AmazonRufusScraper(headless=False)
        results = rufus_scraper.scrape_product_data(product_url)
        if results['success']:
            rufus_scraper.save_to_txt(results, product_id, save_dir)
        rufus_scraper.close()
        my_product_id = product_id
        competitor_product_id = input("Enter competitor product ID: ").strip()
        max_pages = int(input("Enter max pages to scrape: "))
        reviews_scraper = AmazonReviewsScraper(headless=False)
        my_reviews = reviews_scraper.scrape_reviews(my_product_id, is_my_product=True, max_pages=max_pages)
        if my_reviews:
            reviews_scraper.save_to_csv(my_reviews, my_product_id, is_my_product=True, save_dir=save_dir)
        competitor_reviews = reviews_scraper.scrape_reviews(competitor_product_id, is_my_product=False, max_pages=max_pages)
        if competitor_reviews:
            reviews_scraper.save_to_csv(competitor_reviews, competitor_product_id, is_my_product=False, save_dir=save_dir)
        reviews_scraper.close_driver()
    else:
        print("Exiting.")

if __name__ == "__main__":
    main() 