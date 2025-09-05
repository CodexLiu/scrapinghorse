import undetected_chromedriver as uc
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
import time
import os
import tempfile
import shutil
import json
import subprocess
import math
from .ai_mode_parser import extract_structured_from_html

# Configuration constants
START_URL = "https://www.google.com/search?udm=50&q="
ENABLE_USAGE_ESTIMATE = os.getenv('ENABLE_USAGE_ESTIMATE', '0') == '1'

def _get_screen_size_macos() -> tuple[int, int]:
    """Get screen dimensions on macOS using AppleScript."""
    try:
        result = subprocess.check_output([
            "osascript", "-e",
            'tell application "Finder" to get bounds of window of desktop'
        ], text=True).strip()
        # Parse result like "0, 0, 1920, 1080"
        parts = [int(p.strip()) for p in result.replace(",", " ").split()]
        width = parts[2] - parts[0]
        height = parts[3] - parts[1]
        return width, height
    except Exception:
        # Fallback to reasonable default
        return 1440, 900

def _compute_grid(workers: int) -> tuple[int, int]:
    """Compute grid dimensions for given number of workers."""
    workers = max(1, workers)
    cols = int(math.ceil(math.sqrt(workers)))
    rows = int(math.ceil(workers / cols))
    return cols, rows

def _slot_to_position(workers: int, slot: int, margin: int) -> tuple[int, int]:
    """Convert slot number to x,y position on screen."""
    screen_width, screen_height = _get_screen_size_macos()
    cols, rows = _compute_grid(workers)
    
    # Calculate position within grid
    col = slot % cols
    row = slot // cols
    
    # Calculate window position (not changing size, just position)
    x = margin + col * ((screen_width - (cols + 1) * margin) // cols + margin)
    y = margin + row * ((screen_height - (rows + 1) * margin) // rows + margin)
    
    return x, y

def _allocate_slot(workers: int) -> int:
    """Allocate a unique window slot for this process."""
    cols, rows = _compute_grid(workers)
    total_slots = cols * rows
    
    # Try to claim a slot using lock files
    for slot in range(total_slots):
        try:
            # Try to create lock file atomically
            lock_path = f".window_slots/slot_{slot}"
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return slot
        except FileExistsError:
            continue
        except Exception:
            continue
    
    # If all slots taken, use process ID as fallback
    return os.getpid() % total_slots

def _prepare_oxylabs_extension():
    """Prepare Oxylabs proxy extension with credentials from environment variables."""
    username = os.getenv('OXYLABS_USERNAME')
    password = os.getenv('OXYLABS_PASSWORD')
    
    if not username or not password:
        return None
    
    # Build full username with US country targeting
    username_full = f"customer-{username}-cc-US"
    
    # Get proxy settings from env or use defaults
    proxy_host = os.getenv('OXYLABS_PROXY_HOST', 'pr.oxylabs.io')
    proxy_port = os.getenv('OXYLABS_PROXY_PORT', '7777')
    
    try:
        # Create temp directory for extension
        temp_dir = tempfile.mkdtemp(prefix='oxylabs_ext_')
        
        # Copy extension files to temp directory
        extension_source = os.path.join(os.path.dirname(__file__), '..', '..', 'scripts', 'oxylabs_proxy_extension')
        if os.path.exists(extension_source):
            shutil.copytree(extension_source, temp_dir, dirs_exist_ok=True)
        else:
            # If source doesn't exist, create minimal files
            manifest = {
                "manifest_version": 3,
                "name": "Oxylabs Proxy Extension",
                "version": "1.0",
                "permissions": ["proxy", "storage", "webRequest"],
                "host_permissions": ["<all_urls>"],
                "background": {"service_worker": "background.js"},
                "minimum_chrome_version": "96"
            }
            
            background_js = '''
chrome.runtime.onStartup.addListener(setupProxy);
chrome.runtime.onInstalled.addListener(setupProxy);

async function setupProxy() {
  try {
    const response = await fetch(chrome.runtime.getURL('config.json'));
    const config = await response.json();
    
    const proxyConfig = {
      value: {
        mode: "fixed_servers",
        rules: {
          singleProxy: {
            scheme: config.protocol || "http",
            host: config.host,
            port: parseInt(config.port)
          }
        }
      },
      scope: "regular"
    };
    
    await chrome.proxy.settings.set(proxyConfig);
    console.log('Oxylabs proxy configured:', config.host + ':' + config.port);
    
  } catch (error) {
    console.error('Failed to setup proxy:', error);
  }
}

chrome.webRequest.onAuthRequired.addListener(
  function(details) {
    return new Promise(async (resolve) => {
      try {
        const response = await fetch(chrome.runtime.getURL('config.json'));
        const config = await response.json();
        
        resolve({
          authCredentials: {
            username: config.username_full,
            password: config.password
          }
        });
      } catch (error) {
        console.error('Auth failed:', error);
        resolve({});
      }
    });
  },
  { urls: ["<all_urls>"] },
  ["blocking"]
);

setupProxy();
            '''
            
            with open(os.path.join(temp_dir, 'manifest.json'), 'w') as f:
                json.dump(manifest, f, indent=2)
            
            with open(os.path.join(temp_dir, 'background.js'), 'w') as f:
                f.write(background_js)
        
        # Create config.json with proxy credentials
        config = {
            "host": proxy_host,
            "port": proxy_port,
            "username_full": username_full,
            "password": password,
            "protocol": "http"
        }
        
        with open(os.path.join(temp_dir, 'config.json'), 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"✅ Oxylabs proxy extension prepared: {username_full}@{proxy_host}:{proxy_port}")
        return temp_dir
        
    except Exception as e:
        print(f"❌ Failed to prepare Oxylabs extension: {e}")
        return None

def _build_options(binary_path: str = None) -> uc.ChromeOptions:
    """Build fresh Chrome options to avoid reuse errors."""
    options = uc.ChromeOptions()
    
    # Configure Oxylabs proxy extension if credentials are available
    extension_path = _prepare_oxylabs_extension()
    if extension_path:
        options.add_argument(f'--load-extension={extension_path}')
        print("🔄 Oxylabs proxy extension loaded")
    
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
    
    # Position window in grid layout
    try:
        workers = int(os.getenv("WORKERS", "1"))
        margin = int(os.getenv("WINDOW_MARGIN", "20"))
        slot = _allocate_slot(workers)
        x, y = _slot_to_position(workers, slot, margin)
        driver.set_window_position(x, y)
        print(f"Chrome window positioned at slot {slot}: ({x}, {y})")
    except Exception as e:
        print(f"Warning: Could not position window: {e}")
    
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
