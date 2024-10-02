from playwright.async_api import async_playwright
from dataclasses import dataclass, asdict, field
import pandas as pd
import argparse
import os
import sys
import re
import asyncio

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
            (asdict(business) for business in self.business_list), sep="_"
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

async def main():
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
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"])
        page = await browser.new_page()

        await page.goto("https://www.google.com/maps", timeout=60000)
        await page.wait_for_timeout(5000)

        for search_for_index, search_for in enumerate(search_list):
            print(f"-----\n{search_for_index} - {search_for}".strip())

            # Separate the search into city and business type
            city, business_type = search_for.split(';')

            # Search for the city first
            await page.locator('//input[@id="searchboxinput"]').fill(city.strip())
            await page.wait_for_timeout(3000)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(5000)

            # Clear the search box and search for the business type
            await page.locator('//input[@id="searchboxinput"]').fill(business_type.strip())
            await page.wait_for_timeout(3000)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(3000)

            # Scroll and gather listings
            await page.hover('//a[contains(@href, "https://www.google.com/maps/place")]')
            previously_counted = 0
            while True:
                await page.mouse.wheel(0, 10000)
                await page.wait_for_timeout(3000)

                count = await page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').count()
                if count >= total:
                    all_listings = await page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()
                    listings = all_listings[:total]
                    print(f"Total Scraped: {len(listings)}")
                    break
                else:
                    if count == previously_counted:
                        all_listings = await page.locator('//a[contains(@href, "https://www.google.com/maps/place")]').all()
                        listings = all_listings
                        print(f"Arrived at all available\nTotal Scraped: {len(listings)}")
                        break
                    else:
                        previously_counted = count
                        print(f"Currently Scraped: ", previously_counted)

            business_list = BusinessList()

        # Scraping business details
        for listing in listings:
            try:
                await listing.click()  # Cambia a await aquí
                await page.wait_for_timeout(5000)

                name_xpath = '//h1[@class="DUwDvf lfPIob"]'
                address_xpath = '//button[@data-item-id="address"]//div[contains(@class, "fontBodyMedium")]'
                website_xpath = '//a[@data-item-id="authority"]//div[contains(@class, "fontBodyMedium")]'
                phone_number_xpath = '//button[contains(@data-item-id, "phone:tel:")]//div[contains(@class, "fontBodyMedium")]'
                reviews_average_xpath = '//span[@class="ceNzKf"]'

                business = Business()

                if await page.locator(name_xpath).count() > 0:
                    business.name = await page.locator(name_xpath).inner_text()  # Cambia a await aquí
                else:
                    business.name = ""
                if await page.locator(address_xpath).count() > 0:
                    addresses = await page.locator(address_xpath).all()  # Asegúrate de usar await aquí
                    if addresses:
                        business.address = await addresses[0].inner_text()  # Cambia a await aquí
                    else:
                        business.address = ""
                else:
                    business.address = ""
                if await page.locator(website_xpath).count() > 0:
                    websites = await page.locator(website_xpath).all()  # Asegúrate de usar await aquí
                    if websites:
                        business.website = await websites[0].inner_text()  # Cambia a await aquí
                    else:
                        business.website = ""
                else:
                    business.website = ""
                if await page.locator(phone_number_xpath).count() > 0:
                    phone_numbers = await page.locator(phone_number_xpath).all()  # Asegúrate de usar await aquí
                    if phone_numbers:
                        business.phone_number = await phone_numbers[0].inner_text()  # Cambia a await aquí
                    else:
                        business.phone_number = ""
                else:
                    business.phone_number = ""
                if await page.locator(reviews_average_xpath).count() > 0:
                    aria_label = await page.locator(reviews_average_xpath).get_attribute('aria-label')  # Cambia a await aquí
                    if aria_label:
                        business.reviews_average = float(
                            aria_label.split()[0]
                            .replace(',', '.')
                            .strip()
                        )
                    else:
                        business.reviews_average = ""
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

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())