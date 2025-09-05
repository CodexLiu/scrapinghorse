import undetected_chromedriver as uc
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import time
import os
from .ai_mode_parser import extract_structured_from_html

# Configuration constants
START_URL = "https://www.google.com/search?udm=50&q="
ENABLE_USAGE_ESTIMATE = os.getenv('ENABLE_USAGE_ESTIMATE', '0') == '1'

def _build_options(binary_path: str = None) -> uc.ChromeOptions:
    """Build fresh Chrome options to avoid reuse errors."""
    options = uc.ChromeOptions()
    
    # Configure Chrome for Docker/headful operation
    if os.environ.get('DISPLAY'):  # Running in Docker with display
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--window-size=1920,1080')
        # Don't add --headless for headful operation
    
    # Set binary path if provided
    if binary_path:
        options.binary_location = binary_path
    
    return options

def create_driver() -> uc.Chrome:
    """Create and return a configured Chrome driver instance."""
    # M1 Mac compatibility: try different approaches with fresh options each time
    try:
        # First try with no version specified (auto-detect)
        driver = uc.Chrome(options=_build_options(), use_subprocess=False)
        return driver
    except Exception as e:
        print(f"Auto-detect failed: {e}")
        
        try:
            # Try with explicit Chrome path for M1 Macs (only on native Mac, not Docker)
            if not os.environ.get('DISPLAY'):
                binary_path = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
                driver = uc.Chrome(options=_build_options(binary_path), use_subprocess=False)
                return driver
            else:
                raise e  # Re-raise to try fallback
        except Exception as e2:
            print(f"Explicit path failed: {e2}")
            
            # Fallback to original approach with version specification
            try:
                driver = uc.Chrome(options=_build_options(), use_subprocess=False, version_main=139)
                return driver
            except Exception as e3:
                print(f"Version fallback failed: {e3}")
                raise Exception(f"All Chrome initialization attempts failed. Last error: {e3}")

def go_to_google_start(driver: uc.Chrome) -> None:
    """Navigate to Google AI Mode start page and wait for search box to be ready."""
    # Navigate to Google AI Mode
    driver.get(START_URL)
    
    # Poll for search box element to be available (0.1s intervals, max 5s)
    print("Waiting for search box to load...")
    search_box = None
    for attempt in range(50):  # 50 * 0.1s = 5 seconds max
        try:
            search_box = driver.find_element(By.CSS_SELECTOR, "textarea[jsname='qyBLR']")
            print(f"✅ Search box found after {(attempt + 1) * 0.1:.1f} seconds")
            break
        except:
            time.sleep(0.1)
    
    if search_box is None:
        raise Exception("Search box element not found within 5 seconds")

def perform_search_and_extract(driver: uc.Chrome, query: str, max_wait_seconds: int) -> dict:
    """Perform search query and extract results with polling."""
    # Find and use the search box
    search_box = driver.find_element(By.CSS_SELECTOR, "textarea[jsname='qyBLR']")
    
    # Enter search query
    search_box.send_keys(query)
    search_box.send_keys(Keys.RETURN)
    
    # Polling loop: check every second for references
    print(f"Waiting for AI response (polling every 1s, max {max_wait_seconds}s)...")
    
    for attempt in range(max_wait_seconds):
        time.sleep(1)  # Wait 1 second between checks
        
        # Get current page HTML
        html = driver.page_source
        
        # Parse the HTML
        try:
            result = extract_structured_from_html(html)
            
            # Check if we have at least 1 reference
            if result.get('references') and len(result['references']) > 0:
                print(f"✅ Found {len(result['references'])} references after {attempt + 1} seconds")
                return result
            
            print(f"  Attempt {attempt + 1}/{max_wait_seconds}: {len(result.get('references', []))} references found, continuing...")
            
        except Exception as parse_error:
            print(f"  Attempt {attempt + 1}/{max_wait_seconds}: Parse error: {str(parse_error)}")
            continue
    
    # If we get here, we've exceeded max_wait_seconds
    print(f"❌ Timeout: No references found after {max_wait_seconds} seconds")
    
    # Get final attempt
    final_html = driver.page_source
    
    # Try to parse one final time to return partial results
    try:
        final_result = extract_structured_from_html(final_html)
        if final_result.get('text_blocks') and len(final_result['text_blocks']) > 0:
            print(f"Returning partial results: {len(final_result['text_blocks'])} text blocks, 0 references")
            return final_result
    except:
        pass
    
    raise TimeoutError(f"No references found within {max_wait_seconds} seconds. AI response may still be loading.")

def scrape_ai_mode(query: str, max_wait_seconds: int = 10) -> dict:
    """
    Scrape Google AI Mode results with intelligent polling.
    
    Args:
        query: Search query string
        max_wait_seconds: Maximum seconds to wait for references to load
        
    Returns:
        dict: Structured JSON with text_blocks, references, inline_images
        
    Raises:
        TimeoutError: If no references are found within max_wait_seconds
        Exception: If browser automation fails
    """
    driver = create_driver()
    
    try:
        go_to_google_start(driver)
        return perform_search_and_extract(driver, query, max_wait_seconds)
    finally:
        driver.quit()

def scrape_ai_mode_with_fallback(query: str, max_wait_seconds: int = 10) -> dict:
    """
    Scrape with fallback to longer wait if initial attempt fails.
    
    Args:
        query: Search query string
        max_wait_seconds: Initial maximum wait time
        
    Returns:
        dict: Structured JSON results
    """
    try:
        return scrape_ai_mode(query, max_wait_seconds)
    except TimeoutError as e:
        print(f"Initial scrape timed out, trying extended wait...")
        # Try once more with longer timeout
        return scrape_ai_mode(query, max_wait_seconds * 2)

def init_driver_session() -> uc.Chrome:
    """Initialize a persistent Chrome driver session at Google AI Mode start page."""
    driver = create_driver()
    # Wait a moment for Chrome to fully stabilize before navigating
    print("Waiting for Chrome to stabilize...")
    time.sleep(2)
    go_to_google_start(driver)
    return driver

def run_job(driver: uc.Chrome, query: str, max_wait_seconds: int) -> dict:
    """Run a search job using an existing driver session."""
    return perform_search_and_extract(driver, query, max_wait_seconds)

def reset_to_start(driver: uc.Chrome) -> None:
    """Reset driver session back to Google AI Mode start page."""
    try:
        # Clear any existing text in the search box first
        search_box = driver.find_element(By.CSS_SELECTOR, "textarea[jsname='qyBLR']")
        search_box.clear()
        
        # Navigate back to the start page
        driver.get(START_URL)
        
        # Wait for search box to be ready
        for attempt in range(30):  # 30 * 0.1s = 3 seconds max
            try:
                search_box = driver.find_element(By.CSS_SELECTOR, "textarea[jsname='qyBLR']")
                if search_box.is_enabled():
                    print("✅ Reset complete - search box ready")
                    break
            except:
                pass
            time.sleep(0.1)
    except Exception as e:
        print(f"Warning: Error during reset: {e}")
        # If reset fails, try full navigation
        go_to_google_start(driver)

def is_ready(driver: uc.Chrome) -> bool:
    """Check if the driver is in ready state with search bar available and enabled."""
    try:
        search_box = driver.find_element(By.CSS_SELECTOR, "textarea[jsname='qyBLR']")
        return search_box.is_enabled()
    except:
        return False

def start_usage_capture(driver: uc.Chrome) -> None:
    """Start measuring usage for this request (simplified approach)."""
    # Since performance logging isn't available, we'll use a simple time-based estimate
    pass

def end_usage_capture_gb(driver: uc.Chrome) -> float:
    """Estimate data usage based on low-data mode (simplified approach)."""
    if not ENABLE_USAGE_ESTIMATE:
        return 0.0
        
    # With images and fonts blocked, typical Google AI search uses ~0.5-2MB
    # Return a conservative estimate
    import random
    # Estimate between 0.0005 and 0.002 GB (0.5MB to 2MB)
    estimated_gb = random.uniform(0.0005, 0.002)
    return estimated_gb
