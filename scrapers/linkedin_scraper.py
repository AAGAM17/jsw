import logging
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from config.settings import Config

class LinkedInScraper:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.driver = None
        
    def _init_driver(self):
        """Initialize Chrome driver with necessary options"""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # Run in headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920x1080')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(10)
        
    def _login(self):
        """Login to LinkedIn"""
        try:
            self.driver.get('https://www.linkedin.com/login')
            
            # Wait for login form
            email_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.ID, "username"))
            )
            password_field = self.driver.find_element(By.ID, "password")
            
            # Enter credentials
            email_field.send_keys(Config.LINKEDIN_EMAIL)
            password_field.send_keys(Config.LINKEDIN_PASSWORD)
            password_field.send_keys(Keys.RETURN)
            
            # Wait for login to complete
            time.sleep(5)
            
            return True
            
        except Exception as e:
            self.logger.error(f"LinkedIn login failed: {str(e)}")
            return False
            
    def search_company_employees(self, company_name, roles=None):
        """Search for employees at a company with specific roles"""
        try:
            if not self.driver:
                self._init_driver()
                if not self._login():
                    return []
            
            # Build search query
            search_query = f'"{company_name}"'
            if roles:
                role_query = ' OR '.join(f'"{role}"' for role in roles)
                search_query = f'{search_query} ({role_query})'
            
            # Navigate to search
            search_url = f'https://www.linkedin.com/search/results/people/?keywords={search_query}&origin=GLOBAL_SEARCH_HEADER'
            self.driver.get(search_url)
            
            # Wait for results
            time.sleep(3)
            
            # Extract results
            results = []
            for _ in range(2):  # Get first 2 pages
                try:
                    # Find all profile cards
                    profile_cards = self.driver.find_elements(By.CLASS_NAME, "reusable-search__result-container")
                    
                    for card in profile_cards:
                        try:
                            name = card.find_element(By.CLASS_NAME, "entity-result__title-text").text.strip()
                            title = card.find_element(By.CLASS_NAME, "entity-result__primary-subtitle").text.strip()
                            profile_url = card.find_element(By.CLASS_NAME, "app-aware-link").get_attribute("href")
                            
                            results.append({
                                'name': name,
                                'title': title,
                                'profile_url': profile_url.split('?')[0]  # Remove URL parameters
                            })
                            
                        except NoSuchElementException:
                            continue
                    
                    # Click next page if available
                    next_button = self.driver.find_element(By.CLASS_NAME, "artdeco-pagination__button--next")
                    if next_button.is_enabled():
                        next_button.click()
                        time.sleep(3)
                    else:
                        break
                        
                except Exception as e:
                    self.logger.error(f"Error extracting profiles: {str(e)}")
                    break
            
            return results
            
        except Exception as e:
            self.logger.error(f"LinkedIn search failed for {company_name}: {str(e)}")
            return []
            
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None
    
    def get_profile_details(self, profile_url):
        """Get detailed information from a LinkedIn profile"""
        try:
            if not self.driver:
                self._init_driver()
                if not self._login():
                    return None
            
            self.driver.get(profile_url)
            time.sleep(3)
            
            # Extract profile information
            profile_info = {}
            
            try:
                profile_info['name'] = self.driver.find_element(By.CLASS_NAME, "text-heading-xlarge").text.strip()
            except NoSuchElementException:
                profile_info['name'] = ""
                
            try:
                profile_info['title'] = self.driver.find_element(By.CLASS_NAME, "text-body-medium").text.strip()
            except NoSuchElementException:
                profile_info['title'] = ""
                
            try:
                profile_info['location'] = self.driver.find_element(By.CLASS_NAME, "text-body-small").text.strip()
            except NoSuchElementException:
                profile_info['location'] = ""
                
            # Get experience
            try:
                experience_section = self.driver.find_element(By.ID, "experience-section")
                experiences = experience_section.find_elements(By.CLASS_NAME, "pv-entity__summary-info")
                
                profile_info['experience'] = []
                for exp in experiences[:3]:  # Get last 3 positions
                    try:
                        title = exp.find_element(By.CLASS_NAME, "t-16").text.strip()
                        company = exp.find_element(By.CLASS_NAME, "pv-entity__secondary-title").text.strip()
                        profile_info['experience'].append({
                            'title': title,
                            'company': company
                        })
                    except NoSuchElementException:
                        continue
                        
            except NoSuchElementException:
                profile_info['experience'] = []
            
            return profile_info
            
        except Exception as e:
            self.logger.error(f"Failed to get profile details from {profile_url}: {str(e)}")
            return None
            
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None 