from playwright.sync_api import sync_playwright
from dataclasses import dataclass, asdict, field
import pandas as pd
import argparse
import os
import sys
import re

@dataclass
class Business:
    """holds business data"""

    name: str = None
    address: str = None
    website: str = None
    phone_number: str = None
    reviews_average: float = None
    latitude: float = None
    longitude: float = None

@dataclass
class BusinessList:
    """holds list of Business objects, and save to both excel and csv"""
    business_list: list[Business] = field(default_factory=list)
    save_at = 'output'

    def dataframe(self):
        """transform business_list to pandas dataframe"""
        return pd.json_normalize(
            (asdict(business) for business in self.business_list), sep="_" # type: ignore
        )

    def save_to_excel(self, filename):
        """saves pandas dataframe to excel (xlsx) file"""
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_excel(f"{self.save_at}/{filename}.xlsx", index=False)

    def save_to_csv(self, filename):
        """saves pandas dataframe to csv file"""
        if not os.path.exists(self.save_at):
            os.makedirs(self.save_at)
        self.dataframe().to_csv(f"{self.save_at}/{filename}.csv", index=False)

def clean_filename(filename):
    """Replaces invalid characters in filenames with an underscore"""
    return re.sub(r'[<>:"/\\|?*\n;]', '_', filename)

def extract_coordinates_from_url(url: str) -> tuple[float, float]:
    """helper function to extract coordinates from url"""
    coordinates = url.split('/@')[-1].split('/')[0]
    # return latitude, longitude
    return float(coordinates.split(',')[0]), float(coordinates.split(',')[1])

def main():
    # Read search from arguments
    parser = argparse.ArgumentParser()
    parser.add_argument("-s", "--search", type=str)
    parser.add_argument("-t", "--total", type=int)
    args = parser.parse_args()

    search_list = [args.search] if args.search else []
    total = args.total if args.total else 1_000_000  # Default large number if no total is provided

    if not search_list:
        # If no search is passed, read from input.txt file
        input_file_name = 'input.txt'
        input_file_path = os.path.join(os.getcwd(), input_file_name)
        if os.path.exists(input_file_path):
            with open(input_file_path, 'r') as file:
                search_list = file.readlines()

        if not search_list:
            print('Error: You must either pass the -s search argument, or add searches to input.txt')
            sys.exit()

    # Scraping with Playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        page.goto("https://www.google.com/maps", timeout=60000)
        page.wait_for_timeout(5000)

        for search_for_index, search_for in enumerate(search_list):
            print(f"-----\n{search_for_index} - {search_for}".strip())

            # Separate the search into city and business type
            city, business_type = search_for.split(';')

            # Search for the city first
            page.locator('//input[@id="searchboxinput"]').fill(city.strip())
            page.wait_for_timeout(3000)
            page.keyboard.press("Enter")
            page.wait_for_timeout(5000)

            # Clear the search box and search for the business type
            page.locator('//input[@id="searchboxinput"]').fill(business_type.strip())
            page.wait_for_timeout(3000)
            page.keyboard.press("Enter")
            page.wait_for_timeout(3000)

            # Scroll and gather listings
            page.hover('//a[contains(@href, "https://www.google.com/maps/place")]')
            previously_counted = 0
            while True:
                page.mouse.wheel(0, 10000)
                page.wait_for_timeout(3000)

                if page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count() >= total:
                    listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()[:total]
                    listings = [listing.locator("xpath=..") for listing in listings]
                    print(f"Total Scraped: {len(listings)}")
                    break
                else:
                    if page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count() == previously_counted:
                        listings = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()
                        print(f"Arrived at all available\nTotal Scraped: {len(listings)}")
                        break
                    else:
                        previously_counted = page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()
                        print(f"Currently Scraped: ", previously_counted)

            business_list = BusinessList()

            # Scraping business details
            for listing in listings:
                try:
                    listing.click()
                    page.wait_for_timeout(5000)

                    name_xpath = '//h1[@class="DUwDvf lfPIob"]'
                    address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                    website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                    phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                    reviews_average_xpath = '//span[@class="ceNzKf"]'

                    business = Business()

                    if page.locator(name_xpath).count() > 0:
                        business.name = page.locator(name_xpath).inner_text()
                    else:
                        business.name = ""
                    if page.locator(address_xpath).count() > 0:
                        business.address = page.locator(address_xpath).all()[0].inner_text()
                    else:
                        business.address = ""
                    if page.locator(website_xpath).count() > 0:
                        business.website = page.locator(website_xpath).all()[0].inner_text()
                    else:
                        business.website = ""
                    if page.locator(phone_number_xpath).count() > 0:
                        business.phone_number = page.locator(phone_number_xpath).all()[0].inner_text()
                    else:
                        business.phone_number = ""
                    if page.locator(reviews_average_xpath).count() > 0:
                        business.reviews_average = float(
                            page.locator(reviews_average_xpath).get_attribute('aria-label')
                            .split()[0]
                            .replace(',', '.')
                            .strip())
                    else:
                        business.reviews_average = ""

                    business.latitude, business.longitude = extract_coordinates_from_url(page.url)

                    business_list.business_list.append(business)
                except Exception as e:
                    print(f'Error occurred: {e}')

            # Clean and save the filename
            filename = clean_filename(f"google_maps_data_{search_for}".replace(' ', '_'))
            business_list.save_to_excel(filename)
            business_list.save_to_csv(filename)

        browser.close()

if __name__ == "__main__":
    main()
