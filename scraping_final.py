import time
import json
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import random
import os

class AmazonReviewsScraper:
    def __init__(self, headless=True):
        """Initialize the scraper with Chrome options"""
        self.options = Options()
        if headless:
            self.options.add_argument('--headless')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.options.add_experimental_option('useAutomationExtension', False)
        
        # Set user agent to avoid detection
        self.options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        self.driver = None
        self.wait = None
    
    def start_driver(self):
        """Start the Chrome driver"""
        try:
            self.driver = webdriver.Chrome(options=self.options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            self.wait = WebDriverWait(self.driver, 10)
            print("Driver started successfully")
        except Exception as e:
            print(f"Error starting driver: {e}")
            raise
    
    def get_reviews_url(self, product_id, is_my_product=True):
        """Generate reviews URL based on product type"""
        if is_my_product:
            # For your product - get positive reviews
            return f"https://www.amazon.com/product-reviews/{product_id}/ref=cm_cr_dp_d_show_all_btm?ie=UTF8&reviewerType=all_reviews&filterByStar=positive"
        else:
            # For competitor - get critical reviews
            return f"https://www.amazon.com/product-reviews/{product_id}/ref=cm_cr_dp_d_show_all_btm?ie=UTF8&reviewerType=all_reviews&filterByStar=critical"
    
    def scrape_reviews(self, product_id, is_my_product=True, max_pages=5):
        """Scrape reviews from Amazon product page"""
        if not self.driver:
            self.start_driver()
        
        reviews_url = self.get_reviews_url(product_id, is_my_product)
        reviews_data = []
        
        product_type = "My Product" if is_my_product else "Competitor"
        review_type = "positive" if is_my_product else "critical"
        
        try:
            print(f"Navigating to reviews page for {product_type} ({review_type} reviews): {reviews_url}")
            self.driver.get(reviews_url)
            
            # Wait for page to load
            time.sleep(random.uniform(20, 30))
            
            for page in range(1, max_pages + 1):
                print(f"Scraping page {page} for {product_type}...")
                
                # Wait for reviews to load
                try:
                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, '[data-hook="review"]')))
                except TimeoutException:
                    print("No reviews found on this page")
                    break
                
                # Find all review containers
                review_elements = self.driver.find_elements(By.CSS_SELECTOR, '[data-hook="review"]')
                
                for review_element in review_elements:
                    try:
                        review_data = self.extract_review_data(review_element)
                        if review_data:
                            reviews_data.append(review_data)
                    except Exception as e:
                        print(f"Error extracting review: {e}")
                        continue
                
                # Try to go to next page
                if page < max_pages:
                    if not self.go_to_next_page():
                        print("No more pages available")
                        break
                
                # Random delay between pages
                time.sleep(random.uniform(2, 5))
            
            print(f"Successfully scraped {len(reviews_data)} {review_type} reviews for {product_type}")
            return reviews_data
            
        except Exception as e:
            print(f"Error scraping reviews for {product_type}: {e}")
            return reviews_data
    
    def extract_review_data(self, review_element):
        """Extract data from a single review element"""
        try:
            review_data = {}
            
            # Review title
            try:
                title_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="review-title"]')
                review_data['title'] = title_element.text.strip()
            except NoSuchElementException:
                review_data['title'] = "N/A"
            
            # Rating
            try:
                rating_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="review-star-rating"]')
                rating_text = rating_element.get_attribute('class')
                # Extract rating from class name (e.g., "a-star-5" -> 5)
                rating = rating_text.split('a-star-')[1].split()[0] if 'a-star-' in rating_text else "N/A"
                review_data['rating'] = rating
            except NoSuchElementException:
                review_data['rating'] = "N/A"
            
            # Review text
            try:
                text_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="review-body"]')
                review_data['text'] = text_element.text.strip()
            except NoSuchElementException:
                review_data['text'] = "N/A"
            
            # Reviewer name
            try:
                author_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="genome-widget"] a')
                review_data['author'] = author_element.text.strip()
            except NoSuchElementException:
                review_data['author'] = "N/A"
            
            # Review date
            try:
                date_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="review-date"]')
                review_data['date'] = date_element.text.strip()
            except NoSuchElementException:
                review_data['date'] = "N/A"
            
            # Verified purchase
            try:
                verified_element = review_element.find_element(By.CSS_SELECTOR, '[data-hook="avp-badge"]')
                review_data['verified_purchase'] = "Yes" if verified_element else "No"
            except NoSuchElementException:
                review_data['verified_purchase'] = "No"
            
            # Helpful votes
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
        """Navigate to the next page of reviews"""
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
        """Save reviews data to CSV file"""
        if not reviews_data:
            print("No data to save")
            return
        
        fieldnames = ['title', 'rating', 'text', 'author', 'date', 'verified_purchase', 'helpful_votes']
        
        # Generate filename based on product type
        if is_my_product:
            filename = f"my_product_positive_reviews_{product_id}.csv"
        else:
            filename = f"competitor_critical_reviews_{product_id}.csv"

        # If save_dir is provided, ensure it exists and use it
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
        """Close the browser driver"""
        if self.driver:
            self.driver.quit()
            print("Driver closed")

def main():
    """Example usage of the AmazonReviewsScraper for both products"""
    # Initialize scraper
    scraper = AmazonReviewsScraper(headless=False)  # Set to True for headless mode
    
    try:
        # Get product IDs
        my_product_id = input("Enter your product ID: ")
        competitor_product_id = input("Enter competitor product ID: ")
        max_pages = int(input("Enter max pages to scrape: "))
        
        # Set save directory for both files
        save_dir = f"D:/college/Profit_Story/task4(2)/task4/{my_product_id}"
        
        # Scrape positive reviews for your product
        print("\n" + "="*60)
        print("SCRAPING POSITIVE REVIEWS FOR YOUR PRODUCT")
        print("="*60)
        my_reviews = scraper.scrape_reviews(my_product_id, is_my_product=True, max_pages=max_pages)
        
        # Save your product reviews
        if my_reviews:
            scraper.save_to_csv(my_reviews, my_product_id, is_my_product=True, save_dir=save_dir)
            print(f"Scraped {len(my_reviews)} positive reviews for your product")
            
            # Print first few reviews
            print("\nFirst 3 positive reviews for your product:")
            for i, review in enumerate(my_reviews[:3], 1):
                print(f"\n--- Review {i} ---")
                print(f"Title: {review['title']}")
                print(f"Rating: {review['rating']}")
                print(f"Author: {review['author']}")
                print(f"Date: {review['date']}")
                print(f"Verified: {review['verified_purchase']}")
                print(f"Text: {review['text'][:100]}...")
        
        # Add delay between products
        print("\nWaiting before scraping competitor reviews...")
        time.sleep(random.uniform(5, 10))
        
        # Scrape critical reviews for competitor
        print("\n" + "="*60)
        print("SCRAPING CRITICAL REVIEWS FOR COMPETITOR")
        print("="*60)
        competitor_reviews = scraper.scrape_reviews(competitor_product_id, is_my_product=False, max_pages=max_pages)
        
        # Save competitor reviews
        if competitor_reviews:
            scraper.save_to_csv(competitor_reviews, competitor_product_id, is_my_product=False, save_dir=save_dir)
            print(f"Scraped {len(competitor_reviews)} critical reviews for competitor")
            
            # Print first few reviews
            print("\nFirst 3 critical reviews for competitor:")
            for i, review in enumerate(competitor_reviews[:3], 1):
                print(f"\n--- Review {i} ---")
                print(f"Title: {review['title']}")
                print(f"Rating: {review['rating']}")
                print(f"Author: {review['author']}")
                print(f"Date: {review['date']}")
                print(f"Verified: {review['verified_purchase']}")
                print(f"Text: {review['text'][:100]}...")
        
        # Summary
        print("\n" + "="*60)
        print("SCRAPING SUMMARY")
        print("="*60)
        print(f"Your product positive reviews: {len(my_reviews) if my_reviews else 0}")
        print(f"Competitor critical reviews: {len(competitor_reviews) if competitor_reviews else 0}")
        
    except Exception as e:
        print(f"Error in main execution: {e}")
    
    finally:
        # Always close the driver
        scraper.close_driver()

if __name__ == "__main__":
    main()