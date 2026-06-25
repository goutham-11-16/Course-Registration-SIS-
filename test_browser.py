import os
import sys
import time
from browser import RegistrationBrowser
from config import logger

def run_local_mock_test():
    """Tests the browser parsing and injection logic using the local HTML file."""
    logger.info("Starting local mock test...")
    browser = RegistrationBrowser()
    
    try:
        driver = browser.initialize_driver()
        
        # Get absolute path to the local HTML file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        local_html_path = os.path.join(current_dir, "Course Registration - KARE.html")
        file_url = f"file:///{local_html_path.replace(chr(92), '/')}"
        
        logger.info(f"Loading local HTML file: {file_url}")
        try:
            driver.get(file_url)
        except Exception as e:
            logger.warning(f"Local file load navigation timed out (probably waiting for external css/js), continuing: {e}")
        
        # 1. Parse categories & options
        logger.info("Scraping course options from the local page...")
        select_elements = driver.find_elements("name", "courses[]")
        if not select_elements:
            logger.error("No course select elements found! HTML structure might have changed.")
            return False
            
        logger.success(f"Found {len(select_elements)} select dropdown(s).")
        
        categories = []
        for index, select in enumerate(select_elements):
            try:
                tr = select.find_element("xpath", "./ancestor::tr")
                tds = tr.find_elements("tag name", "td")
                category_name = tds[1].text.strip() if len(tds) > 1 else f"Category {index + 1}"
                category_type = tds[2].text.strip() if len(tds) > 2 else "Unknown"
                category_credits = tds[3].text.strip() if len(tds) > 3 else "0.0"
                full_name = f"{category_name} ({category_type}, {category_credits} Credits)"
            except Exception as e:
                logger.warning(f"Could not parse row text: {e}")
                full_name = f"Category {index + 1}"

            options = []
            option_elements = select.find_elements("tag name", "option")
            for opt in option_elements:
                val = opt.get_attribute("value")
                text = opt.text.strip()
                if val and text and "select" not in text.lower():
                    options.append({"value": val, "text": text})
            
            logger.info(f"Category: '{full_name}' has {len(options)} options:")
            for opt in options[:3]: # print first 3 options
                logger.info(f"  - Value: {opt['value']} -> {opt['text']}")
            if len(options) > 3:
                logger.info(f"  - ... and {len(options) - 3} more options")

            categories.append({
                "index": index,
                "name": full_name,
                "options": options
            })

        # 2. Inject selections
        logger.info("Simulating injection of selection...")
        # Let's select "24951" - 213CHE1119 - Fine Chemical Technology
        target_value = "24951"
        test_selections = {0: target_value}
        
        # Inject selection
        from selenium.webdriver.support.ui import Select
        for idx, select_el in enumerate(select_elements):
            val = test_selections.get(idx)
            if val:
                select_obj = Select(select_el)
                select_obj.select_by_value(val)
                logger.info(f"Successfully selected value '{val}' in dropdown {idx}.")

        # Take debug screenshot
        screenshot_path = browser.save_debug_screenshot("mock_test_injected")
        logger.success(f"Local test successful! Screenshot saved at: {screenshot_path}")
        
        # 3. Simulate submit
        logger.info("Attempting to click submit...")
        submit_btn = driver.find_element("css selector", "input[type='submit']")
        logger.info(f"Found submit button with value: '{submit_btn.get_attribute('value')}'")
        
        # We won't click it during local test since it will redirect to live server
        # but we successfully located it.
        logger.success("Submit button located successfully.")
        return True

    except Exception as e:
        logger.error(f"Local mock test failed: {e}")
        return False
    finally:
        browser.close_driver()

def run_live_login_test():
    """Attempts to log in to the actual portal using credentials in .env."""
    from config import PORTAL_USERNAME, PORTAL_PASSWORD
    logger.info("Starting live login test...")
    browser = RegistrationBrowser()
    try:
        success = browser.login(PORTAL_USERNAME, PORTAL_PASSWORD)
        if success:
            logger.success("Live login test PASSED!")
            
            # Check registration page
            logger.info("Checking registration page on live portal...")
            res = browser.check_registration_live()
            if res is None:
                logger.info("Registration page is not live (which is expected unless registration is active).")
            else:
                logger.success("REGISTRATION PAGE IS LIVE ON THE PORTAL!")
                logger.info(f"Scraped categories: {res}")
            return True
        else:
            logger.error("Live login test FAILED.")
            return False
    except Exception as e:
        logger.error(f"Live login test encountered an error: {e}")
        return False
    finally:
        browser.close_driver()

if __name__ == "__main__":
    print("--- COURSE REGISTRATION BOT - BROWSER MODULE TEST ---")
    
    choice = None
    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        if arg in ("1", "--mock", "mock"):
            choice = "1"
        elif arg in ("2", "--live", "live"):
            choice = "2"
            
    if not choice:
        print("1. Run Local Mock Page Test (Verifies HTML parsing and dropdown injection)")
        print("2. Run Live Login Test (Verifies credentials, selenium stealth, and connectivity)")
        try:
            choice = input("Enter choice (1 or 2): ").strip()
        except (KeyboardInterrupt, EOFError):
            choice = "1" # Default to mock test if input fails

    if choice == "1":
        run_local_mock_test()
    elif choice == "2":
        run_live_login_test()
    else:
        print("Invalid choice.")

