from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import time
import logging
from typing import List, Dict, Optional
import json
import os
from dotenv import load_dotenv
import random
import undetected_chromedriver as uc
import requests
from datetime import datetime, timedelta
from pathlib import Path
import re

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add at the top with other imports
CACHE_DIR = Path("cache")
CACHE_DURATION = timedelta(minutes=5)  # Cache data for 5 minutes

class ScrapingError(Exception):
    pass

def setup_driver() -> webdriver.Chrome:
    """Set up and return a configured Chrome WebDriver."""
    options = uc.ChromeOptions()
    
    # Basic options
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-notifications")
    options.add_argument("--disable-popup-blocking")
    
    # Enable location services
    options.add_argument("--enable-geolocation")
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.geolocation": 1,  # 1:allow, 2:block
        "profile.default_content_settings.geolocation": 1,
        "profile.managed_default_content_settings.geolocation": 1
    })
    
    # Add realistic browser preferences
    options.add_experimental_option("prefs", {
        "profile.default_content_setting_values.notifications": 2,  # Block notifications
        "profile.default_content_settings.cookies": 1,  # Allow cookies
        "profile.default_content_settings.images": 1,  # Allow images
        "profile.default_content_settings.javascript": 1,  # Allow JavaScript
        "profile.default_content_settings.plugins": 1,  # Allow plugins
        "profile.default_content_settings.popups": 2,  # Block popups
        "profile.default_content_settings.geolocation": 1,  # Allow geolocation
        "profile.default_content_settings.media_stream": 1,  # Allow media stream
        "profile.default_content_settings.media_stream_mic": 1,  # Allow microphone
        "profile.default_content_settings.media_stream_camera": 1,  # Allow camera
        "profile.default_content_settings.protocol_handlers": 1,  # Allow protocol handlers
        "profile.default_content_settings.midi_sysex": 1,  # Allow MIDI
        "profile.default_content_settings.push_messaging": 2,  # Block push messaging
        "profile.default_content_settings.ssl_cert_decisions": 1,  # Allow SSL cert decisions
        "profile.default_content_settings.mixed_script": 1,  # Allow mixed script
        "profile.default_content_settings.media_engagement": 1,  # Allow media engagement
        "profile.default_content_settings.durable_storage": 1,  # Allow durable storage
    })
    
    # Add realistic user agent
    options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
    
    # Add language and platform info
    options.add_argument("--lang=en-US,en;q=0.9")
    options.add_argument("--platform=MacIntel")
    
    # Add security headers
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-features=IsolateOrigins,site-per-process")
    
    # Create and configure the driver
    driver = uc.Chrome(options=options)
    driver.set_window_size(1920, 1080)
    
    # Set page load timeout
    driver.set_page_load_timeout(30)
    
    return driver

def random_sleep(min_seconds: float = 1.0, max_seconds: float = 3.0):
    """Sleep for a random amount of time to simulate human behavior."""
    time.sleep(random.uniform(min_seconds, max_seconds))

def wait_for_element(driver: webdriver.Chrome, by: By, value: str, timeout: int = 10) -> Optional[webdriver.remote.webelement.WebElement]:
    """Wait for an element to be present and return it."""
    try:
        element = WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, value))
        )
        return element
    except TimeoutException:
        logger.warning(f"Timeout waiting for element: {value}")
        return None

def scroll_to_load_content(driver: webdriver.Chrome, max_scrolls: int = 5):
    """Scroll the page to load more content."""
    for _ in range(max_scrolls):
        # Scroll a random amount
        scroll_amount = random.randint(300, 700)
        driver.execute_script(f"window.scrollBy(0, {scroll_amount});")
        random_sleep(1.0, 2.0)

def handle_access_denied(driver: webdriver.Chrome, max_retries: int = 3) -> bool:
    """Handle access denied page and return True if handled successfully."""
    for attempt in range(max_retries):
        try:
            if "Access to this page has been denied" in driver.title:
                logger.warning(f"Access denied detected (attempt {attempt + 1}/{max_retries})")
                
                # Try to find and click any "I'm not a robot" or similar elements
                captcha_selectors = [
                    "//iframe[contains(@src, 'recaptcha')]",
                    "//div[contains(@class, 'captcha')]",
                    "//div[contains(text(), 'I am human')]",
                    "//button[contains(text(), 'Verify')]",
                    "//div[contains(@class, 'cf-browser-verification')]",
                    "//div[contains(@class, 'cf-verification')]",
                    "//div[contains(@class, 'cf-challenge')]"
                ]
                
                for selector in captcha_selectors:
                    try:
                        element = driver.find_element(By.XPATH, selector)
                        if element:
                            logger.info(f"Found potential CAPTCHA element: {selector}")
                            # Wait for manual intervention
                            time.sleep(30)  # Give time for manual CAPTCHA solving
                            return "Access to this page has been denied" not in driver.title
                    except NoSuchElementException:
                        continue
                
                # If we can't find a CAPTCHA, try refreshing the page
                driver.refresh()
                random_sleep(5.0, 8.0)
                
                # Try to clear cookies and cache
                driver.delete_all_cookies()
                driver.execute_script("window.localStorage.clear();")
                driver.execute_script("window.sessionStorage.clear();")
                
                return "Access to this page has been denied" not in driver.title
                
        except Exception as e:
            logger.error(f"Error handling access denied (attempt {attempt + 1}): {str(e)}")
            if attempt < max_retries - 1:
                random_sleep(5.0, 10.0)
                continue
    
    return False

def scrape_prizepicks(driver: webdriver.Chrome) -> List[Dict]:
    """
    Scrape MLB player props from PrizePicks.
    Returns a list of dictionaries containing prop information.
    """
    try:
        logger.info("Starting PrizePicks MLB scraping...")
        driver.get("https://app.prizepicks.com/")
        
        # Wait for initial load
        random_sleep(8.0, 12.0)
        
        # Debug: Print page source to understand structure
        logger.info("Page title: " + driver.title)
        
        # Handle access denied if necessary
        if not handle_access_denied(driver):
            logger.error("Could not handle access denied page")
            return []
        
        # Click on MLB section using multiple possible selectors
        mlb_selectors = [
            "//div[contains(text(), 'MLB')]",
            "//div[contains(@class, 'league') and contains(text(), 'MLB')]",
            "//div[contains(@class, 'sport') and contains(text(), 'MLB')]",
            "//a[contains(text(), 'MLB')]",
            "//div[contains(@data-test, 'MLB')]",
            "//div[contains(@class, 'league-selector')]//div[contains(text(), 'MLB')]",
            "//div[contains(@class, 'sports-league')]//div[contains(text(), 'MLB')]",
            "//div[contains(@class, 'league-tab')]//div[contains(text(), 'MLB')]"
        ]
        
        mlb_clicked = False
        for selector in mlb_selectors:
            try:
                mlb_button = wait_for_element(driver, By.XPATH, selector)
                if mlb_button:
                    # Scroll to the element
                    driver.execute_script("arguments[0].scrollIntoView(true);", mlb_button)
                    random_sleep(1.0, 2.0)
                    
                    # Try JavaScript click first
                    try:
                        driver.execute_script("arguments[0].click();", mlb_button)
                    except:
                        # Fall back to regular click
                        mlb_button.click()
                    
                    random_sleep(3.0, 5.0)
                    logger.info(f"Clicked on MLB section using selector: {selector}")
                    mlb_clicked = True
                    break
            except Exception as e:
                logger.warning(f"Failed to click MLB section with selector {selector}: {str(e)}")
        
        if not mlb_clicked:
            logger.warning("Could not find or click MLB section")
            return []
        
        # Click on Player Props tab using multiple possible selectors
        props_selectors = [
            "//div[contains(text(), 'Player Props')]",
            "//div[contains(@class, 'tab') and contains(text(), 'Player Props')]",
            "//button[contains(text(), 'Player Props')]",
            "//a[contains(text(), 'Player Props')]",
            "//div[contains(@data-test, 'player-props')]",
            "//div[contains(@class, 'tab-selector')]//div[contains(text(), 'Player Props')]",
            "//div[contains(@class, 'props-tab')]//div[contains(text(), 'Player Props')]",
            "//div[contains(@class, 'tab-content')]//div[contains(text(), 'Player Props')]"
        ]
        
        props_clicked = False
        for selector in props_selectors:
            try:
                props_button = wait_for_element(driver, By.XPATH, selector)
                if props_button:
                    # Scroll to the element
                    driver.execute_script("arguments[0].scrollIntoView(true);", props_button)
                    random_sleep(1.0, 2.0)
                    
                    # Try JavaScript click first
                    try:
                        driver.execute_script("arguments[0].click();", props_button)
                    except:
                        # Fall back to regular click
                        props_button.click()
                    
                    random_sleep(3.0, 5.0)
                    logger.info(f"Clicked on Player Props tab using selector: {selector}")
                    props_clicked = True
                    break
            except Exception as e:
                logger.warning(f"Failed to click Player Props tab with selector {selector}: {str(e)}")
        
        if not props_clicked:
            logger.warning("Could not find or click Player Props tab")
            return []
        
        # Scroll to load content
        scroll_to_load_content(driver, max_scrolls=10)
        
        # Find all player cards using multiple possible selectors
        card_selectors = [
            "[data-test='player-card']",
            "div[class*='PlayerCard']",
            "div[class*='player-card']",
            "div[class*='card']",
            "div[class*='PlayerPropsCard']",
            "div[class*='player-props-card']",
            "div[class*='player-props']",
            "div[class*='props-card']"
        ]
        
        player_cards = []
        for selector in card_selectors:
            cards = driver.find_elements(By.CSS_SELECTOR, selector)
            if cards:
                player_cards = cards
                logger.info(f"Found {len(cards)} player cards using selector: {selector}")
                break
        
        if not player_cards:
            logger.warning("No player cards found with any selector")
            return []
        
        props = []
        for card in player_cards:
            try:
                # Extract player name using multiple possible selectors
                name_selectors = [
                    "[data-test='player-name']",
                    "div[class*='PlayerName']",
                    "div[class*='player-name']",
                    "div[class*='name']",
                    "div[class*='PlayerPropsName']",
                    "div[class*='player-props-name']",
                    "div[class*='player-title']",
                    "div[class*='player-header']"
                ]
                
                player_name = None
                for selector in name_selectors:
                    try:
                        name_element = card.find_element(By.CSS_SELECTOR, selector)
                        player_name = name_element.text.strip()
                        if player_name:
                            break
                    except NoSuchElementException:
                        continue
                
                if not player_name:
                    logger.warning("Could not find player name")
                    continue
                
                # Extract stat type and line
                stat_selectors = [
                    "[data-test='stat-row']",
                    "div[class*='Stat']",
                    "div[class*='stat-row']",
                    "div[class*='stat']",
                    "div[class*='PlayerPropsStat']",
                    "div[class*='player-props-stat']",
                    "div[class*='prop-row']",
                    "div[class*='stat-line']"
                ]
                
                for stat_selector in stat_selectors:
                    stat_elements = card.find_elements(By.CSS_SELECTOR, stat_selector)
                    for stat in stat_elements:
                        try:
                            # Try different selectors for stat type
                            type_selectors = [
                                "[data-test='stat-type']",
                                "div[class*='StatType']",
                                "div[class*='stat-type']",
                                "div[class*='type']",
                                "div[class*='PlayerPropsType']",
                                "div[class*='player-props-type']",
                                "div[class*='prop-type']",
                                "div[class*='stat-name']"
                            ]
                            
                            stat_type = None
                            for type_selector in type_selectors:
                                try:
                                    type_element = stat.find_element(By.CSS_SELECTOR, type_selector)
                                    stat_type = type_element.text.strip()
                                    if stat_type:
                                        break
                                except NoSuchElementException:
                                    continue
                            
                            if not stat_type:
                                continue
                            
                            # Try different selectors for line
                            line_selectors = [
                                "[data-test='line']",
                                "div[class*='Line']",
                                "div[class*='line']",
                                "div[class*='value']",
                                "div[class*='PlayerPropsLine']",
                                "div[class*='player-props-line']",
                                "div[class*='prop-line']",
                                "div[class*='stat-value']"
                            ]
                            
                            line = None
                            for line_selector in line_selectors:
                                try:
                                    line_element = stat.find_element(By.CSS_SELECTOR, line_selector)
                                    line_text = line_element.text.strip()
                                    line = float(line_text.replace('O/U ', ''))
                                    break
                                except (NoSuchElementException, ValueError):
                                    continue
                            
                            if not line:
                                continue
                            
                            # Try different selectors for odds
                            odds_selectors = [
                                "[data-test='odds']",
                                "div[class*='Odds']",
                                "div[class*='odds']",
                                "div[class*='price']",
                                "div[class*='PlayerPropsOdds']",
                                "div[class*='player-props-odds']",
                                "div[class*='prop-odds']",
                                "div[class*='stat-odds']"
                            ]
                            
                            odds = None
                            for odds_selector in odds_selectors:
                                try:
                                    odds_element = stat.find_element(By.CSS_SELECTOR, odds_selector)
                                    odds_text = odds_element.text.strip()
                                    odds = float(odds_text.replace('+', '').replace('-', '-'))
                                    break
                                except (NoSuchElementException, ValueError):
                                    continue
                            
                            if not odds:
                                continue
                            
                            props.append({
                                "player_name": player_name,
                                "prop_type": stat_type,
                                "line": line,
                                "prizepicks_odds": odds
                            })
                            logger.info(f"Successfully scraped prop for {player_name}: {stat_type} {line} ({odds})")
                            
                        except Exception as e:
                            logger.warning(f"Error parsing stat: {str(e)}")
                            continue
                
            except Exception as e:
                logger.warning(f"Error parsing player card: {str(e)}")
                continue
        
        logger.info(f"Successfully scraped {len(props)} props from PrizePicks")
        return props
        
    except Exception as e:
        logger.error(f"Error scraping PrizePicks: {str(e)}")
        raise ScrapingError(f"Failed to scrape PrizePicks: {str(e)}")

def convert_to_american_odds(decimal_odds: float) -> float:
    """Convert decimal odds to American odds."""
    if decimal_odds >= 2.0:
        return round((decimal_odds - 1) * 100)
    else:
        return round(-100 / (decimal_odds - 1))

def scrape_pinnacle(driver: webdriver.Chrome) -> List[Dict]:
    """
    Scrape MLB player props from Pinnacle.
    Returns a list of dictionaries containing prop information.
    """
    try:
        logger.info("Starting Pinnacle MLB scraping...")
        driver.get("https://www.pinnacle.com/en/baseball/mlb/matchups/")
        
        # Wait for initial load
        random_sleep(8.0, 12.0)
        
        # Debug: Print page source to understand structure
        logger.info("Page title: " + driver.title)
        
        # Click on Player Props tab using multiple possible selectors
        props_selectors = [
            "//a[contains(text(), 'Player Props')]",
            "//div[contains(text(), 'Player Props')]",
            "//button[contains(text(), 'Player Props')]",
            "//span[contains(text(), 'Player Props')]"
        ]
        
        props_clicked = False
        for selector in props_selectors:
            try:
                props_tab = wait_for_element(driver, By.XPATH, selector)
                if props_tab:
                    # Scroll to the element
                    driver.execute_script("arguments[0].scrollIntoView(true);", props_tab)
                    random_sleep(1.0, 2.0)
                    
                    # Click the element
                    props_tab.click()
                    random_sleep(3.0, 5.0)
                    logger.info(f"Clicked on Player Props tab using selector: {selector}")
                    props_clicked = True
                    break
            except Exception as e:
                logger.warning(f"Failed to click Player Props tab with selector {selector}: {str(e)}")
        
        if not props_clicked:
            logger.warning("Could not find or click Player Props tab")
            return []
        
        # Scroll to load content
        scroll_to_load_content(driver, max_scrolls=10)
        
        # Find all prop rows using multiple possible selectors
        row_selectors = [
            "[data-test='prop-row']",
            "div[class*='prop-row']",
            "div[class*='PropRow']",
            "div[class*='row']"
        ]
        
        prop_rows = []
        for selector in row_selectors:
            rows = driver.find_elements(By.CSS_SELECTOR, selector)
            if rows:
                prop_rows = rows
                logger.info(f"Found {len(rows)} prop rows using selector: {selector}")
                break
        
        if not prop_rows:
            logger.warning("No prop rows found with any selector")
            return []
        
        props = []
        for row in prop_rows:
            try:
                # Extract player name using multiple possible selectors
                name_selectors = [
                    "[data-test='player-name']",
                    "div[class*='player-name']",
                    "div[class*='PlayerName']",
                    "div[class*='name']"
                ]
                
                player_name = None
                for selector in name_selectors:
                    try:
                        name_element = row.find_element(By.CSS_SELECTOR, selector)
                        player_name = name_element.text.strip()
                        if player_name:
                            break
                    except NoSuchElementException:
                        continue
                
                if not player_name:
                    logger.warning("Could not find player name")
                    continue
                
                # Extract prop type using multiple possible selectors
                type_selectors = [
                    "[data-test='prop-type']",
                    "div[class*='prop-type']",
                    "div[class*='PropType']",
                    "div[class*='type']"
                ]
                
                prop_type = None
                for selector in type_selectors:
                    try:
                        type_element = row.find_element(By.CSS_SELECTOR, selector)
                        prop_type = type_element.text.strip()
                        if prop_type:
                            break
                    except NoSuchElementException:
                        continue
                
                if not prop_type:
                    logger.warning("Could not find prop type")
                    continue
                
                # Extract line using multiple possible selectors
                line_selectors = [
                    "[data-test='line']",
                    "div[class*='line']",
                    "div[class*='Line']",
                    "div[class*='value']"
                ]
                
                line = None
                for selector in line_selectors:
                    try:
                        line_element = row.find_element(By.CSS_SELECTOR, selector)
                        line_text = line_element.text.strip()
                        line = float(line_text.replace('O/U ', ''))
                        break
                    except (NoSuchElementException, ValueError):
                        continue
                
                if not line:
                    logger.warning("Could not find line")
                    continue
                
                # Extract odds using multiple possible selectors
                odds_selectors = [
                    "[data-test='odds']",
                    "div[class*='odds']",
                    "div[class*='Odds']",
                    "div[class*='price']"
                ]
                
                over_odds = None
                under_odds = None
                
                for selector in odds_selectors:
                    try:
                        # Look for over/under odds separately
                        odds_elements = row.find_elements(By.CSS_SELECTOR, selector)
                        if len(odds_elements) >= 2:
                            # First element is usually over, second is under
                            over_text = odds_elements[0].text.strip()
                            under_text = odds_elements[1].text.strip()
                            
                            # Handle different odds formats
                            try:
                                # Try parsing as American odds first
                                over_odds = float(over_text.replace('+', '').replace('-', '-'))
                                under_odds = float(under_text.replace('+', '').replace('-', '-'))
                            except ValueError:
                                try:
                                    # Try parsing as decimal odds
                                    over_decimal = float(over_text)
                                    under_decimal = float(under_text)
                                    over_odds = convert_to_american_odds(over_decimal)
                                    under_odds = convert_to_american_odds(under_decimal)
                                except ValueError:
                                    logger.warning(f"Could not parse odds: {over_text}, {under_text}")
                                    continue
                            
                            break
                    except NoSuchElementException:
                        continue
                
                if not over_odds or not under_odds:
                    logger.warning("Could not find both over and under odds")
                    continue
                
                props.append({
                    "player_name": player_name,
                    "prop_type": prop_type,
                    "line": line,
                    "pinnacle_over": over_odds,
                    "pinnacle_under": under_odds
                })
                logger.info(f"Successfully scraped prop for {player_name}: {prop_type} {line} (O: {over_odds}, U: {under_odds})")
                
            except Exception as e:
                logger.warning(f"Error parsing Pinnacle prop: {str(e)}")
                continue
        
        logger.info(f"Successfully scraped {len(props)} props from Pinnacle")
        return props
        
    except Exception as e:
        logger.error(f"Error scraping Pinnacle: {str(e)}")
        raise ScrapingError(f"Failed to scrape Pinnacle: {str(e)}")

def match_props(prizepicks_props: List[Dict], pinnacle_props: List[Dict]) -> List[Dict]:
    """
    Match props between PrizePicks and Pinnacle based on player name and prop type.
    Returns a list of matched props with both odds.
    """
    matched_props = []
    
    for pp_prop in prizepicks_props:
        # Find matching Pinnacle prop
        matching_pinnacle = next(
            (p for p in pinnacle_props 
             if p["player_name"].lower() == pp_prop["player_name"].lower() 
             and p["prop_type"].lower() == pp_prop["prop_type"].lower()),
            None
        )
        
        if matching_pinnacle:
            # Calculate no-vig odds for both over and under
            over_vig = 1 / (1 + abs(matching_pinnacle["pinnacle_over"])/100) if matching_pinnacle["pinnacle_over"] > 0 else abs(matching_pinnacle["pinnacle_over"])/(abs(matching_pinnacle["pinnacle_over"]) + 100)
            under_vig = 1 / (1 + abs(matching_pinnacle["pinnacle_under"])/100) if matching_pinnacle["pinnacle_under"] > 0 else abs(matching_pinnacle["pinnacle_under"])/(abs(matching_pinnacle["pinnacle_under"]) + 100)
            total_vig = over_vig + under_vig
            
            # Remove vig
            over_no_vig = over_vig / total_vig
            under_no_vig = under_vig / total_vig
            
            # Convert back to American odds
            over_no_vig_american = round((1/over_no_vig - 1) * 100) if over_no_vig < 0.5 else round(-100/(1/over_no_vig - 1))
            under_no_vig_american = round((1/under_no_vig - 1) * 100) if under_no_vig < 0.5 else round(-100/(1/under_no_vig - 1))
            
            matched_props.append({
                "player_name": pp_prop["player_name"],
                "prop_type": pp_prop["prop_type"],
                "line": pp_prop["line"],
                "prizepicks_odds": pp_prop["prizepicks_odds"],
                "pinnacle_over": matching_pinnacle["pinnacle_over"],
                "pinnacle_under": matching_pinnacle["pinnacle_under"],
                "no_vig_over": over_no_vig_american,
                "no_vig_under": under_no_vig_american
            })
            logger.info(f"Matched prop for {pp_prop['player_name']}: {pp_prop['prop_type']}")
    
    return matched_props 

def get_espn_odds() -> List[Dict]:
    """
    Fetch odds from ESPN's public API for all available sports.
    Returns a list of dictionaries containing prop information.
    """
    try:
        # ESPN API endpoints for all major sports
        sports = [
            ('baseball', 'mlb'),
            ('basketball', 'nba'),
            ('basketball', 'ncaab'),
            ('football', 'nfl'),
            ('football', 'ncaaf'),
            ('hockey', 'nhl')
        ]
        
        all_props = []
        
        for sport, league in sports:
            logger.info(f"Fetching ESPN data for {sport} {league}")
            urls = [
                f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/scoreboard",
                f"https://site.api.espn.com/apis/site/v2/sports/{sport}/{league}/summary"
            ]
            
            for url in urls:
                try:
                    # Make request
                    logger.info(f"Making request to {url}")
                    response = requests.get(url)
                    response.raise_for_status()
                    
                    # Parse response
                    data = response.json()
                    logger.info(f"Got response from {url}")
                    
                    # Handle different response formats
                    events = []
                    if 'events' in data:
                        events = data['events']
                        logger.info(f"Found {len(events)} events in 'events' key")
                    elif 'gamepackage' in data:
                        events = [data['gamepackage']]
                        logger.info("Found gamepackage data")
                    else:
                        logger.warning(f"Unexpected data format from {url}: {list(data.keys())}")
                    
                    for event in events:
                        # Get game info
                        game_time = event.get('date')
                        home_team = None
                        away_team = None
                        
                        # Extract team names from different possible locations
                        if 'competitions' in event:
                            for comp in event['competitions']:
                                for team in comp.get('competitors', []):
                                    if team.get('homeAway') == 'home':
                                        home_team = team.get('team', {}).get('name')
                                    else:
                                        away_team = team.get('team', {}).get('name')
                        
                        # Get odds and props
                        odds = event.get('odds', [{}])[0]
                        if odds:
                            # Extract player props
                            props = odds.get('playerProps', [])
                            logger.info(f"Found {len(props)} props for {home_team} vs {away_team}")
                            
                            for prop in props:
                                player_name = prop.get('player', {}).get('name')
                                stat_type = prop.get('statType')
                                line = prop.get('line')
                                over_odds = prop.get('overOdds')
                                under_odds = prop.get('underOdds')
                                
                                # Clean and validate data
                                if all([player_name, stat_type, line, over_odds, under_odds]):
                                    try:
                                        # Convert odds to integers if they're strings
                                        if isinstance(over_odds, str):
                                            over_odds = int(over_odds.replace('+', '').replace('-', '-'))
                                        if isinstance(under_odds, str):
                                            under_odds = int(under_odds.replace('+', '').replace('-', '-'))
                                        
                                        # Convert line to float
                                        if isinstance(line, str):
                                            line = float(line.replace('O/U ', ''))
                                        
                                        all_props.append({
                                            'player_name': player_name,
                                            'prop_type': stat_type,
                                            'line': float(line),
                                            'pinnacle_over': int(over_odds),
                                            'pinnacle_under': int(under_odds),
                                            'game_time': game_time,
                                            'home_team': home_team,
                                            'away_team': away_team,
                                            'sport': f"{sport.upper()} {league.upper()}",
                                            'source': 'ESPN'
                                        })
                                        logger.info(f"Added prop for {player_name}: {stat_type} {line}")
                                    except (ValueError, TypeError) as e:
                                        logger.warning(f"Error parsing prop data: {str(e)}")
                                        continue
                                else:
                                    logger.warning(f"Missing required data for prop: {prop}")
                                        
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Error fetching from {url}: {str(e)}")
                    continue
        
        logger.info(f"Successfully fetched {len(all_props)} props from ESPN API")
        return all_props
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching odds from ESPN API: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_espn_odds: {str(e)}")
        return []

def get_action_network_odds() -> List[Dict]:
    """
    Fetch odds from Action Network's public API for all available sports.
    Returns a list of dictionaries containing prop information.
    """
    try:
        # Action Network API endpoints for all major sports
        sports = [
            ('baseball', 'mlb'),
            ('basketball', 'nba'),
            ('basketball', 'ncaab'),
            ('football', 'nfl'),
            ('football', 'ncaaf'),
            ('hockey', 'nhl')
        ]
        
        # Headers to mimic browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
            'Accept': 'application/json',
            'Origin': 'https://www.actionnetwork.com'
        }
        
        all_props = []
        
        for sport, league in sports:
            logger.info(f"Fetching Action Network data for {sport} {league}")
            urls = [
                f"https://api.actionnetwork.com/web/v1/scoreboard/{league}",
                f"https://api.actionnetwork.com/web/v1/games/{league}"
            ]
            
            headers['Referer'] = f"https://www.actionnetwork.com/{league}/odds"
            
            for url in urls:
                try:
                    # Make request
                    logger.info(f"Making request to {url}")
                    response = requests.get(url, headers=headers)
                    response.raise_for_status()
                    
                    # Parse response
                    data = response.json()
                    logger.info(f"Got response from {url}")
                    
                    # Handle different response formats
                    games = []
                    if 'games' in data:
                        games = data['games']
                        logger.info(f"Found {len(games)} games in 'games' key")
                    elif isinstance(data, list):
                        games = data
                        logger.info(f"Found {len(games)} games in list format")
                    else:
                        logger.warning(f"Unexpected data format from {url}: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                    
                    for game in games:
                        # Get game info
                        game_time = game.get('start_time')
                        home_team = game.get('home_team', {}).get('name')
                        away_team = game.get('away_team', {}).get('name')
                        
                        # Get props from different possible locations
                        props = []
                        if 'player_props' in game:
                            props = game['player_props']
                            logger.info(f"Found {len(props)} props in player_props for {home_team} vs {away_team}")
                        elif 'props' in game:
                            props = game['props']
                            logger.info(f"Found {len(props)} props in props for {home_team} vs {away_team}")
                        
                        for prop in props:
                            player_name = prop.get('player_name') or prop.get('player', {}).get('name')
                            stat_type = prop.get('stat_type') or prop.get('type')
                            line = prop.get('line') or prop.get('points')
                            over_odds = prop.get('over_odds') or prop.get('over')
                            under_odds = prop.get('under_odds') or prop.get('under')
                            
                            # Clean and validate data
                            if all([player_name, stat_type, line, over_odds, under_odds]):
                                try:
                                    # Convert odds to integers if they're strings
                                    if isinstance(over_odds, str):
                                        over_odds = int(over_odds.replace('+', '').replace('-', '-'))
                                    if isinstance(under_odds, str):
                                        under_odds = int(under_odds.replace('+', '').replace('-', '-'))
                                    
                                    # Convert line to float
                                    if isinstance(line, str):
                                        line = float(line.replace('O/U ', ''))
                                    
                                    all_props.append({
                                        'player_name': player_name,
                                        'prop_type': stat_type,
                                        'line': float(line),
                                        'pinnacle_over': int(over_odds),
                                        'pinnacle_under': int(under_odds),
                                        'game_time': game_time,
                                        'home_team': home_team,
                                        'away_team': away_team,
                                        'sport': f"{sport.upper()} {league.upper()}",
                                        'source': 'Action Network'
                                    })
                                    logger.info(f"Added prop for {player_name}: {stat_type} {line}")
                                except (ValueError, TypeError) as e:
                                    logger.warning(f"Error parsing prop data: {str(e)}")
                                    continue
                            else:
                                logger.warning(f"Missing required data for prop: {prop}")
                                    
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Error fetching from {url}: {str(e)}")
                    continue
        
        logger.info(f"Successfully fetched {len(all_props)} props from Action Network API")
        return all_props
        
    except Exception as e:
        logger.error(f"Unexpected error in get_action_network_odds: {str(e)}")
        return []

def get_odds_api_data() -> List[Dict]:
    """
    Fetch odds from The Odds API (free tier) for all available sports.
    Returns a list of dictionaries containing prop information.
    """
    try:
        api_key = os.getenv('ODDS_API_KEY')
        if not api_key:
            logger.warning("No Odds API key found")
            return []
            
        # Get current and next day dates
        today = datetime.now().strftime('%Y-%m-%d')
        tomorrow = (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Available sports
        sports = [
            'baseball_mlb',
            'basketball_nba',
            'basketball_ncaab',
            'football_nfl',
            'football_ncaaf',
            'hockey_nhl'
        ]
        
        all_props = []
        
        for sport in sports:
            logger.info(f"Fetching Odds API data for {sport}")
            for date in [today, tomorrow]:
                url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds"
                params = {
                    'apiKey': api_key,
                    'date': date,
                    'regions': 'us',
                    'markets': 'player_props',
                    'oddsFormat': 'american'
                }
                
                try:
                    # Make request
                    logger.info(f"Making request to {url} for date {date}")
                    response = requests.get(url, params=params)
                    response.raise_for_status()
                    
                    games = response.json()
                    logger.info(f"Got {len(games)} games from {url}")
                    
                    for game in games:
                        game_time = game.get('commence_time')
                        home_team = game.get('home_team')
                        away_team = game.get('away_team')
                        
                        for bookmaker in game.get('bookmakers', []):
                            for market in bookmaker.get('markets', []):
                                if market.get('key') == 'player_props':
                                    outcomes = market.get('outcomes', [])
                                    logger.info(f"Found {len(outcomes)} props for {home_team} vs {away_team}")
                                    
                                    for outcome in outcomes:
                                        player_name = outcome.get('name')
                                        stat_type = outcome.get('description')
                                        line = outcome.get('point')
                                        odds = outcome.get('price')
                                        
                                        if all([player_name, stat_type, line, odds]):
                                            try:
                                                all_props.append({
                                                    'player_name': player_name,
                                                    'prop_type': stat_type,
                                                    'line': float(line),
                                                    'pinnacle_over': int(odds) if odds > 0 else int(odds),
                                                    'pinnacle_under': int(-odds) if odds > 0 else int(-odds),
                                                    'game_time': game_time,
                                                    'home_team': home_team,
                                                    'away_team': away_team,
                                                    'sport': sport.upper().replace('_', ' '),
                                                    'source': 'The Odds API'
                                                })
                                                logger.info(f"Added prop for {player_name}: {stat_type} {line}")
                                            except (ValueError, TypeError) as e:
                                                logger.warning(f"Error parsing prop data: {str(e)}")
                                                continue
                                        else:
                                            logger.warning(f"Missing required data for prop: {outcome}")
                                                
                except requests.exceptions.RequestException as e:
                    logger.warning(f"Error fetching from {url}: {str(e)}")
                    continue
        
        logger.info(f"Successfully fetched {len(all_props)} props from The Odds API")
        return all_props
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching odds from The Odds API: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in get_odds_api_data: {str(e)}")
        return []

def get_cached_data(source: str) -> Optional[List[Dict]]:
    """Get cached data if it exists and is not expired."""
    cache_file = CACHE_DIR / f"{source}_cache.json"
    if not cache_file.exists():
        return None
        
    try:
        with open(cache_file, 'r') as f:
            cache_data = json.load(f)
            cache_time = datetime.fromisoformat(cache_data['timestamp'])
            if datetime.now() - cache_time < CACHE_DURATION:
                return cache_data['data']
    except Exception as e:
        logger.warning(f"Error reading cache: {str(e)}")
    return None

def save_to_cache(source: str, data: List[Dict]):
    """Save data to cache with timestamp."""
    try:
        CACHE_DIR.mkdir(exist_ok=True)
        cache_file = CACHE_DIR / f"{source}_cache.json"
        with open(cache_file, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'data': data
            }, f)
    except Exception as e:
        logger.warning(f"Error saving to cache: {str(e)}")

def scrape_underdog_fantasy(driver: webdriver.Chrome) -> List[Dict]:
    """
    Scrape player props from Underdog Fantasy.
    Returns a list of dictionaries containing prop information.
    """
    try:
        logger.info("Starting Underdog Fantasy scraping...")
        driver.get("https://underdogfantasy.com/pick-em")
        
        # Wait for initial load
        random_sleep(8.0, 12.0)
        
        # Handle access denied if necessary
        if not handle_access_denied(driver):
            logger.error("Could not handle access denied page")
            return []
        
        # Find all player cards
        card_selectors = [
            "[data-test='player-card']",
            "div[class*='PlayerCard']",
            "div[class*='player-card']",
            "div[class*='card']"
        ]
        
        player_cards = []
        for selector in card_selectors:
            cards = driver.find_elements(By.CSS_SELECTOR, selector)
            if cards:
                player_cards = cards
                logger.info(f"Found {len(cards)} player cards using selector: {selector}")
                break
        
        if not player_cards:
            logger.warning("No player cards found")
            return []
        
        props = []
        for card in player_cards:
            try:
                # Extract player name
                name_element = card.find_element(By.CSS_SELECTOR, "[data-test='player-name']")
                player_name = name_element.text.strip()
                
                # Extract stat type and line
                stat_elements = card.find_elements(By.CSS_SELECTOR, "[data-test='stat-row']")
                for stat in stat_elements:
                    try:
                        stat_type = stat.find_element(By.CSS_SELECTOR, "[data-test='stat-type']").text.strip()
                        line = float(stat.find_element(By.CSS_SELECTOR, "[data-test='line']").text.strip().replace('O/U ', ''))
                        odds = float(stat.find_element(By.CSS_SELECTOR, "[data-test='odds']").text.strip().replace('+', '').replace('-', '-'))
                        
                        props.append({
                            "player_name": player_name,
                            "prop_type": stat_type,
                            "line": line,
                            "underdog_odds": odds
                        })
                        logger.info(f"Successfully scraped prop for {player_name}: {stat_type} {line} ({odds})")
                    except Exception as e:
                        logger.warning(f"Error parsing stat: {str(e)}")
                        continue
                
            except Exception as e:
                logger.warning(f"Error parsing player card: {str(e)}")
                continue
        
        logger.info(f"Successfully scraped {len(props)} props from Underdog Fantasy")
        return props
        
    except Exception as e:
        logger.error(f"Error scraping Underdog Fantasy: {str(e)}")
        raise ScrapingError(f"Failed to scrape Underdog Fantasy: {str(e)}")

def scrape_draftkings(driver: webdriver.Chrome) -> List[Dict]:
    """
    Scrape player props from DraftKings.
    Returns a list of dictionaries containing prop information.
    """
    try:
        logger.info("Starting DraftKings scraping...")
        driver.get("https://sportsbook.draftkings.com/player-props")
        
        # Wait for initial load
        random_sleep(8.0, 12.0)
        
        # Handle access denied if necessary
        if not handle_access_denied(driver):
            logger.error("Could not handle access denied page")
            return []
        
        # Find all prop rows
        row_selectors = [
            "[data-test='prop-row']",
            "div[class*='prop-row']",
            "div[class*='PropRow']",
            "div[class*='row']"
        ]
        
        prop_rows = []
        for selector in row_selectors:
            rows = driver.find_elements(By.CSS_SELECTOR, selector)
            if rows:
                prop_rows = rows
                logger.info(f"Found {len(rows)} prop rows using selector: {selector}")
                break
        
        if not prop_rows:
            logger.warning("No prop rows found")
            return []
        
        props = []
        for row in prop_rows:
            try:
                # Extract player name
                name_element = row.find_element(By.CSS_SELECTOR, "[data-test='player-name']")
                player_name = name_element.text.strip()
                
                # Extract prop type and line
                type_element = row.find_element(By.CSS_SELECTOR, "[data-test='prop-type']")
                prop_type = type_element.text.strip()
                
                line_element = row.find_element(By.CSS_SELECTOR, "[data-test='line']")
                line = float(line_element.text.strip().replace('O/U ', ''))
                
                # Extract over/under odds
                over_element = row.find_element(By.CSS_SELECTOR, "[data-test='over-odds']")
                under_element = row.find_element(By.CSS_SELECTOR, "[data-test='under-odds']")
                
                over_odds = float(over_element.text.strip().replace('+', '').replace('-', '-'))
                under_odds = float(under_element.text.strip().replace('+', '').replace('-', '-'))
                
                props.append({
                    "player_name": player_name,
                    "prop_type": prop_type,
                    "line": line,
                    "draftkings_over": over_odds,
                    "draftkings_under": under_odds
                })
                logger.info(f"Successfully scraped prop for {player_name}: {prop_type} {line} (O: {over_odds}, U: {under_odds})")
                
            except Exception as e:
                logger.warning(f"Error parsing prop row: {str(e)}")
                continue
        
        logger.info(f"Successfully scraped {len(props)} props from DraftKings")
        return props
        
    except Exception as e:
        logger.error(f"Error scraping DraftKings: {str(e)}")
        raise ScrapingError(f"Failed to scrape DraftKings: {str(e)}")

def scrape_betting_forums(driver: webdriver.Chrome) -> List[Dict]:
    """
    Scrape player props from popular betting forums.
    Returns a list of dictionaries containing prop information.
    """
    try:
        logger.info("Starting betting forums scraping...")
        forums = [
            "https://www.reddit.com/r/sportsbook/",
            "https://www.reddit.com/r/dfsports/",
            "https://www.reddit.com/r/fantasyfootball/",
            "https://www.reddit.com/r/fantasybaseball/",
            "https://www.reddit.com/r/fantasybasketball/"
        ]
        
        all_props = []
        for forum in forums:
            try:
                logger.info(f"Scraping forum: {forum}")
                driver.get(forum)
                random_sleep(5.0, 8.0)
                
                # Find all posts
                post_selectors = [
                    "[data-test='post']",
                    "div[class*='Post']",
                    "div[class*='post']",
                    "div[class*='thread']"
                ]
                
                posts = []
                for selector in post_selectors:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements:
                        posts = elements
                        logger.info(f"Found {len(elements)} posts using selector: {selector}")
                        break
                
                for post in posts:
                    try:
                        # Extract post title and content
                        title_element = post.find_element(By.CSS_SELECTOR, "[data-test='post-title']")
                        title = title_element.text.strip()
                        
                        content_element = post.find_element(By.CSS_SELECTOR, "[data-test='post-content']")
                        content = content_element.text.strip()
                        
                        # Look for prop patterns in title and content
                        prop_patterns = [
                            r"(\w+)\s+(\w+)\s+(over|under)\s+(\d+\.?\d*)",
                            r"(\w+)\s+(\w+)\s+(\d+\.?\d*)",
                            r"(\w+)\s+(\w+)\s+(\d+\.?\d*)\s+(over|under)"
                        ]
                        
                        for pattern in prop_patterns:
                            matches = re.finditer(pattern, title + " " + content, re.IGNORECASE)
                            for match in matches:
                                try:
                                    groups = match.groups()
                                    if len(groups) >= 3:
                                        player_name = groups[0]
                                        prop_type = groups[1]
                                        line = float(groups[2])
                                        
                                        # Try to extract odds if present
                                        odds_match = re.search(r"(\+|-)\d+", title + " " + content)
                                        odds = float(odds_match.group(0).replace('+', '')) if odds_match else None
                                        
                                        prop = {
                                            "player_name": player_name,
                                            "prop_type": prop_type,
                                            "line": line,
                                            "source": "Betting Forum",
                                            "confidence": "low"  # Mark as low confidence since it's from forums
                                        }
                                        
                                        if odds:
                                            prop["forum_odds"] = odds
                                        
                                        all_props.append(prop)
                                        logger.info(f"Found prop in forum post: {player_name} {prop_type} {line}")
                                except Exception as e:
                                    logger.warning(f"Error parsing prop from forum post: {str(e)}")
                                    continue
                        
                    except Exception as e:
                        logger.warning(f"Error parsing forum post: {str(e)}")
                        continue
                
            except Exception as e:
                logger.warning(f"Error scraping forum {forum}: {str(e)}")
                continue
        
        logger.info(f"Successfully scraped {len(all_props)} props from betting forums")
        return all_props
        
    except Exception as e:
        logger.error(f"Error scraping betting forums: {str(e)}")
        raise ScrapingError(f"Failed to scrape betting forums: {str(e)}")

def get_odds_data() -> List[Dict]:
    """
    Get odds data from PrizePicks and Pinnacle.
    Returns a list of dictionaries containing prop information.
    """
    try:
        # Try to get cached data first
        cached_data = get_cached_data('odds')
        if cached_data:
            logger.info("Using cached odds data")
            return cached_data
            
        all_props = []
        
        # Try PrizePicks first
        logger.info("Scraping odds from PrizePicks...")
        try:
            driver = setup_driver()
            prizepicks_props = scrape_prizepicks(driver)
            if prizepicks_props:
                logger.info(f"Successfully scraped {len(prizepicks_props)} props from PrizePicks")
                all_props.extend(prizepicks_props)
            else:
                logger.warning("No props scraped from PrizePicks")
        except Exception as e:
            logger.error(f"Error scraping PrizePicks: {str(e)}")
        finally:
            driver.quit()
            
        # Try Pinnacle
        logger.info("Scraping odds from Pinnacle...")
        try:
            driver = setup_driver()
            pinnacle_props = scrape_pinnacle(driver)
            if pinnacle_props:
                logger.info(f"Successfully scraped {len(pinnacle_props)} props from Pinnacle")
                all_props.extend(pinnacle_props)
            else:
                logger.warning("No props scraped from Pinnacle")
        except Exception as e:
            logger.error(f"Error scraping Pinnacle: {str(e)}")
        finally:
            driver.quit()
        
        if all_props:
            # Match props between PrizePicks and Pinnacle
            matched_props = match_props(
                [p for p in all_props if 'prizepicks_odds' in p],
                [p for p in all_props if 'pinnacle_over' in p]
            )
            
            if matched_props:
                logger.info(f"Successfully matched {len(matched_props)} props between PrizePicks and Pinnacle")
                save_to_cache('odds', matched_props)
                return matched_props
            else:
                logger.warning("No props matched between PrizePicks and Pinnacle")
                return []
        
        # If all methods fail, return empty list
        logger.error("Failed to scrape props from PrizePicks and Pinnacle")
        return []
        
    except Exception as e:
        logger.error(f"Error in get_odds_data: {str(e)}")
        return [] 