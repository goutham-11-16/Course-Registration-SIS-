import os
import time
from typing import List, Dict, Any, Optional
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException
from selenium_stealth import stealth
from config import logger, URL_LOGIN, URL_REGISTRATION, PORTAL_USERNAME, PORTAL_PASSWORD, HEADLESS, CHROME_DRIVER_PATH

class SiteUnreachableException(Exception):
    """Exception raised when the target site cannot be reached (e.g., DNS error, connection refused, timeout)."""
    pass

class RegistrationBrowser:
    def __init__(self):
        self.driver: Optional[webdriver.Chrome] = None
        self.wait: Optional[WebDriverWait] = None
        self.username: Optional[str] = None
        self.password: Optional[str] = None
        self.last_check_had_error = False
        self.last_error_type: Optional[str] = None
        self.last_registration_screenshot = ""

    def initialize_driver(self) -> webdriver.Chrome:
        """Initializes a Chrome WebDriver with stealth configurations and timeouts."""
        logger.info("Initializing Selenium WebDriver...")
        options = Options()
        
        # Use eager page load strategy to ignore slow stylesheet/image subresources
        options.page_load_strategy = 'eager'
        
        # Block images to save bandwidth and speed up loading
        options.add_experimental_option("prefs", {
            "profile.managed_default_content_settings.images": 2
        })
        
        if HEADLESS:
            logger.info("Running Chrome in HEADLESS mode.")
            options.add_argument("--headless")
            options.add_argument("--disable-gpu")
            options.add_argument("--window-size=1920,1080")
        else:
            logger.info("Running Chrome in WINDOWED mode.")
            options.add_argument("--start-maximized")
            
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        
        # Initialize Chrome service and driver using the pre-cached binary path
        service = Service(CHROME_DRIVER_PATH)
        driver = webdriver.Chrome(service=service, options=options)
        
        # Configure page load timeouts (30s) to prevent thread hanging on 502 gateway loops
        driver.set_page_load_timeout(30)
        driver.set_script_timeout(30)
        
        # Apply Selenium Stealth
        stealth(
            driver,
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32",
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True
        )
        
        self.driver = driver
        self.wait = WebDriverWait(driver, 15)
        return driver

    def is_session_alive(self) -> bool:
        """Checks if the browser window is open and responsive."""
        if not self.driver:
            return False
        try:
            # Accessing title forces communication with the driver
            _ = self.driver.title
            return True
        except WebDriverException:
            logger.warning("Browser session is dead or closed.")
            return False

    def close_driver(self):
        """Quits the browser and clean up driver instance."""
        if self.driver:
            logger.info("Closing browser session...")
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error closing driver: {e}")
            self.driver = None
            self.wait = None

    def save_debug_screenshot(self, name: str) -> str:
        """Saves a debug screenshot and returns the file path."""
        if not self.driver:
            return ""
        os.makedirs("screenshots", exist_ok=True)
        filename = f"screenshots/{int(time.time())}_{name}.png"
        try:
            # Check if driver is responsive
            _ = self.driver.current_url
            self.driver.save_screenshot(filename)
            logger.debug(f"Saved screenshot: {filename}")
            return filename
        except Exception:
            # Silently catch exceptions since this happens if the user cancelled the monitoring task
            # and closed the browser while a background thread was checking the page
            return ""

    def check_gateway_error(self) -> bool:
        """Detects 502/504 gateway or proxy errors on the current page."""
        if not self.driver:
            return True
        try:
            body_text = self.driver.find_element(By.TAG_NAME, "body").text
            title = self.driver.title
            for err in ["502", "504", "gateway", "proxy", "server error", "time-out", "bad gateway"]:
                if err in body_text.lower() or err in title.lower():
                    logger.warning(f"Detected potential gateway error: Title='{title}', Body contains target keywords.")
                    return True
            return False
        except Exception as e:
            logger.error(f"Error checking gateway errors: {e}")
            return True

    def is_chrome_error_page(self) -> bool:
        """Checks if the browser currently displays a Chrome error page or blank page."""
        if not self.driver:
            return True
        try:
            url = self.driver.current_url
            if url.startswith("chrome-error://") or url == "about:blank":
                return True
            
            title = self.driver.title.lower()
            if any(err in title for err in ["site can't be reached", "not available", "error", "problem loading page"]):
                return True
                
            body_text = self.driver.find_element(By.TAG_NAME, "body").text.lower()
            if any(err in body_text for err in ["err_connection_", "err_name_not_resolved", "site can't be reached", "server ip address could not be found"]):
                return True
                
            return False
        except Exception:
            return True

    def is_site_unreachable_error(self, e: Exception) -> bool:
        """Determines if the exception indicates the site was not reached."""
        err_msg = str(e).lower()
        unreachable_keywords = [
            "timeout", "time out", "not reached", "unreachable", "refused", 
            "dns", "name_not_resolved", "connection_refused", "connection_reset",
            "connection timed out", "net::err", "reached error page"
        ]
        return any(kw in err_msg for kw in unreachable_keywords)

    def login(self, username: Optional[str] = None, password: Optional[str] = None) -> bool:
        """Logs into the portal with exponential backoff on server errors."""
        if username:
            self.username = username
        if password:
            self.password = password
            
        user_to_use = self.username
        pass_to_use = self.password
        
        if not user_to_use or not pass_to_use:
            logger.error("Login aborted: Username or Password not provided in browser session.")
            return False
            
        wait_time = 2.0
        max_wait = 30.0
        
        while True:
            try:
                if not self.is_session_alive():
                    self.initialize_driver()
                
                logger.info(f"Navigating to login page: {URL_LOGIN}")
                self.driver.get(URL_LOGIN)
                
                if self.is_chrome_error_page():
                    raise SiteUnreachableException("Site could not be reached (Chrome error page detected)")
                
                if self.check_gateway_error():
                    raise Exception("Gateway Error on login page")
 
                logger.info("Entering login credentials...")
                user_field = self.wait.until(EC.visibility_of_element_located((By.NAME, "register_no")))
                user_field.clear()
                user_field.send_keys(user_to_use)
                
                pass_field = self.driver.find_element(By.NAME, "password")
                pass_field.clear()
                pass_field.send_keys(pass_to_use)
                
                logger.info("Clicking Submit button...")
                self.driver.find_element(By.CSS_SELECTOR, "button[type='submit']").click()
                
                # Wait for login URL to change (login redirects to dashboard)
                self.wait.until(EC.url_changes(URL_LOGIN))
                
                current_url = self.driver.current_url
                logger.success(f"Login successful! Current URL: {current_url}")
                self.save_debug_screenshot("login_success")
                return True

            except Exception as e:
                if isinstance(e, SiteUnreachableException) or self.is_site_unreachable_error(e):
                    self.last_error_type = "unreachable"
                else:
                    self.last_error_type = "other"
                logger.error(f"Login attempt failed: {e}. Retrying in {wait_time}s...")
                self.save_debug_screenshot("login_failure")
                if self.driver:
                    try:
                        self.driver.delete_all_cookies()
                    except Exception:
                        pass
                    # If browser is crashed, close it so a clean one opens on next iteration
                    if "chrome not reachable" in str(e).lower() or "session" in str(e).lower():
                        self.close_driver()
                
                time.sleep(wait_time)
                wait_time = min(wait_time * 1.5, max_wait)

    def check_registration_live(self) -> Optional[List[Dict[str, Any]]]:
        """
        Navigates to the registration page and checks if it's active.
        If live, parses the course categories and options and returns them.
        If not live, returns None.
        """
        self.last_check_had_error = False
        self.last_error_type = None
        try:
            if not self.is_session_alive():
                logger.warning("Browser session was lost before checking registration. Re-logging in...")
                if not self.login():
                    self.last_check_had_error = True
                    self.last_error_type = "unreachable"
                    return None

            logger.info(f"Checking registration page: {URL_REGISTRATION}")
            self.driver.get(URL_REGISTRATION)
            
            # Wait for body tag to ensure basic page load
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            if self.is_chrome_error_page():
                raise SiteUnreachableException("Site could not be reached (Chrome error page detected)")
            
            if self.check_gateway_error():
                logger.warning("Gateway error on registration page. Registration not available yet.")
                self.last_check_had_error = True
                self.last_error_type = "502_504"
                self.save_debug_screenshot("gateway_error")
                return None
                
            # If redirected to login, login session expired
            if "login" in self.driver.current_url:
                logger.warning("Session expired, redirected to login page. Re-logging in...")
                if self.login():
                    # Retry checking registration page
                    return self.check_registration_live()
                self.last_check_had_error = True
                self.last_error_type = "unreachable"
                return None

            # Find all course dropdowns (name="courses[]")
            select_elements = self.driver.find_elements(By.NAME, "courses[]")
            if not select_elements:
                logger.info("No course select elements found. Registration is not live yet.")
                return None

            logger.success(f"Registration is LIVE! Found {len(select_elements)} course category dropdowns.")
            self.last_registration_screenshot = self.save_debug_screenshot("registration_live")
            
            # Scrape categories and options
            categories = []
            for index, select in enumerate(select_elements):
                # Try to extract the Category Name from the table row
                try:
                    # Traverses up to the parent tr to find the category title column
                    tr = select.find_element(By.XPATH, "./ancestor::tr")
                    tds = tr.find_elements(By.TAG_NAME, "td")
                    # In KARE registration table: td[0] is S.No, td[1] is Category, td[2] is Theory/Practical, td[3] is Credits, td[4] is select option
                    category_name = tds[1].text.strip() if len(tds) > 1 else f"Category {index + 1}"
                    category_type = tds[2].text.strip() if len(tds) > 2 else "Unknown"
                    category_credits = tds[3].text.strip() if len(tds) > 3 else "0.0"
                    
                    full_name = f"{category_name} ({category_type}, {category_credits} Credits)"
                except Exception as e:
                    logger.warning(f"Could not parse row text: {e}")
                    full_name = f"Category {index + 1}"

                options = []
                option_elements = select.find_elements(By.TAG_NAME, "option")
                for opt in option_elements:
                    val = opt.get_attribute("value")
                    text = opt.text.strip()
                    # Skip empty/placeholder options
                    if val and text and "select" not in text.lower():
                        options.append({"value": val, "text": text})

                categories.append({
                    "index": index,
                    "name": full_name,
                    "options": options
                })
            
            return categories

        except Exception as e:
            logger.error(f"Error checking registration page: {e}")
            self.last_check_had_error = True
            if isinstance(e, SiteUnreachableException) or self.is_site_unreachable_error(e):
                self.last_error_type = "unreachable"
            else:
                self.last_error_type = "other"
            self.save_debug_screenshot("reg_check_error")
            return None

    def inject_selections_and_submit(self, selections: Dict[int, str]) -> str:
        """
        Injects the selected course values into the dropdown forms, clicks submit,
        and waits for the confirmation page.
        Returns the path to the confirmation page screenshot.
        """
        try:
            if not self.is_session_alive():
                raise Exception("Browser session died before selections could be injected.")
                
            logger.info(f"Injecting selections: {selections}")
            select_elements = self.driver.find_elements(By.NAME, "courses[]")
            
            if not select_elements:
                raise Exception("No course select elements found to inject selections into.")
                
            for idx, select_el in enumerate(select_elements):
                # selections can be keyed by int or stringified int
                val = selections.get(idx) or selections.get(str(idx))
                if val:
                    logger.info(f"Selecting option '{val}' for category index {idx}")
                    select_obj = Select(select_el)
                    select_obj.select_by_value(val)
                else:
                    logger.warning(f"No selection provided for category index {idx}")
                    
            self.save_debug_screenshot("before_submit")
            
            # Find the submit button on the registration form
            # Based on the HTML: <input type='submit' class='btn btn-primary' value='Submit'>
            submit_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='submit'], button[type='submit']")))
            logger.info("Clicking initial Submit button...")
            submit_btn.click()
            
            # Wait for registration confirmation page
            logger.info("Waiting for redirect to registration confirmation page...")
            self.wait.until(EC.url_contains("registration_confirm"))
            
            # Explicitly wait for the final submit button on the confirmation page
            logger.info("Waiting for final confirmation button to be present...")
            confirm_btn = self.wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
            ))
            
            logger.success("Registration confirmation page loaded.")
            screenshot_path = self.save_debug_screenshot("confirm_page")
            return screenshot_path
            
        except Exception as e:
            logger.error(f"Error injecting selections/submitting: {e}")
            screenshot_path = self.save_debug_screenshot("injection_error")
            raise e

    def finalize_registration(self) -> str:
        """
        Clicks the final submit button on the confirmation page to submit the registration.
        Returns the path to the success screenshot.
        """
        try:
            if not self.is_session_alive():
                raise Exception("Browser session died before final submission.")
                
            confirm_btn = self.wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
            ))
            
            logger.info("Clicking final Confirm & Submit button...")
            confirm_btn.click()
            
            # Wait for page to reload/submit (typically takes a couple seconds)
            time.sleep(3)
            
            logger.success("Final registration submitted successfully!")
            screenshot_path = self.save_debug_screenshot("registration_success")
            return screenshot_path
            
        except Exception as e:
            logger.error(f"Error finalizing registration: {e}")
            screenshot_path = self.save_debug_screenshot("final_submit_error")
            raise e
