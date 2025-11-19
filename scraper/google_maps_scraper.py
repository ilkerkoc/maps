from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import time
import re
from io import StringIO

class GoogleMapsScraper:
    def __init__(self):
        self.driver = self._init_driver()

    def _init_driver(self):
        import os
        import platform
        
        options = Options()
        options.add_argument('--headless')  # Remove or comment out this line for debugging
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--disable-software-rasterizer')
        options.add_argument('--disable-extensions')
        options.add_argument('--disable-logging')
        options.add_argument('--disable-infobars')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # Set Chrome binary location based on OS
        system = platform.system()
        if system == 'Linux':
            # Try common Linux Chrome paths
            chrome_paths = [
                '/usr/bin/google-chrome',
                '/usr/bin/google-chrome-stable',
                '/usr/bin/chromium-browser',
                '/usr/bin/chromium',
            ]
            for path in chrome_paths:
                if os.path.exists(path):
                    options.binary_location = path
                    break
        elif system == 'Windows':
            # Windows Chrome paths
            chrome_paths = [
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
            ]
            for path in chrome_paths:
                if os.path.exists(path):
                    options.binary_location = path
                    break
        
        # Try ChromeDriverManager with cache bypass to get latest version
        try:
            # Force ChromeDriverManager to download latest version by setting cache_valid_range to 0
            from webdriver_manager.core.os_manager import ChromeType
            driver_path = ChromeDriverManager(
                chrome_type=ChromeType.CHROMIUM,
                cache_valid_range=0  # Force download latest version
            ).install()
            if system == 'Linux' and os.path.exists(driver_path):
                os.chmod(driver_path, 0o755)
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=options)
            return driver
        except Exception as e:
            print(f"ChromeDriverManager with Chromium type and cache bypass failed: {e}")
            # Try regular ChromeDriverManager with cache bypass
            try:
                driver_path = ChromeDriverManager(cache_valid_range=0).install()
                if system == 'Linux' and os.path.exists(driver_path):
                    os.chmod(driver_path, 0o755)
                service = Service(driver_path)
                driver = webdriver.Chrome(service=service, options=options)
                return driver
            except Exception as e2:
                print(f"ChromeDriverManager with cache bypass failed: {e2}")
                # Try Selenium's automatic driver management
                try:
                    driver = webdriver.Chrome(options=options)
                    return driver
                except Exception as e3:
                    print(f"Selenium automatic driver management failed: {e3}")
                    # Try system chromedriver if available
                    if system == 'Linux':
                        system_chromedriver_paths = [
                            '/usr/bin/chromedriver',
                            '/usr/lib/chromium-browser/chromedriver',
                        ]
                        for chromedriver_path in system_chromedriver_paths:
                            if os.path.exists(chromedriver_path):
                                try:
                                    os.chmod(chromedriver_path, 0o755)
                                    service = Service(chromedriver_path)
                                    driver = webdriver.Chrome(service=service, options=options)
                                    return driver
                                except Exception as e4:
                                    print(f"System chromedriver at {chromedriver_path} failed: {e4}")
                                    continue
                    
                    error_msg = f"Failed to initialize Chrome driver. All methods failed. Errors: {e}, {e2}, {e3}"
                    print(error_msg)
                    raise Exception(error_msg)

    def scrape(self, query, max_results=100, max_pages=5, progress_callback=None):
        if progress_callback:
            progress_callback("Loading Google Maps...")
        
        try:
            self.driver.get(f"https://www.google.com/maps/search/{query}")
        except Exception as e:
            if progress_callback:
                progress_callback(f"Error loading page: {str(e)}")
            raise

        wait = WebDriverWait(self.driver, 15)  # Increased timeout for Cloud
        if progress_callback:
            progress_callback("Waiting for page to load...")
        # Use explicit wait instead of fixed sleep
        try:
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'a.hfpxzc')))
        except TimeoutException:
            pass  # Continue even if elements not found immediately

        # Check if the business name matches the query in the h1 tag
        try:
            h1_element = wait.until(EC.presence_of_element_located((By.XPATH, "//h1[@class='DUwDvf lfPIob']")))
            business_name_in_h1 = h1_element.text.strip()

            if query.lower() in business_name_in_h1.lower():
                print(f"Direct business match found: {business_name_in_h1}")
                if progress_callback:
                    progress_callback("Scraping single business page...")
                csv_string = self._scrape_single_business_page()
                self.driver.quit()
                return csv_string

        except TimeoutException:
            print("No h1 tag found or business name does not match the query.")

        results = []
        for i in range(max_pages):  # Loop through a fixed number of pages
            if len(results) >= max_results:
                break

            page_msg = f"Scraping page {i+1}/{max_pages}... (Found {len(results)} results so far)"
            print(page_msg)
            if progress_callback:
                progress_callback(page_msg)
            
            try:
                businesses = wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a.hfpxzc')))
                print(f"Found {len(businesses)} businesses on this page.")
                if progress_callback:
                    progress_callback(f"Page {i+1}: Found {len(businesses)} businesses")
            except TimeoutException:
                print("Timeout: No businesses found.")
                if progress_callback:
                    progress_callback(f"Timeout: No businesses found on page {i+1}")
                break

            for idx, business in enumerate(businesses):
                if len(results) >= max_results:
                    break
                    
                try:
                    business_name = business.get_attribute('aria-label')
                    if not business_name:
                        continue

                    # Skip sponsored businesses
                    try:
                        sponsored = business.find_element(By.XPATH, ".//span[contains(text(), 'Sponsored')]")
                        if sponsored:
                            print("Skipping sponsored business...")
                            continue
                    except NoSuchElementException:
                        pass  # No "Sponsored" label found, proceed normally

                    # Skip businesses with "· Visited link" in the name
                    if "· Visited link" in business_name:
                        print(f"Skipping business: {business_name}")
                        continue

                    current_msg = f"Processing: {business_name} ({len(results)+1}/{max_results})"
                    print(current_msg)
                    if progress_callback:
                        progress_callback(current_msg)
                    
                    print(f"Clicking on {business_name}")
                    business.click()
                    # Use explicit wait instead of fixed sleep - wait for business details pane to load
                    try:
                        wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'AeaXub')]//div[contains(@class, 'Io6YTe')]")))
                    except TimeoutException:
                        # If pane doesn't load, skip this business
                        print(f"Pane did not load for {business_name}, skipping...")
                        continue

                    # Scrape address
                    address = self._get_address()

                    # Scrape phone number
                    phone = self._get_phone_number()

                    # Only add to results if phone number is found (not 'N/A' or empty)
                    if phone and phone != 'N/A' and phone.strip():
                        # Scrape website
                        website = self._get_element_attribute("//a[@aria-label and contains(@aria-label, 'Website')]", 'href')

                        results.append({'Name': business_name, 'Address': address, 'Phone': phone, 'Website': website})
                        print(f"Scraped: {business_name}, {address}, {phone}, {website}")
                    else:
                        print(f"Skipped {business_name}: No mobile phone number found")

                    # Go back to the list
                    self.driver.execute_script("window.history.go(-1)")
                    # Use explicit wait instead of fixed sleep - wait for list to reload
                    try:
                        wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'a.hfpxzc')))
                        # Re-locate businesses after coming back
                        businesses = self.driver.find_elements(By.CSS_SELECTOR, 'a.hfpxzc')
                    except TimeoutException:
                        print("List did not reload, breaking...")
                        break

                except StaleElementReferenceException:
                    print(f"Stale element reference error encountered. Retrying...")
                    continue  # Continue to the next business

                except Exception as e:
                    print(f"Error: {e}")
                    continue

            # Scroll down to load more results
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            # Reduced wait time - new results usually load quickly
            time.sleep(2)  # Reduced from 5 to 2 seconds

        if progress_callback:
            progress_callback(f"Scraping completed! Found {len(results)} results.")
        
        self.driver.quit()
        return self._create_csv_string(results)

    def _scrape_single_business_page(self):
        """Scrape business data when only one business is listed."""
        try:
            # Scrape business details
            business_name = self._get_element_text("//h1[@class='DUwDvf lfPIob']")
            address = self._get_address()
            phone = self._get_phone_number()
            
            # Only return result if phone number is found (not 'N/A' or empty)
            if phone and phone != 'N/A' and phone.strip():
                website = self._get_element_attribute("//a[@aria-label and contains(@aria-label, 'Website')]", 'href')

                # Store the result in CSV format
                result = [{'Name': business_name, 'Address': address, 'Phone': phone, 'Website': website}]
                print(f"Scraped data: Name: {business_name} | address: {address} | phone: {phone} | website: {website}")
                return self._create_csv_string(result)
            else:
                print(f"Skipped {business_name}: No mobile phone number found")
                # Return empty CSV
                return self._create_csv_string([])  

        except Exception as e:
            print(f"Error scraping business page: {e}")

    def _get_element_text(self, xpath):
        try:
            return self.driver.find_element(By.XPATH, xpath).text
        except NoSuchElementException:
            return 'N/A'

    def _get_element_attribute(self, xpath, attribute):
        try:
            return self.driver.find_element(By.XPATH, xpath).get_attribute(attribute)
        except NoSuchElementException:
            return 'N/A'

    def _get_address(self):
        """Extract address from Google Maps business page."""
        # Try to get all Io6YTe elements and find the one that looks like an address
        try:
            all_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'AeaXub')]//div[contains(@class, 'Io6YTe')]")
            for element in all_elements:
                text = element.text.strip()
                # If it looks like an address, return it
                if self._looks_like_address(text) or (text and not self._is_valid_phone(text)):
                    return text
            
            # If no address-like element found, return the first one
            if all_elements:
                return all_elements[0].text.strip()
        except NoSuchElementException:
            pass
        
        # Fallback to original selector
        return self._get_element_text("//div[contains(@class, 'AeaXub')]//div[contains(@class, 'Io6YTe')]")

    def _get_phone_number(self):
        """Extract mobile phone number from Google Maps business page."""
        # First, try specific phone number selectors (buttons/links with Phone aria-label)
        phone_selectors = [
            "//button[contains(@aria-label, 'Phone')]",
            "//a[contains(@aria-label, 'Phone')]",
            "//span[contains(@aria-label, 'Phone')]",
            "//a[contains(@href, 'tel:')]",
            "//button[contains(@data-value, '+')]",
        ]
        
        for selector in phone_selectors:
            try:
                element = self.driver.find_element(By.XPATH, selector)
                # Try to get href attribute if it's a link
                href = element.get_attribute('href')
                if href and 'tel:' in href:
                    phone = href.replace('tel:', '').strip()
                    if self._is_mobile_phone(phone):
                        return phone
                
                # Try to get text
                phone_text = element.text.strip()
                if phone_text and self._is_mobile_phone(phone_text):
                    return phone_text
                
                # Try data-value attribute
                data_value = element.get_attribute('data-value')
                if data_value and self._is_mobile_phone(data_value):
                    return data_value.strip()
            except NoSuchElementException:
                continue
        
        # If specific selectors fail, try to find phone in Io6YTe elements
        # but filter out addresses by checking if it looks like a mobile phone number
        try:
            all_elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'Io6YTe')]")
            for element in all_elements:
                text = element.text.strip()
                # Check if it's a mobile phone number (contains digits and phone-like characters, but not address-like)
                if self._is_mobile_phone(text) and not self._looks_like_address(text):
                    return text
        except NoSuchElementException:
            pass
        
        return 'N/A'
    
    def _is_valid_phone(self, text):
        """Check if text looks like a phone number."""
        if not text or len(text) < 7:
            return False
        
        # Remove common phone formatting characters
        cleaned = re.sub(r'[\s\-\(\)\+]', '', text)
        
        # Check if it contains mostly digits
        digit_count = sum(c.isdigit() for c in cleaned)
        if digit_count < 7:  # Minimum 7 digits for a phone number
            return False
        
        # Check if it has phone-like patterns
        has_plus = '+' in text
        has_parentheses = '(' in text and ')' in text
        has_digits = any(c.isdigit() for c in text)
        
        # Should have digits and phone-like formatting
        return has_digits and (has_plus or has_parentheses or (digit_count >= 7 and digit_count <= 15))
    
    def _is_mobile_phone(self, text):
        """Check if text is a mobile phone number (Turkey format: 05XX or +90 5XX)."""
        if not text:
            return False
        
        # Remove common formatting characters
        cleaned = re.sub(r'[\s\-\(\)]', '', text)
        
        # Remove +90 or 0090 prefix if present
        if cleaned.startswith('+90'):
            cleaned = cleaned[3:]
        elif cleaned.startswith('0090'):
            cleaned = cleaned[4:]
        elif cleaned.startswith('90') and len(cleaned) > 10:
            cleaned = cleaned[2:]
        
        # Check if it starts with 05 (Turkey mobile prefix)
        if cleaned.startswith('05'):
            # Should be 10 digits (05XX XXX XX XX)
            digits_only = re.sub(r'[^\d]', '', cleaned)
            if len(digits_only) == 10 and digits_only.startswith('05'):
                # Check if second digit is 0-9 (05X)
                if len(digits_only) >= 3 and digits_only[2] in '0123456789':
                    return True
        
        # Also check international format +90 5XX
        if text.startswith('+90') or text.startswith('0090'):
            # Extract the part after country code
            after_country = cleaned
            if '+' in text:
                parts = text.split('+90')
                if len(parts) > 1:
                    after_country = re.sub(r'[\s\-\(\)]', '', parts[1])
            
            # Check if it starts with 5 and has 10 digits total
            digits_only = re.sub(r'[^\d]', '', after_country)
            if len(digits_only) == 10 and digits_only.startswith('5'):
                return True
        
        return False
    
    def _looks_like_address(self, text):
        """Check if text looks like an address rather than a phone number."""
        if not text:
            return False
        
        # Address indicators
        address_keywords = ['cad', 'sok', 'mah', 'no:', 'no ', 'apt', 'daire', 'kat', 'blok', 
                           'street', 'avenue', 'road', 'boulevard', 'lane', 'drive', 'way',
                           'cd.', 'cd ', 'sk.', 'sk ', 'mh.', 'mh ']
        
        text_lower = text.lower()
        # Check for address keywords
        if any(keyword in text_lower for keyword in address_keywords):
            return True
        
        # Check for postal code patterns (usually 5 digits at the end)
        if re.search(r'\d{5}', text):
            # If it has postal code and address keywords, it's likely an address
            return True
        
        # If it contains "W98M+J3" like format (Google Maps Plus Code), it's an address
        if re.search(r'[A-Z0-9]+\+[A-Z0-9]+', text):
            return True
        
        return False

    def _create_csv_string(self, results):
        df = pd.DataFrame(results)
        output = StringIO()
        df.to_csv(output, index=False)
        return output.getvalue()
