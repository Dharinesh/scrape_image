from selenium import webdriver
from selenium.webdriver.chrome.service import Service
import os

try:
    chrome_driver_path = os.path.join(os.getcwd(), 'chromedriver.exe')
    print(f"Looking for ChromeDriver at: {chrome_driver_path}")
    
    if not os.path.exists(chrome_driver_path):
        print(f"❌ ChromeDriver not found!")
    else:
        print(f"✅ ChromeDriver found!")
        
        service = Service(chrome_driver_path)
        driver = webdriver.Chrome(service=service)
        driver.get("https://www.google.com")
        print(f"✅ Browser opened successfully!")
        print(f"Page title: {driver.title}")
        driver.quit()
        print(f"✅ Test passed!")
        
except Exception as e:
    print(f"❌ Error: {e}")