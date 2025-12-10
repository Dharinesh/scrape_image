'''
from scraping.crew import ProductScraperCrew  # Adjust import path as needed
import sys
import os

def validate_amazon_url(url):
    """Validate if the URL is a valid Amazon product page"""
    amazon_domains = ['amazon.com', 'amazon.co.uk', 'amazon.ca', 'amazon.de', 'amazon.fr', 'amazon.it', 'amazon.es', 'amazon.in', 'amazon.co.jp']
    
    if not url.startswith(('http://', 'https://')):
        return False, "URL must start with http:// or https://"
    
    # Check if it's an Amazon domain
    is_amazon = any(domain in url.lower() for domain in amazon_domains)
    if not is_amazon:
        return False, "URL must be from an Amazon domain"
    
    return True, "Valid Amazon product URL"

def get_amazon_url():
    """Get and validate Amazon product URL from user input"""
    while True:
        print("\n" + "="*60)
        print("AMAZON PRODUCT REVIEW SCRAPER")
        print("="*60)
        print("Please enter the Amazon product page URL.")
        print("Example: https://www.amazon.com/dp/B08N5WRWNW")
        print("Note: This will scrape ALL reviews across ALL pages")
        print("-"*60)
        
        website_url = input("Amazon Product URL: ").strip()
        
        if not website_url:
            print("❌ Error: URL cannot be empty. Please try again.")
            continue
        
        # Validate URL
        is_valid, message = validate_amazon_url(website_url)
        if not is_valid:
            print(f"❌ Error: {message}")
            print("Please enter a valid Amazon product page URL.")
            continue
        
        # Confirm with user
        print(f"\n✅ Valid URL detected: {website_url}")
        confirm = input("Proceed with scraping? (y/n): ").strip().lower()
        
        if confirm in ['y', 'yes']:
            return website_url
        elif confirm in ['n', 'no']:
            print("Operation cancelled by user.")
            sys.exit(0)
        else:
            print("Please enter 'y' for yes or 'n' for no.")

def run():
    """Main scraping method - Entry point for the application"""
    try:
        print("🔍 Starting Amazon Product Review Scraping System...")
        print("📋 This tool will collect ALL customer reviews from ALL pages")
        print("⚡ Features: Pagination handling, comprehensive data extraction, error recovery")
        
        print("\n🚀 Initializing Amazon Review Scraper...")
        print("⚠️  WARNING: This process may take several minutes depending on the number of review pages.")
        
        # Get the URL from user input with validation
        website_url = get_amazon_url()
        
        # Create crew instance
        print("\n📊 Setting up scraping crew...")
        crew_instance = ProductScraperCrew()
        
        # Display scraping information
        print("\n" + "="*60)
        print("SCRAPING STARTED")
        print("="*60)
        print(f"🔗 Target URL: {website_url}")
        print("📝 Task: Extract ALL customer reviews from ALL pages")
        print("⏱️  Status: Processing... (this may take a while)")
        print("="*60)
        
        # Run the crew with the URL
        result = crew_instance.kickoff(website_url)
        
        print("\n" + "="*60)
        print("✅ SCRAPING COMPLETED SUCCESSFULLY!")
        print("="*60)
        print("📁 Check the 'output-files' directory for your CSV file")
        print("📊 The file contains all reviews from all pages")
        print("="*60)
        
        print(f"\n🎉 Scraping session completed!")
        print("💾 Data has been saved to CSV format")
        print("📈 You can now analyze the comprehensive review dataset")
        
        return result
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Scraping interrupted by user (Ctrl+C)")
        print("🔄 Partial data may have been saved to CSV file")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Error running crew: {str(e)}")
        print("\n🔧 Troubleshooting tips:")
        print("1. Check your internet connection")
        print("2. Verify the Amazon URL is correct and accessible")
        print("3. Ensure all required dependencies are installed")
        print("4. Check if the output-files directory exists and is writable")
        print(f"\n💥 Fatal error occurred: {str(e)}")
        print("🆘 Please check the error message above and try again")
        raise

if __name__ == "__main__":
    run()'''

#!/usr/bin/env python3

import os
import sys
import csv
import json
import re
from datetime import datetime
from typing import Dict, List, Any

# CrewAI imports
from crewai import Agent, Task, Crew, Process
from crewai_tools import SeleniumScrapingTool

def extract_asin_from_url(url: str) -> str:
    """Extract ASIN from Amazon product URL"""
    try:
        # Common patterns for ASIN in Amazon URLs
        if "/dp/" in url:
            return url.split("/dp/")[1].split("/")[0]
        elif "/gp/product/" in url:
            return url.split("/gp/product/")[1].split("/")[0]
        elif "/product-reviews/" in url:
            return url.split("/product-reviews/")[1].split("/")[0]
        else:
            # Try to find 10-character alphanumeric string (typical ASIN format)
            asin_match = re.search(r'/([A-Z0-9]{10})(?:/|$|\?)', url)
            if asin_match:
                return asin_match.group(1)
            else:
                return "UNKNOWN_ASIN"
    except:
        return "UNKNOWN_ASIN"

def build_reviews_url(url: str) -> str:
    """Convert product URL to reviews URL if needed"""
    if "/product-reviews/" in url:
        return url
    
    asin = extract_asin_from_url(url)
    return f"https://www.amazon.com/product-reviews/{asin}/ref=cm_cr_dp_d_show_all_btm?ie=UTF8&reviewerType=all_reviews"

def save_reviews_to_csv(reviews_data: str, asin: str) -> str:
    """Save scraped reviews to CSV file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"customer_reviews_all_pages_{timestamp}.csv"
    
    try:
        # Parse the reviews data (assuming it's structured text)
        lines = reviews_data.split('\n')
        reviews = []
        
        # Simple parsing - this would be adjusted based on actual scraper output
        current_review = {}
        page_num = 1
        
        for line in lines:
            line = line.strip()
            if line:
                # Basic parsing logic - adjust based on actual data structure
                if "Customer Name:" in line:
                    current_review['customer_name'] = line.replace("Customer Name:", "").strip()
                elif "Rating:" in line:
                    current_review['rating'] = line.replace("Rating:", "").strip()
                elif "Title:" in line:
                    current_review['review_title'] = line.replace("Title:", "").strip()
                elif "Review:" in line:
                    current_review['review_text'] = line.replace("Review:", "").strip()
                elif "Date:" in line:
                    current_review['review_date'] = line.replace("Date:", "").strip()
                elif "Verified:" in line:
                    current_review['verified_purchase'] = line.replace("Verified:", "").strip()
                elif "Helpful:" in line:
                    current_review['helpful_votes'] = line.replace("Helpful:", "").strip()
                    # End of review, save it
                    current_review['asin'] = asin
                    current_review['page_number'] = page_num
                    reviews.append(current_review.copy())
                    current_review = {}
        
        # Write to CSV
        if reviews:
            with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = ['asin', 'customer_name', 'rating', 'review_title', 'review_text', 
                             'review_date', 'verified_purchase', 'helpful_votes', 'page_number']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(reviews)
        
        return filename
    except Exception as e:
        print(f"Error saving to CSV: {str(e)}")
        return ""

def main():
    """Main function to run the CrewAI scraping process"""
    
    # Get URL from command line argument or prompt user
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Enter the Amazon product URL: ").strip()
    
    if not url:
        print("Please provide a valid Amazon URL")
        return
    
    # Extract ASIN and build reviews URL
    asin = extract_asin_from_url(url)
    reviews_url = build_reviews_url(url)
    
    print(f"Product ASIN: {asin}")
    print(f"Reviews URL: {reviews_url}")
    
    # Initialize the Selenium scraping tool
    selenium_tool = SeleniumScrapingTool()
    
    # Create the scraper agent
    scraper_agent = Agent(
        role="Senior Amazon Reviews Data Scraper & Pagination Expert",
        goal="Comprehensively scrape ALL customer reviews from an Amazon product page by navigating through all available review pages using pagination controls.",
        backstory="""You are an experienced web scraper specialized in e-commerce platforms, particularly Amazon.
        Your expertise includes:
        - Navigating complex pagination systems
        - Handling dynamic content loading
        - Extracting structured data from customer reviews
        - Managing large-scale data collection across multiple pages
        - Implementing robust error handling for web scraping operations
        
        You understand that Amazon reviews are paginated and that collecting comprehensive review data
        requires systematically navigating through all available pages. You know how to identify
        pagination controls, handle page transitions, and ensure no data is lost during the scraping process.""",
        tools=[selenium_tool],
        verbose=True,
        allow_delegation=False
    )
    
    # Create the scraping task
    scraping_task = Task(
        description=f"""Navigate to the Amazon reviews page and scrape ALL customer reviews across multiple pages.
        
        URL to scrape: {reviews_url}
        Product ASIN: {asin}
        
        IMPORTANT INSTRUCTIONS:
        1. Start by scraping reviews from the first page
        2. Extract the following data for each review:
           - Customer Name (from profile name)
           - Rating (star rating, e.g., "5.0 out of 5 stars")
           - Review Title 
           - Review Text/Content
           - Review Date
           - Verified Purchase status (look for "Verified Purchase" badge)
           - Helpful votes (if available)
        
        3. PAGINATION HANDLING:
           - After scraping the current page, look for the "Next" button 
           - Use CSS selector: "ul.a-pagination li.a-last a" or similar pagination controls
           - If the "Next" button exists and is clickable (not disabled), navigate to the next page
           - Continue scraping reviews from each subsequent page
           - Repeat this process until you reach the last page (when Next button is disabled or doesn't exist)
           - Keep track of the current page number for reference
        
        4. DATA STRUCTURE:
           - For each review, extract data in this format:
             Customer Name: [name]
             Rating: [rating]
             Title: [review title]
             Review: [review text]
             Date: [review date]
             Verified: [Yes/No]
             Helpful: [helpful votes count]
             ---
        
        5. ERROR HANDLING:
           - If a page fails to load, log the error and continue with the next page
           - If pagination fails, ensure already collected data is preserved
           - Handle cases where reviews might be loading dynamically (wait for elements to load)
        
        6. COMPLETION CRITERIA:
           - Stop when the "Next" button is no longer available or clickable
           - Ensure all available review pages have been processed
           - Provide a summary of total pages scraped and total reviews collected
        
        Use the SeleniumScrapingTool to navigate through all pages and extract all reviews systematically.""",
        
        expected_output=f"""A comprehensive structured dataset containing ALL customer reviews from ALL pages of the Amazon product.
        
        For each review, provide data in this exact format:
        Customer Name: [extracted name]
        Rating: [star rating]
        Title: [review title]
        Review: [full review text]
        Date: [review date]
        Verified: [Yes/No for verified purchase]
        Helpful: [helpful votes count]
        ---
        
        At the end, include a summary:
        SCRAPING SUMMARY:
        - Product ASIN: {asin}
        - Total pages scraped: [number]
        - Total reviews collected: [number]
        - Any errors encountered: [list errors]
        
        The reviews should be ready for CSV conversion with all necessary data fields extracted.""",
        
        agent=scraper_agent
    )
    
    # Create and run the crew
    crew = Crew(
        agents=[scraper_agent],
        tasks=[scraping_task],
        process=Process.sequential,
        verbose=True
    )
    
    print(f"\nStarting Amazon reviews scraping for: {url}")
    print("This may take several minutes depending on the number of review pages...")
    print("="*60)
    
    try:
        # Execute the crew
        result = crew.kickoff()
        
        print("\n" + "="*60)
        print("SCRAPING COMPLETED")
        print("="*60)
        print(result)
        
        # Save to CSV
        if result:
            filename = save_reviews_to_csv(str(result), asin)
            if filename:
                print(f"\nReviews saved to: {filename}")
            else:
                print("\nNote: CSV conversion failed, but raw data is displayed above")
        
    except Exception as e:
        print(f"Error during scraping: {str(e)}")
        print("Please check your internet connection and try again.")

if __name__ == "__main__":
    main()