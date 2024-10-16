#!/usr/bin/python
# -*- coding: utf-8 -*-
from random import randint
import re
import requests
from playwright.sync_api import sync_playwright
import time
from django.db.models import Count
from home.models import Proxy


class BaseProductDetails:

    def __init__(self, url):
        self.url = url
        self.images = {}
        self.details = {}

    def fetch_source_code(self):
        try:
            count = Proxy.objects.filter(enable=True).aggregate(count=Count('id'))['count']
            proxies = None
    
            if count > 0:
                # Get a random proxy
                random_index = randint(0, count - 1)
                proxy = Proxy.objects.filter(enable=True)[random_index]
    
                # Use the proxy for the request
                if proxy.username and proxy.password:
                    proxy_str = f'http://{proxy.username}:{proxy.password}@{proxy.ip}:{proxy.port}'
                else:
                    proxy_str = f'http://{proxy.ip}:{proxy.port}'
    
                proxies = {'http': proxy_str, 'https': proxy_str}
    
            print(f"Fetching source code of {self.url}...")
            r = requests.get(self.url, proxies=proxies, timeout=10 )#, verify=False
            time.sleep(5)
            r.raise_for_status()  # Raise an HTTPError for bad responses
            if r.status_code == 200:
                return r.content
        except requests.exceptions.RequestException as e:
            print(f"Error: {e} {self.url}...")
            return None


class BuchererProductDetails(BaseProductDetails):
    def get_images(self, soup):
        print("Bucherer images")
        imagesLink = soup.find('div',
                               attrs={'class': 'm-product-slider__main js-m-product-slider__main'
                               }).children
        for index,imageLink in enumerate(imagesLink):
            imageTag = imageLink.find('img')
            if imageTag != -1:
                imageName = re.sub(r'[^\w\-_\.]', '', imageTag.get('alt').replace('\n', '').strip().replace(' ','_'))+ '_' + str(index + 1)
                srcset = imageTag.get('data-srcset').split(', ')
                for src in reversed(srcset):
                    try:
                        url, width = src.strip().split(' ')
                        if width == '1366w':
                            image = url
                            break
                    except ValueError:
                        continue
                self.images[imageName] = image
                break # REMOVE IT IF WANT TO GET ALL IMAGES
        return self.images

    def get_details(self, soup):
        print("Bucherer details")
        detailsCon = soup.find_all('div',attrs={'class': 'm-product-specification__item'})
        for attr in detailsCon:
            name = attr.find('span',
                             attrs={'class': 'm-product-specification__label'
                             }).get_text().replace('\n', '').strip().title()
            value = attr.find('span',
                              attrs={'class': 'm-product-specification__name'
                              }).get_text().replace('\n', '').strip()
            self.details[name] = value
        
        return self.details


class TourneauProductDetails(BaseProductDetails):
    def get_images(self, soup):
        imagesLink = soup.find_all('div',
                               attrs={'class': 'product-details__primary-slide'
                               })
        for index,imageLink in enumerate(imagesLink):
            imageTag = imageLink.find('img')
            if imageTag != -1:
                imageName = re.sub(r'[^\w\-_\.]', '', imageTag.get('alt').replace('\n', '').strip().replace(' ','_'))+ '_' + str(index + 1)
                image = imageLink.get('data-src')
                self.images[imageName] = image
                break # REMOVE IT IF WANT TO GET ALL IMAGES
            
        return self.images

    def get_details(self, soup):
        detailsCon = soup.find('div',
                                   attrs={'class': 'product-details__specs'
                                   }).find_all('li', attrs={'class': 'attribute'})
        for attr in detailsCon:
            name = attr.find('span',
                             attrs={'class': 'label'
                             }).get_text().strip().title()
            value = attr.find('span',
                              attrs={'class': 'value'
                              }).get_text().strip()
            if value:
                self.details[name] = value
        # Add description to details if it exists
        descriptionDiv = soup.find('div', attrs={'class': 'product-details__description'})  
        if descriptionDiv:
            description = descriptionDiv.find('span', attrs={'itemprop': 'description'}).get_text().strip()
            self.details['Description'] = description
        if not self.details.get('Collection'):
            product = soup.find('h1', {'class': 'product-details__product-name'})
            product_name = product.get_text(strip=True)
            brand_name = product.find('div', {'class': 'product-details__brand'}).get_text(strip=True)
            collection_name = product_name.replace(brand_name, '').replace('"', '').strip()
            self.details['Collection'] = collection_name

        return self.details


class CrownandcaliberProductDetails(BaseProductDetails):

    def get_images(self, soup):
        imagesLink = soup.find_all('div',
                               attrs={'class': 'slider--item'
                               })
        for index,imageLink in enumerate(imagesLink):
            imageTag = imageLink.find('img')
            if imageTag != -1:
                imageName = re.sub(r'[^\w\-_\.]', '', imageTag.get('alt').replace('\n', '').strip().replace(' ','_'))+ '_' + str(index + 1)
                image = "https:"+imageTag.get('src')
                self.images[imageName] = image
                break # REMOVE IT IF WANT TO GET ALL IMAGES
        return self.images

    def get_details(self, soup):
        detailsCon = soup.find('div', attrs={'class': 'prod-specs'})
        for attr in detailsCon.children:
            if attr.name == 'div':
                name_span = attr.find('span')
                value_span = attr.find('span', attrs={'class': 'list-value'})
                if name_span and value_span:
                    name = name_span.get_text().replace('\n','').replace('-','').strip()
                    value = value_span.contents[0].replace('\n','').replace("  "," ").strip()
                    self.details[name] = value
        ref_no= soup.find('span', attrs={'class': 'model-number'}).get_text().strip()
        self.details['Reference #'] = ref_no
        description_div = soup.find('div', attrs={'class': 'more-detail'})
        preowned_watch_details_h2 = description_div.find('h2', string='Preowned Watch Details')
        if preowned_watch_details_h2:
            preowned_watch_details_p = preowned_watch_details_h2.find_next_sibling('p')
            description = preowned_watch_details_p.get_text().strip()
            self.details["Description"] = description
        stock = soup.find('span', attrs={'id': 'variant-inventory'}).get_text().strip()
        if stock not in ['In stock']:
            self.details['Stock'] = False

        return self.details


class BobswatchesProductDetails(BaseProductDetails):

    def get_images(self, soup):
        imagesDiv = soup.find('div', attrs={'class': 'swiper-wrapper'})
        if imagesDiv is not None:
            imagesLink = imagesDiv.find_all('div', attrs={'class': 'swiper-slide'})  # change this line
            for index, imageLink in enumerate(imagesLink):
                imageTag = imageLink.find('img')
                if imageTag is not None:
                    imageName = re.sub(r'[^\w\-#]|(\.\s*$)|(^CON$|^PRN$|^AUX$|^NUL$|^COM[1-9]$|^LPT[1-9]$)', '', imageTag.get('alt').replace('\n', '').strip().replace(' ','_').replace('"', '')) + '_' + str(index + 1)
                    image = imageTag.get('src')
                    if not image.startswith('http'):
                        image = "https://www.bobswatches.com/" + image
                    self.images[imageName] = image
                    break # REMOVE IT IF WANT TO GET ALL IMAGES
        return self.images

    def get_details(self, soup):
        detailsCon = soup.find('div', attrs={'id': 'panel-collapseProductDetail'})
        details = detailsCon.find_all('tr')
        for attr in details:
            nameTag = attr.find('td')
            valueTag = nameTag.find_next_sibling('td') if nameTag else None
            if nameTag and valueTag and nameTag.get_text(strip=True).endswith(':'):
                name = nameTag.get_text(strip=True).rstrip(':')
                value = valueTag.get_text().replace('\n', ' ').strip()
                self.details[name] = value
        
        descriptionDiv = soup.find('div', attrs={'class': 'product-description'})
        if descriptionDiv:
            description = descriptionDiv.find('p').get_text(strip=True)
            self.details["Description"] = description
        
        # For 'Case Diameter'
        case = self.details.get('Case')
        if case:
            match = re.search(r'(\d+(\.\d+)?\s*mm)', case)
            if match:
                self.details['Case Diameter'] = match.group(1)
        
        # For 'Model Name' and 'Model Number'
        model = self.details.pop('Model Name/Number', None)
        if model:
            match = re.search(r'(.*?)(?:\sref\s|\s)(\S+)$', model)
            if match:
                # self.details['Model Name'] = match.group(1).strip()
                self.details['Model Number'] = match.group(2)
        
        return self.details


class GoldsmithsProductDetails(BaseProductDetails):

    def get_images(self, soup):
        imagesLink = soup.find_all('div',
                                   attrs={'class': 'item productImageGallery-Standard'
                                   })
        for index, imageLink in enumerate(imagesLink):
            imageTag = imageLink.find('img')
            if imageTag != -1:
                imageName = imageName = re.sub(r'[^\w\-_\.]', '', imageTag.get('alt').replace('\n', '').strip().replace(' ','_'))+ '_' + str(index + 1)
                image = imageTag.get('src')
                self.images[imageName] = image
                break # REMOVE IT IF WANT TO GET ALL IMAGES
        return self.images

    def get_details(self, soup):
        con = soup.find('div',
                        attrs={'class': 'productPageCollapsibleSectionBody productSpecification'
                        })
        detailsCon = con.find_all('li')

            # detailsCon=soup.find_all('ul',attrs={"class":"productSpecs"})[1].find_all('li')

        for attr in detailsCon:
            name = attr.find('span', attrs={'class': 'specLabel'
                             }).get_text().replace('\n', '')
            value = attr.find('span', attrs={'class': 'specValue'
                              }).get_text().replace('\n', '')
            self.details[name] = value

        # Description
        descriptionCon = soup.find('div', attrs={'id': 'productPageCollapsibleSectionBody'})
        descriptionParagraphs = descriptionCon.find_all('p')
        description = ""

        if len(descriptionParagraphs) >= 1:
            for descriptionParagraph in descriptionParagraphs:
                if descriptionParagraph.find('a'):  # Skip paragraph if it contains an 'a' tag
                    continue
                paragraph_text = descriptionParagraph.get_text().replace('\n', '').replace('"', '')
                description += paragraph_text + "\n"
        else:
            description = descriptionCon.get_text().replace('\n', '').replace('"', '')

        self.details['Description'] = description.strip()
        
        return self.details


class WatchesofswitzerlandProductDetails(BaseProductDetails):

    def get_images(self, soup):
        imagesLink = soup.find_all('div',
                                   attrs={'class': 'item productImageGallery-Standard'
                                   })
        for index, imageLink in enumerate(imagesLink):
            imageTag = imageLink.find('img')
            if imageTag != -1:
                imageName = re.sub(r'[^\w\-_\.]', '', imageTag.get('alt').replace('\n', '').strip().replace(' ','_'))+ '_' + str(index + 1)
                image = imageTag.get('src')
                self.images[imageName] = image
                break # REMOVE IT IF WANT TO GET ALL IMAGES 
        return self.images

    def get_details(self, soup):
        con = soup.find('div',
                        attrs={'class': 'productPageCollapsibleSectionBody productSpecification'
                        })
        detailsCon = con.find_all('li')

            # detailsCon=soup.find_all('ul',attrs={"class":"productSpecs"})[1].find_all('li')

        for attr in detailsCon:
            name = attr.find('span', attrs={'class': 'specLabel'
                             }).get_text().replace('\n', '')
            value = attr.find('span', attrs={'class': 'specValue'
                              }).get_text().replace('\n', '')
            self.details[name] = value

        # Description
        descriptionCon = soup.find('div', attrs={'id': 'productPageCollapsibleSectionBody'})
        descriptionParagraphs = descriptionCon.find_all('p')
        description = ""

        if len(descriptionParagraphs) >= 1:
            for descriptionParagraph in descriptionParagraphs:
                if descriptionParagraph.find('a'):  # Skip paragraph if it contains an 'a' tag
                    continue
                paragraph_text = descriptionParagraph.get_text().replace('\n', '').replace('"', '')
                description += paragraph_text + "\n"
        else:
            description = descriptionCon.get_text().replace('\n', '').replace('"', '')

        self.details['Description'] = description.strip()
        return self.details


class JomashopProductDetails(BaseProductDetails):
    def fetch_source_code(self):
        try:
            # Get count of all enabled proxies
            count = Proxy.objects.filter(enable=True).aggregate(count=Count('id'))['count']
            proxy_server = None
    
            if count > 0:
                # Get a random proxy
                random_index = randint(0, count - 1)
                proxy = Proxy.objects.filter(enable=True)[random_index]
    
                if proxy.username and proxy.password:
                    proxy_str = f'http://{proxy.username}:{proxy.password}@{proxy.ip}:{proxy.port}'
                else:
                    proxy_str = f'http://{proxy.ip}:{proxy.port}'
    
                proxy_server = {"server": proxy_str}
    
            with sync_playwright() as p:
                browser = p.chromium.launch(proxy=proxy_server)
                page = browser.new_page()
                try:
                    page.goto(self.url)
    
                    page.wait_for_selector('.guarantee-list')
                    page.wait_for_load_state('domcontentloaded')
                    
    
                    # Get the HTML after JavaScript execution
                    return page.content()
                finally:
                    browser.close()
        except Exception as e:
            print(f"Error fetching source code of {self.url}: {e}")
            return None

    def get_images(self, soup):
        imagesLink = soup.find_all('img',
                                   attrs={'class': 'slide-item-main-image'
                                   })
        for index, imageLink in enumerate(imagesLink):
            imageName = re.sub(r'[^\w\-_\.]', '', imageLink.get('title').replace('\n', '').strip().replace(' ','_'))+ '_' + str(index + 1)
            image = imageLink.get('src')
            self.images[imageName] = image
            break
        return self.images

    def get_details(self, soup):
        description = soup.find('div', attrs={'class': 'desc-content'}).get_text().replace('\n', '')

        detailsCon = soup.find_all(['a', 'div'], attrs={'class': 'more-detail-content'})
        
        for attr in detailsCon:
            name = attr.find('h4', attrs={'class': 'more-label'}).get_text().replace('\n', '').strip().title()
            value = attr.find('span', attrs={'class': 'more-value'}).get_text().replace('\n', '').strip()
            self.details[name] = value

        ref_no = self.details.pop('Model', None)
        if ref_no:
            self.details['ref_no'] = ref_no

        warranty = self.details.get('Warranty')
        if warranty:
            self.details['Warranty'] = warranty.replace('Jomashop', 'LC').strip()

        self.details['Description'] = description
        
        return self.details


class MayorsProductDetails(BaseProductDetails):

    def get_images(self, soup):
        imagesLink = soup.find_all('div',
                                   attrs={'class': 'item productImageGallery-Standard'
                                   })
        for index, imageLink in enumerate(imagesLink):
            imageTag = imageLink.find('img')
            if imageTag != -1:
                imageName = re.sub(r'[^\w\-_\.]', '', imageTag.get('alt').replace('\n', '').strip().replace(' ','_'))+ '_' + str(index + 1)
                image = imageTag.get('src')
                self.images[imageName] = image
                break # REMOVE IT IF WANT TO GET ALL IMAGES
        return self.images

    def get_details(self, soup):
        con = soup.find('div',
                        attrs={'class': 'productPageCollapsibleSectionBody productSpecification'
                        })
        detailsCon = con.find_all('li')

            # detailsCon=soup.find_all('ul',attrs={"class":"productSpecs"})[1].find_all('li')

        for attr in detailsCon:
            name = attr.find('span', attrs={'class': 'specLabel'
                             }).get_text().replace('\n', '')
            value = attr.find('span', attrs={'class': 'specValue'
                              }).get_text().replace('\n', '')
            self.details[name] = value

        # Description
        descriptionCon = soup.find('div', attrs={'id': 'productPageCollapsibleSectionBody'})
        descriptionParagraphs = descriptionCon.find_all('p')
        description = ""

        if len(descriptionParagraphs) >= 1:
            for descriptionParagraph in descriptionParagraphs:
                if descriptionParagraph.find('a'):  # Skip paragraph if it contains an 'a' tag
                    continue
                paragraph_text = descriptionParagraph.get_text().replace('\n', '').replace('"', '')
                description += paragraph_text + "\n"
        else:
            description = descriptionCon.get_text().replace('\n', '').replace('"', '')

        self.details['Description'] = description.strip()
        return self.details
