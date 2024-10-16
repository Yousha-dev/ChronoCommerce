#!/usr/bin/python
# -*- coding: utf-8 -*-

import json
from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
import time
import re
from django.db.models import Count
from random import randint
from home.models import Proxy
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from home.scraper.currency_map import currency_map

class BaseProductsPage:

    def __init__(self, url):
        self.url = url
        self.product_pages = []
        self.driver = None

    def setup_driver(self):
        # Get count of all enabled proxies
        count = Proxy.objects.filter(enable=True).aggregate(count=Count('id'))['count']
        proxy_str = None

        if count > 0:
            # Get a random proxy
            random_index = randint(0, count - 1)
            proxy = Proxy.objects.filter(enable=True)[random_index]

            if proxy.username and proxy.password:
                proxy_str = f'http://{proxy.username}:{proxy.password}@{proxy.ip}:{proxy.port}'
            else:
                proxy_str = f'http://{proxy.ip}:{proxy.port}'
        chrome_options = Options()
        chrome_options.add_argument("--log-level=3")
        # chrome_options.add_argument("--headless")  # Run in headless mode
        # chrome_options.add_argument("--no-sandbox")  # Bypass OS security model
        # chrome_options.add_argument("--disable-gpu")
        # chrome_options.add_argument("--disable-dev-shm-usage")  # Overcome limited resource problems

        if proxy_str:
            chrome_options.add_argument(f'--proxy-server={proxy_str}')


        # Set up Chrome service
        service = ChromeService(ChromeDriverManager().install())

        self.driver = webdriver.Chrome(service=service, options=chrome_options)
    
    def close_driver(self):
        if self.driver is not None:
            self.driver.quit()
            self.driver = None
    
    def fetch_source_code(self):
        try:
            self.setup_driver()
            self.driver.get(self.url)
            time.sleep(3)
            self.scroll_down(self.driver)
            time.sleep(2)
            return self.driver.page_source
            
        except Exception as e:
            return None
        # finally:
        #     self.close_driver()

    def scroll_down(self, driver):
        scroll_pause_time = 0.4
        screen_height = \
            driver.execute_script('return window.screen.height;')
        i = 0.4
        while True:
            driver.execute_script('window.scrollTo(0, {screen_height}*{i});'.format(screen_height=screen_height,
                                  i=i))
            i += 0.4
            time.sleep(scroll_pause_time)
            scroll_height = \
                driver.execute_script('return document.body.scrollHeight;'
                    )
            if screen_height * i > scroll_height:
                break

    def get_products_info(self, soup):
        pass


class BuchererProductsPage(BaseProductsPage):

    # def fetch_source_code(self):
    #     try:
    #         self.setup_driver()
    #         self.driver.get(self.url)
    #         time.sleep(3)
    #         self.scroll_down(self.driver)
    #         time.sleep(2)
    #         # while True:
    #         #     try:
    #         #         self.driver.execute_script("""
    #         #             var button = document.querySelector('.o-search__load-more-btn');
    #         #             if (button) {
    #         #                 button.click();
    #         #             } else {
    #         #                 throw 'No more "load more" button';
    #         #             }
    #         #         """)
    #         #         time.sleep(2)  # wait for the page to load
    #         #         self.scroll_down(self.driver)
    #         #         time.sleep(2)
    #         #     except Exception:
    #         #         break  # no more "load more" button, break the loop
    #         # time.sleep(2)
    #         return self.driver.page_source
            
    #     except Exception as e:
    #         return None
    #     # finally:
    #     #     self.close_driver()

    # def scroll_down(self, driver):
    #     scroll_pause_time = 0.1
    #     i = 0.975
    #     while True:
    #         scroll_height = \
    #             driver.execute_script('return document.body.scrollHeight;'
    #                 )
    #         driver.execute_script('window.scrollTo(0, {scroll_height}-({scroll_height}*{i}));'.format(scroll_height=scroll_height,
    #                               i=i))
    #         i -= 0.025
    #         time.sleep(scroll_pause_time)
    #         if  i < 0.05:
    #             break


    def get_products_info(self, soup):
        products = soup.find_all('a',
                                 attrs={'class': 'm-product-tile__link'
                                 })
        for product in products:
            link = 'https://www.bucherer.com' + product.get('href')
            brand = product.find('span',
                                 attrs={'class': 'm-product-tile__product-brand'
                                 }).get_text().replace('\n', '').strip().title()
            model_full = product.find('span',
                                 attrs={'class': 'm-product-tile__product-model'
                                 }).get_text().replace('\n', '').strip()
            model = extract_model_name(model_full)
            price = product.find('span', attrs={'class': 'value'}).get('content')
            currency = product.find('span', attrs={'class': 'value'}).get_text().strip().split(' ')[0]
            self.product_pages.append((brand, model, link, price, currency))
        return self.product_pages


class TourneauProductsPage(BaseProductsPage):

    def get_products_info(self, soup):
        products = soup.find_all('li', attrs={'class': 'grid-tile'})
        for product in products:
            link = product.find('a', attrs={'class': 'thumb-link'
                                }).get('href')
            brand = product.find('div', attrs={'class': 'brand'
                                 }).get_text().replace('\n', '').strip().title()
            model_full = product.find('a', attrs={'class': 'name-link'
                                 }).get_text().replace('\n', '').strip()
            model = extract_model_name(model_full)
            price = product.find('span', attrs={'class': 'product-sales-price'}).get_text()
            price = re.sub('\D', '', price)
            currency = product.find('meta', attrs={'itemprop': 'priceCurrency'}).get('content')
            self.product_pages.append((brand, model, link, price, currency))
        return self.product_pages


class CrownandcaliberProductsPage(BaseProductsPage):

    def get_products_info(self, soup):
        products = soup.find_all('div',
                                 attrs={'class': 'cell small-12 medium-4 ss-item ng-scope'
                                 })
        for product in products:
            productCon = product.find('a',
                    attrs={'class': 'grid-view-item__link'})
            link = "https:"+productCon.get('href')
            brand = productCon.find('div',
                                    attrs={'class': 'card-title ng-binding'
                                    }).get_text().replace('\n', '').strip().title()
            model_full = productCon.find('div',
                                    attrs={'class': 'card-subTitle ng-binding'
                                    }).get_text().replace('\n', '').strip().title()
            model = extract_model_name(model_full)
            price_with_currency = productCon.find('span',
                                                  attrs={'class': 'current-price product-price__price ng-binding'
                                                  }).get_text().replace(' ', ''
                                  ).replace('\n', '').replace("'", '').replace(',', ''
                                  )

            # Split the currency symbol and the price
            currency_symbol, price = price_with_currency[0], price_with_currency[1:]

            currency = currency_map.get(currency_symbol, "")

            self.product_pages.append((brand, model, link, price, currency))
        return self.product_pages


class BobswatchesProductsPage(BaseProductsPage):

    def get_products_info(self, soup):
        products = soup.find_all('div', attrs={'class': 'seocart_ProductWrapper'})
        for product in products:
            product_json = json.loads(product.find('script', type='application/ld+json').string)
            link = product_json["url"]
            
            for prop in product_json["additionalProperty"]:
                if prop["name"] == "Model Name":
                    model = prop["value"]
                    break
            try:
                brand = product_json["name"][:product_json["name"].index(model)].strip()
            except ValueError:
                brand = product_json["name"]
            brand = brand.title()
            if len(brand.split()) > 1:
                    brand = ""
            currency = product_json["offers"]["priceCurrency"]
            price = product_json["offers"]["price"]
            self.product_pages.append((brand, model, link, price, currency))
        return self.product_pages


class GoldsmithsProductsPage(BaseProductsPage):

    def get_products_info(self, soup):
        products = soup.find_all('div', attrs={'class': 'productTile'})
        for product in products:
            productCon = product.find('a')
            link = 'https://www.goldsmiths.co.uk' \
                + productCon.get('href')
            brand = productCon.find('div',
                                    attrs={'class': 'productTileBrand'
                                    }).get_text().replace('\n', '').strip().title()
            model_full = productCon.find('div',
                    attrs={'class': 'productTileName'
                    }).get_text().replace('\n', '')
            model = extract_model_name(model_full)
            
            price_div = productCon.find('div', attrs={'class': 'productTilePrice'})
            price = ''.join(price_div.find_all(text=True, recursive=False)).replace('\n', '').replace('\t', '').replace(',', '').replace(' ', '')
            price_with_currency = re.sub('(\\d+\\.00)(\xc2\xa3)', r'\1 \2', price)
            currency_symbol, price = price_with_currency[0], price_with_currency[1:]

            currency = currency_map.get(currency_symbol, "")
            
            self.product_pages.append((brand, model, link, price, currency))
        self.close_driver()
        return self.product_pages


class WatchesofswitzerlandProductsPage(BaseProductsPage):

    def get_products_info(self, soup):
        products = soup.find_all('div', attrs={'class': 'productTile'})
        for product in products:
            productCon = product.find('a')
            link = 'https://www.watchesofswitzerland.com' + productCon.get('href')
            brand = productCon.find('div', attrs={'class': 'productTileBrand'}).get_text().replace('\n', '').title()
            model_full = productCon.find('div', attrs={'class': 'productTileName'}).get_text().replace('\n', '')
            model = extract_model_name(model_full)
            price_div = productCon.find('div', attrs={'class': 'productTilePrice'})
            price = ''.join(price_div.find_all(text=True, recursive=False)).replace('\n', '').replace('\t', '').replace(',', '').replace(' ', '')
            price_with_currency = re.sub('(\\d+\\.00)(\xc2\xa3)', r'\1 \2', price)
            currency_symbol, price = price_with_currency[0], price_with_currency[1:]
        
            currency = currency_map.get(currency_symbol, "")

            self.product_pages.append((brand, model, link, price, currency))
        
        return self.product_pages


class JomashopProductsPage(BaseProductsPage):

    def get_products_info(self, soup):
        products = soup.find_all('div',
                                 attrs={'class': 'productItemBlock'})
        for product in products:
            link = 'https://www.jomashop.com' \
                + product.get('data-scroll-target')
            brand = product.find('span', attrs={'class': 'brand-name'
                                 }).get_text().replace('\n', '').strip().title()
            name = product.find('span', attrs={'class': 'name-out-brand'
                                 }).get_text().replace('\n', '').strip()
            model = extract_model_name(name)
            priceCon = product.find('div', attrs={'class': 'now-price'})
            priceSpans = priceCon.find_all('span')
            if len(priceSpans) > 1:
                price = priceSpans[1].get_text()
            else:
                price = priceSpans[0].get_text()
            # Separate currency from price
            currency_symbol, price = price[0], price[1:].replace(' ', '').replace('\n', '').replace("'", '').replace(',', '')
            
            wpriceCon = product.find('div',
                    attrs={'class': 'was-wrapper'})
            if wpriceCon:
                wpriceSpans = wpriceCon.find_all('span')
                wprice = wpriceSpans[1].get_text().replace(' ', ''
                        ).replace('\n', '').replace("'", '').replace(','
                        , '')
                wcurrency_symbol, wprice = wprice[0], wprice[1:]
                
            currency = currency_map.get(currency_symbol, "")

            self.product_pages.append((brand, model, link, price, currency))
        return self.product_pages


class MayorsProductsPage(BaseProductsPage):

    def get_products_info(self, soup):
        products = soup.find_all('div', attrs={'class': 'productTile'})
        for product in products:
            productCon = product.find('a')
            link = 'https://www.mayors.com' + productCon.get('href')
            brand = productCon.find('div',
                                    attrs={'class': 'productTileBrand'
                                    }).get_text().replace('\n', ''
                    ).replace('Pre-Owned ', '').strip().title()
            model_full = productCon.find('div',
                    attrs={'class': 'productTileName'
                    }).get_text().strip().replace('\n', '')
            model = extract_model_name(model_full)

            price_container = product.find('div', attrs={'class': 'productTilePrice'})
            # Extract price
            price = price_container.contents[0].replace('\n', '').replace('\t', '').replace(',', '').replace(' ', '')

            # Separate currency from price
            currency_symbol, price = price[0], price[1:]

            # Extract wprice
            wprice_container = price_container.find('span', attrs={'class': 'productTileWasPrice'})
            if wprice_container:
                wprice = wprice_container.get_text().replace('\n', '').replace('\t', '').replace(',', '').replace(' ', '')
                wcurrency, wprice = wprice[0], wprice[1:]
            else:
                wprice = None

            currency = currency_map.get(currency_symbol, "")

            self.product_pages.append((brand, model, link, price, currency))
        return self.product_pages
    
class ThewatchboxProductsPage(BaseProductsPage):
    def GetProductsInfo(self, soup):
        products = soup.find_all('a', attrs={"class": "link grid-carousel-link"})
        for product in products:
            link = "https://www.thewatchbox.com" + product.get('href')
            brand = product.find('div', attrs={"class": "grid__brand"}).get_text().replace("\n", "")
            model = product.find('span', attrs={"class": "grid__name"}).get_text().replace("\n", "")
            priceCon = product.find('div', attrs={"class": "grid__price"})
            price=priceCon.find('span').get_text().replace(" ", "").replace("\n", "").replace("'", "").replace(",", "")
            self.productPages.append((brand, model, link, price))

def extract_model_name(name):
    words = name.split()
    for i, word in enumerate(words):
        if word[-1] == ',':
            return ' '.join(words[:i+1]).rstrip(',')
        elif word in ['Automatic', 'Watch', 'Men\'s', 'Mens', 'Ladies','Uni','Unisex','Women\'s','Womens']:
            return ' '.join(words[:i])
        elif word in ['Dial']:
            return ' '.join(words[:i-1])
        elif word == 'mm':
            return ' '.join(words[:i-1])
        elif word[-2:] == "mm":
            word = word.replace("mm","")
            if all(char.isdigit() or char == '.' for char in word):
                return ' '.join(words[:i])
    return name