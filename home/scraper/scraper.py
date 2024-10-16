#!/usr/bin/python
# -*- coding: utf-8 -*-
import hashlib
import re
from shutil import copyfileobj
import traceback
from bs4 import BeautifulSoup
import json
import os
import logging
from datetime import datetime
from django.conf import settings
from django.utils import timezone
import requests
from home.models import Product, BatchSerialTracking, InventoryTracking, Image, WoocommerceProduct
from decimal import ROUND_UP, Decimal
from django.core.mail import send_mail, BadHeaderError
from smtplib import SMTPException
from django.db import transaction
# from home.scraper.domain_config import domain_config

# https://www.bucherer.com/buy-watches?srule=Global+sorting+rule&start=0&sz=48   
# https://www.tourneau.com/watches/brands/tudor/          
# https://www.crownandcaliber.com/collections/shop-for-watches   
# https://www.bobswatches.com/luxury-watches/    
# https://www.goldsmiths.co.uk/c/Watches?q=&sort=  
# https://www.watchesofswitzerland.com/c/Watches/Mens-Watches
# https://www.jomashop.com/watches.html
# https://www.mayors.com/c/Watches

class Scraper:
    def __init__(self, url, source, config, batch_counter, brand_filter=None, model_filter=None, inverse_filter=False, price_min_filter=None, price_max_filter=None):
        self.url = url
        self.source = source
        self.config = config
        self.brand_filter = brand_filter
        self.model_filter = model_filter
        self.inverse_filter = inverse_filter
        self.price_min_filter = price_min_filter
        self.price_max_filter = price_max_filter
        self.ProductsPageClass = config["ProductsPageClass"]
        self.ProductDetailsClass = config["ProductDetailsClass"]
        self.counter = 1
        self.batch_counter = batch_counter
    
    def send_error_email(self, error_message):
        try:
            send_mail(
                'Error Occurred',
                f'An error occurred on scraping tool: {error_message}',
                settings.EMAIL_HOST_USER,
                ['youshamasood53@gmail.com'],
                fail_silently=False
            )
            print("Error email sent successfully.")
        except (BadHeaderError, SMTPException) as e:
            print(f"Failed to send error email: {e}")


    def fetch_source_code(self, instance):
        try:
            logging.info(f"Fetching source code")
            return instance.fetch_source_code()
        except AttributeError as e:
            self.send_error_email(f"Error fetching source code: {e}")
            logging.error(f"Error fetching source code: {e}")
            return None
    
    def fetch_product_info(self, instance, soup):
        try:
            logging.info(f"Fetching product info")
            return instance.get_products_info(soup)
        except AttributeError as e:
            self.send_error_email(f"Error fetching product info: {e}")
            logging.error(f"Error fetching product info: {e}")
            return None

    def fetch_images(self, instance, soup):
        try:
            logging.info(f"Fetching images")
            return instance.get_images(soup)
        except AttributeError as e:
            self.send_error_email(f"Error fetching images: {e}")
            logging.error(f"Error fetching images: {e}")
            return None

    def fetch_details(self, instance, soup):
        try:
            logging.info(f"Fetching details")
            return instance.get_details(soup)
        except AttributeError as e:
            self.send_error_email(f"Error fetching details: {e}")
            logging.error(f"Error fetching details: {e}")
            return None
        
    def convert_to_usd(self, amount, from_currency, batch_counter):
        # Load the exchange rates from the text file
        filename = f"usd_rates_{batch_counter}.txt"
        filepath = os.path.join('exchange_rates', filename)
        with open(filepath, 'r') as f:
            rates = json.load(f)
        usd_rate = rates.get(from_currency, 1)  # Use 1 as the default rate for USD
    
        usd_rate = Decimal(usd_rate)
        # Convert the rate to a Decimal
        converted_amount = (amount / usd_rate).quantize(Decimal('0.01'), rounding=ROUND_UP)
        return converted_amount  # Divide the amount by the rate to convert to USD


    def get_diameter(self, details):
        try:
            diameter_str = details.get("Diameter", "")
            if not diameter_str:
                return None, None
            
            diameter_elements = diameter_str.split(" ")
            # If there are 3 or more elements, only keep the first two
            if len(diameter_elements) >= 3:
                diameter_str = " ".join(diameter_elements[:2])
            _diameter = re.findall(r'(\d+(\.\d+)?)|([a-zA-Z]+)', diameter_str)
            _diameter = [item[0] or item[2] for item in _diameter]
            diameter = Decimal(_diameter[0]) if _diameter[0] else '0'
            measurement_unit = _diameter[1].strip() if len(_diameter) > 1 else "mm"
            # Convert diameter from inches to millimeters
            if measurement_unit.lower() == "inches":
                diameter = diameter * Decimal(25.4)
                measurement_unit = "mm"
        except (ValueError, AttributeError, TypeError) as e:
            diameter = None
            measurement_unit = None
        return diameter, measurement_unit
    
    def update_existing_product(self, product, price, warranty, warranty_extension, return_timeline, stock_available):
        is_updated = False  # Flag to check if any field is updated
        # If product exists, update price if it has changed
        if product.price != price:
            product.price = price
            is_updated = True
        batch_serial_tracking = BatchSerialTracking.objects.get(product=product)
        # If BatchSerialTracking exists, update warranty and return timeline if they have changed
        if batch_serial_tracking.warranty != warranty:
            batch_serial_tracking.warranty = warranty
            is_updated = True
        if batch_serial_tracking.warranty_extension != warranty_extension:
            batch_serial_tracking.warranty_extension = warranty_extension
            is_updated = True
        if batch_serial_tracking.return_timeline != return_timeline:
            batch_serial_tracking.return_timeline = return_timeline
            is_updated = True
    
        inventory_tracking = InventoryTracking.objects.get(product=product)
        if inventory_tracking.stock_available != stock_available:
            inventory_tracking.stock_available = stock_available
            is_updated = True
        inventory_tracking.last_checked = timezone.now()
        inventory_tracking.save()
    
        # Update last_updated and save product after all updates if any field is updated
        if is_updated:
            now = timezone.now()
            batch_number = f"{now.month:02d}{now.day:02d}-{self.batch_counter:06d}"
            batch_serial_tracking.batch_number = batch_number
            batch_serial_tracking.save()
            product.last_updated = timezone.now()
            product.save()
    
    def create_new_product(self, url, brand, model, price, currency, details, images, warranty, warranty_extension, return_timeline, stock_available):
        # Now assign the variables
        ref_no = details.get("Reference #").strip()  # getting reference number
        gender = details.get("Gender", None)
        material = details.get("Material", None) 
        if material:
            material = re.sub(r'\(.*?\)', '', material).strip()
        color = details.get("Color", None)
        if color:
            color = re.sub(r'\(.*?\)', '', color).strip()
        description = details.pop("Description", None)

        details.pop("SKU", "")  # Remove the SKU key from the details
        details.pop("Serial", "")  # Remove the Serial number key from the details
        details.pop("Department", "")  # Remove the Department key from the details
        details.pop("Category", "")  # Remove the Category key from the details
        details.pop("Regular Price", "")  # Remove the Regular Price key from the details

        diameter, measurement_unit = self.get_diameter(details)
        if diameter != None:
            details["Diameter"] = f"{diameter} {measurement_unit}"
        
    
        details_json = json.dumps(details)
        
        # Create product
        product = Product(
            ref_no=ref_no,
            brand=brand,
            model=model,
            color=color,
            material=material, 
            diameter=diameter, 
            measurement_unit=measurement_unit, 
            gender=gender, 
            profit_margin=0.00,
            price=price,
            currency=currency, 
            description=description,
            details=details_json,
            source=self.source,
            url=url
        )
        product.save()
    
        # Create WoocommerceProduct
        woocommerce_product = WoocommerceProduct(
            product=product,
            sent_to_woocommerce=False
        )
        woocommerce_product.save()
    
        # Create Images
        self.save_images(product, images)
    
        # Create BatchSerialTracking
        self.create_batch_serial_tracking(product, warranty, warranty_extension, return_timeline)
    
        # Create InventoryTracking
        self.create_inventory_tracking(product, stock_available)
    
    def save_images(self, product, images):
        safe_ref_no = re.sub(r'[<>:"/\\|?*#%{}^~[\]` ]', '_', product.ref_no)
        dir_path = os.path.join(settings.MEDIA_ROOT, 'images', safe_ref_no)
        image_files = []  # Create an empty list to store image filenames
        for image_name, image_url in images.items():  # Loop over each image
            try:
                file_path = os.path.join(dir_path, f'{image_name}.jpg')  # Create a file path for the image
                if not os.path.exists(file_path):  # Check if the image file already exists
                    response = requests.get(image_url, stream=True)  # Fetch the image
                    response.raise_for_status()  # Raise an exception if the request failed
                    os.makedirs(dir_path, exist_ok=True)  # Create the directories if they don't exist
                    with open(file_path, 'wb') as file:  # Open the image file in write mode
                        copyfileobj(response.raw, file)  # Save the image
                    response.raw.decode_content = True  # Reset the response raw stream position to the beginning
                image_files.append(f'{image_name}.jpg')  # Add the filename to the list
            except Exception as e:
                self.send_error_email(f"Error storing images: {e}")
                logging.error(f"Error storing images: {e}")
                continue  # Continue with the next iteration of the loop

        # Create a single Images record for all images
        image_tb = Image(
            product=product,
            images=json.dumps(image_files),  # Convert the list of filenames to a JSON string
            is_official=False  # Add real data when available
        )
        image_tb.save()  # Save the Image record
    
    def create_batch_serial_tracking(self, product, warranty, warranty_extension, return_timeline):
        now = timezone.now()
        batch_number = f"{now.month:02d}{now.day:02d}-{self.batch_counter:06d}"
        product_id = str(product.id).zfill(6)
        # Create BatchSerialTracking
        batch_serial_tracking = BatchSerialTracking(
            product=product,
            batch_number=batch_number,
            serial_number=f"SN{product_id}",  # Use the padded product id as the serial number
            warranty=warranty,  # Add real data when available
            warranty_extension=warranty_extension,
            return_timeline=return_timeline  # Add real data when available
        )
        batch_serial_tracking.save()
    
    def create_inventory_tracking(self, product, stock_available):
        # Create InventoryTracking
        inventory_tracking = InventoryTracking(
            product=product,
            stock_available=stock_available  # Add real data when available
        )
        inventory_tracking.save()
    
    def insert_into_db(self, data):
        print(data)
        logging.info(f"Attempting to save to database")
        product = None
        try:
            with transaction.atomic():
                url, brand, model, price, currency, details, images, warranty, warranty_extension, return_timeline, stock_available = data
                try:
                    product = Product.objects.get(url=url)
                    self.update_existing_product(product, price, warranty, warranty_extension, return_timeline, stock_available)
                except (Product.DoesNotExist, BatchSerialTracking.DoesNotExist, InventoryTracking.DoesNotExist):
                    self.create_new_product(url, brand, model, price, currency, details, images, warranty, warranty_extension, return_timeline, stock_available)
        except Exception as e:
            self.send_error_email(f"Error saving to database: {e}")
            logging.error(f"Error saving to database: {e}")
            logging.error(traceback.format_exc())
            return False
        logging.info(f"Product {self.counter} Successfully saved to database")
        return True

    def process_product(self, product):
        print(product)  
        (brand, model, url, price, currency) = product
        logging.info(f"Product {self.counter}: Processing {url}")

        price = Decimal(price)
        if currency != 'USD':
            price = self.convert_to_usd(price, currency, self.batch_counter)
            currency = 'USD'

        # Check if the product matches the filter attributes
        if self.brand_filter is not None and brand != "":
            brands = [b.strip() for b in self.brand_filter.split(',')]
            if (self.inverse_filter and brand in brands) or (not self.inverse_filter and brand not in brands):
                logging.info(f"{brand} Brand filter unmatched")
                return
        if self.model_filter is not None and model != "":
            models = [m.strip() for m in self.model_filter.split(',')]
            if (self.inverse_filter and model in models) or (not self.inverse_filter and model not in models):
                logging.info(f"{model} Model filter unmatched")
                return
        if self.price_min_filter is not None and price < self.price_min_filter:
            logging.info(f"{self.price_min} Minimum Price filter unmatched")
            return
        if self.price_max_filter is not None and price > self.price_max_filter:
            logging.info(f"{self.price_max} Maximum Price filter unmatched")
            return
        
        product_detail_instance = self.ProductDetailsClass(url)
        source_code = self.fetch_source_code(product_detail_instance)
        if source_code is None:
            self.send_error_email("Can't access url "+ url)
            logging.error(f"Can't access url")
            return

        soup = BeautifulSoup(source_code, 'lxml')
        # print(soup)

        details = self.fetch_details(product_detail_instance, soup)
        if details is None:
            self.send_error_email("Can't access details "+ url)
            logging.error(f"Can't access details")
            return
        
        # Update the keys in details that are present in self.config
        for config_key, value in self.config.items():
            if value in details:
                details[config_key] = details.pop(value)
        
        brand_details = details.get("Brand", "").title()
        if not brand_details:
            details["Brand"] = brand
        else:
            brand = brand_details

        if self.brand_filter is not None:
            brands = [b.strip() for b in self.brand_filter.split(',')]
            if (self.inverse_filter and brand in brands) or (not self.inverse_filter and brand not in brands):
                logging.info(f"{brand} Brand filter unmatched")
                return
        
        model_details = details.get("Model", "").title()
        if not model_details:
            details["Model"] = model
        else:
            model = model_details

        if self.model_filter is not None:
            models = [m.strip() for m in self.model_filter.split(',')]
            if (self.inverse_filter and model in models) or (not self.inverse_filter and model not in models):
                logging.info(f"{model} Model filter unmatched")
                return
        
        images = self.fetch_images(product_detail_instance, soup)
        if images is None:
            self.send_error_email("Can't access images "+ url)
            logging.error(f"Can't access images")

        warranty = details.pop("Warranty","")
        warranty_extension = details.pop("Warranty Extension","")
        return_timeline = details.pop("Return Timeline","") 
        stock_available=details.pop("Stock",True)
        
        data = [url, brand, model, price, currency, details, images, warranty, warranty_extension, return_timeline, stock_available]
        self.insert_into_db(data)

        # Increment the counter
        self.counter += 1

    def run(self):
        # Get the current date and time
        now = datetime.now()

        # Format it as a string
        now_str = now.strftime("%Y-%m-%d_%H-%M-%S")

        # Create the logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.makedirs('logs')

        # Use it in the log filename
        logging.basicConfig(filename=f'logs/scraper_{now_str}.log', level=logging.INFO)
        productsPageInstance = self.ProductsPageClass(self.url)
        logging.info(f"Starting scraping from {self.url}")

        source_code = self.fetch_source_code(productsPageInstance)
        
        if source_code is None:
            logging.warning("Source code is None. Returning.")
            return
        
        soup = BeautifulSoup(source_code, 'lxml')
        # print(soup)
        pages = self.fetch_product_info(productsPageInstance, soup)
        if pages is None or len(pages) == 0:  # Check if pages is None or an empty list
            logging.warning("No products or Pages is empty list. Returning.")
            return
        logging.info(f"Starting scraping from each product page of {self.url}")
        for product in pages:
            try:
                self.process_product(product)
            except Exception as e:
                self.send_error_email(f"Error processing product: {e}")
                logging.error(f"Error processing product {product}: {e}")
                logging.error(traceback.format_exc())

    @staticmethod
    def hash_to_two_digit(input_string):
        hash_object = hashlib.sha256(input_string.encode())
        hex_dig = hash_object.hexdigest()
        return int(hex_dig, 16) % 100  # Convert to 2-digit number