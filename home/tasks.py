import html
from django.conf import settings
from django.utils import timezone
from celery import shared_task
from django.db.models import Q, F
from home.models import Product, WoocommerceSetting, ScraperSource, ScraperUrl, WoocommerceProduct
from home.scraper.scraper import Scraper
from home.scraper.domain_config import domain_config
from woocommerce import API
from django.db.models import Prefetch
from django.core.mail import send_mail, BadHeaderError
from smtplib import SMTPException
import requests
import json
import os

def get_batch_counter():
        counter_folder_path = 'batch'
        os.makedirs(counter_folder_path, exist_ok=True)
        counter_file_path = os.path.join(counter_folder_path, 'batch_count.txt')
        if not os.path.exists(counter_file_path):
            with open(counter_file_path, 'w') as f:
                f.write('0')
        with open(counter_file_path, 'r') as f:
            counter = int(f.read()) + 1
        with open(counter_file_path, 'w') as f:
            f.write(str(counter))
        return counter

def get_exchange_rates(batch):
    # Fetch the currency conversion rates from the API
    url = settings.EXCHANGE_RATES_API_URL
    response = requests.get(url)
    data = response.json()
    
    os.makedirs('exchange_rates', exist_ok=True)
    # Create a filename with the batch count
    filename = f"usd_rates_{batch}.txt"
    filepath = os.path.join('exchange_rates', filename)
    # Save all the exchange rates to a text file
    with open(filepath, 'w') as f:
        json.dump(data['rates'], f)

@shared_task(bind=True)
def run_scraper(self, request):
    # Fetch all enabled ScraperSource instances
    scraper_sources = ScraperSource.objects.filter(enable=True).prefetch_related(
        Prefetch('scraperurl_set', queryset=ScraperUrl.objects.filter(enable=True))
    )
    scraper_settings = WoocommerceSetting.objects.filter(enable=True)

    batch = get_batch_counter()
    print(f"Starting batch {batch}")
    get_exchange_rates(batch)
    print("Exchange rates fetched")
    
    for source in scraper_sources:
        for scraper_url in source.scraperurl_set.all():
            url = scraper_url.url
            source_name = source.name
            config = domain_config.get(source_name)
            if config is not None:
                # Pass the filter attributes to the Scraper
                scraper = Scraper(url, source, config, batch_counter=batch, brand_filter=scraper_url.brand_filter, model_filter=scraper_url.model_filter, inverse_filter=scraper_url.inverse_filter, price_min_filter=scraper_url.price_min, price_max_filter=scraper_url.price_max)
                scraper.run()
                for settings in scraper_settings:
                    send_products_to_woocommerce(request,settings, source)

# Method to get all products that have not been sent or have been updated since the last send
def get_products_to_send(source):
    return Product.objects.filter(
        Q(woocommerce_product__sent_to_woocommerce=False) | Q(last_updated__gt=F('woocommerce_product__last_sent')),
        source=source 
    )

# Method to create a category in WooCommerce
def create_category(category_name, wcapi):
    data = {
        "name": category_name  # Keep the category name as is, without encoding
    }
    response = wcapi.post("products/categories", data)
    if response.status_code == 201:  # HTTP status code 201 means Created
        new_category = response.json()
        if 'id' in new_category:
            return new_category['id']
        else:
            print("Error: The API response does not contain an 'id' key.")
            return None
    elif response.status_code == 400:  # HTTP status code 400 means Bad Request
        error_response = response.json()
        if error_response.get('code') == 'term_exists':
            return error_response.get('data', {}).get('resource_id')
        else:
            print(f"Error: Failed to create category {category_name}. Status code: {response.status_code}")
            return None
    else:
        print(f"Error: Failed to create category {category_name}. Status code: {response.status_code}")
        return None

def get_categories(wcapi):
    category_cache = {}  
    page = 1
    while True:
        categories = wcapi.get("products/categories", params={"per_page": 100, "page": page}).json()
        for category in categories:
            decoded_name = html.unescape(category['name'])
            category_cache[decoded_name] = category['id']
            print(f"Category {decoded_name} has ID {category['id']}")
        if len(categories) < 100:  # If less than 100 categories were returned, we've reached the last page
            break
        page += 1
    return category_cache

def send_batch(wcapi, data, wc_products):
    print("Sending batch...")
    response = wcapi.post("products/batch", data)
    
    if response.status_code != 200:
        print("Failed to send batch. Status code:", response.status_code)
        # print("Response:", response.json())
        return

    response = response.json()
    updated_products = []
    # print(response)
    for i, product in enumerate(response.get('create', [])):
        db_product = wc_products[i]  # Get the corresponding WoocommerceProduct instance
        db_product.sent_to_woocommerce = True
        db_product.last_sent = timezone.now()
        db_product.woocommerce_id = product['id']  # Set the WooCommerce ID
        updated_products.append(db_product)
    for i, product in enumerate(response.get('update', [])):
        db_product = wc_products[i]  # Get the corresponding WoocommerceProduct instance
        db_product.sent_to_woocommerce = True
        db_product.last_sent = timezone.now()
        updated_products.append(db_product)
    WoocommerceProduct.objects.bulk_update(updated_products, ['sent_to_woocommerce', 'last_sent', 'woocommerce_id'])  # Update the WooCommerce ID
    print("Batch sent.")

def send_products_to_woocommerce(request,settings, source):
    print("Starting send_products_to_woocommerce function")
    wcapi = API(
        url=settings.store_url,
        consumer_key=settings.woocommerce_api_key,
        consumer_secret=settings.woocommerce_api_secret,
        wp_api=True,
        version="wc/v3",
        timeout=1000
    )
    print("API setup complete")
    products_to_send = get_products_to_send(source).select_related('woocommerce_product')
    print(f"Got {len(products_to_send)} products to send")
    data = {"create": [], "update": []}
    wc_products_batch = []  # List to hold the current batch of WoocommerceProduct instances
    category_cache = get_categories(wcapi) # Get all categories from WooCommerce
    for product in products_to_send:
        print(f"Processing product: {product.id}")
        wc_product = WoocommerceProduct.objects.get(product=product)
        product_data = wc_product.to_woocommerce_product(request)
        categories = []
        if product.brand not in category_cache:
            category_cache[product.brand] = create_category(product.brand, wcapi)
        categories.append({
            "id": category_cache[product.brand],  
            "name": product.brand
        })
        product_data["categories"] = categories  
        if wc_product.sent_to_woocommerce:
            product_data["id"] = wc_product.woocommerce_id  # Include the WooCommerce ID in the update data
            data["update"].append(product_data)
            print(f"Product {product.id} added to update list")
        else:
            data["create"].append(product_data)
            print(f"Product {product.id} added to create list")
        wc_products_batch.append(wc_product)  # Add the WoocommerceProduct instance to the current batch
        if len(data["create"]) + len(data["update"]) >= 100:
            print("Sending batch of 100 products")
            send_batch(wcapi, data, wc_products_batch)  # Send the current batch
            data = {"create": [], "update": []}
            wc_products_batch = []  # Clear the batch
    if len(data["create"]) > 0 or len(data["update"]) > 0:
        print("Sending final batch of products")
        send_batch(wcapi, data, wc_products_batch)  # Send the final batch
    print("Finished send_products_to_woocommerce function")

@shared_task(bind=True)
def send_all_products_to_woocommerce(self, request):
    print("Starting send_all_products_to_woocommerce function")
    scraper_sources = ScraperSource.objects.filter(enable=True)
    scraper_settings = WoocommerceSetting.objects.filter(enable=True)
    for settings in scraper_settings:
        print("Setting up API for store: ", settings.store_url)
        wcapi = API(
            url=settings.store_url,
            consumer_key=settings.woocommerce_api_key,
            consumer_secret=settings.woocommerce_api_secret,
            wp_api=True,
            version="wc/v3",
            timeout=1000
        )
        print("API setup complete for store: ", settings.store_url)
        scraper_sources = ScraperSource.objects.all()
        category_cache = get_categories(wcapi) # Get all categories from WooCommerce
        for scraper_source in scraper_sources:
            print(f"Processing source: {scraper_source.id}")
            all_products = Product.objects.filter(source=scraper_source)
            print(f"Got {len(all_products)} products to send for source: {scraper_source.id}")
            data = {"create": [], "update": []}
            wc_products_batch = []  # List to hold the current batch of WoocommerceProduct instances
            for product in all_products:
                print(f"Processing product: {product.id}")
                try:
                    wc_product = WoocommerceProduct.objects.get(product=product)
                except WoocommerceProduct.DoesNotExist:
                    continue
                product_data = wc_product.to_woocommerce_product(request)
                categories = []
                if product.brand not in category_cache:
                    category_cache[product.brand] = create_category(product.brand, wcapi)
                categories.append({
                    "id": category_cache[product.brand],  
                    "name": product.brand
                })
                product_data["categories"] = categories  
                if wc_product.sent_to_woocommerce and wc_product.woocommerce_id > 0:
                    product_data["id"] = wc_product.woocommerce_id  # Include the WooCommerce ID in the update data
                    data["update"].append(product_data)
                    print(f"Product {product.id} added to update list")
                else:
                    data["create"].append(product_data)
                    print(f"Product {product.id} added to create list")
                wc_products_batch.append(wc_product)  # Add the WoocommerceProduct instance to the current batch
                if len(data["create"]) + len(data["update"]) >= 100:
                    print("Sending batch of 100 products")
                    send_batch(wcapi, data, wc_products_batch)  # Send the current batch
                    data = {"create": [], "update": []}
                    wc_products_batch = []  # Clear the batch
            if len(data["create"]) > 0 or len(data["update"]) > 0:
                print("Sending final batch of products")
                send_batch(wcapi, data, wc_products_batch)  # Send the final batch
    print("Finished send_all_products_to_woocommerce function")

@shared_task(bind=True)
def remove_all_products_from_woocommerce(self, request=None):
    scraper_settings = WoocommerceSetting.objects.filter(enable=True)
    for settings in scraper_settings:
        print("Starting remove_all_products_from_woocommerce function")
        wcapi = API(
            url=settings.store_url,
            consumer_key=settings.woocommerce_api_key,
            consumer_secret=settings.woocommerce_api_secret,
            wp_api=True,
            version="wc/v3",
            timeout=60
        )
        print("API setup complete")
        wc_products = WoocommerceProduct.objects.filter(sent_to_woocommerce=True)
        print(f"Got {len(wc_products)} products to remove")
        for i in range(0, len(wc_products), 100):
            batch = wc_products[i:i+100]
            ids_to_delete = [wc_product.woocommerce_id for wc_product in batch]
            print("Deleting batch of products: ", ids_to_delete)
            data = {
                "delete": ids_to_delete
            }
            response = wcapi.post("products/batch", data)
            if response.status_code == 200:  # HTTP status code 200 means OK
                for wc_product in batch:
                    wc_product.sent_to_woocommerce = False
                    wc_product.woocommerce_id = None
                    wc_product.last_sent = None
                    wc_product.save()
                print(f"Batch of {len(batch)} products removed successfully")
            else:
                print(f"Error: Failed to remove batch of products. Status code: {response.status_code}")
                # print(f"Response body: {response.text}")
                for wc_product in batch:
                    wc_product.sent_to_woocommerce = False
                    wc_product.woocommerce_id = None
                    wc_product.last_sent = None
                    wc_product.save()
                print(f"Batch of {len(batch)} products removed successfully")
        print("Finished remove_all_products_from_woocommerce function")