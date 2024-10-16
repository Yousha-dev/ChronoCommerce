import json
import os
import shutil
from urllib.parse import urljoin
from django.conf import settings
from django.db import connection, models
from woocommerce import API
# Create your models here.
    
class WoocommerceSetting(models.Model):
    store_url = models.CharField(max_length=2083)
    woocommerce_api_key = models.CharField(max_length=255, unique=True)
    woocommerce_api_secret = models.CharField(max_length=255, unique=True)
    enable = models.BooleanField(default=True)

    def __str__(self):
        return self.store_url

class ScraperSource(models.Model):
    name = models.CharField(max_length=255, unique=True)
    scrape_interval = models.IntegerField(default=24)
    profit_margin = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    MARGIN_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed'),
    ]
    margin_type = models.CharField(max_length=10, choices=MARGIN_CHOICES, default='percentage')
    warranty = models.TextField(blank=True)
    warranty_extension = models.TextField(blank=True)
    return_timeline = models.TextField(blank=True)
    enable = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class ScraperUrl(models.Model):
    url = models.CharField(max_length=2083, unique=True)
    source = models.ForeignKey(ScraperSource, on_delete=models.CASCADE)
    enable = models.BooleanField(default=True)
    brand_filter = models.CharField(max_length=255, null=True, blank=True)
    model_filter = models.CharField(max_length=255, null=True, blank=True)
    inverse_filter = models.BooleanField(default=False)  
    price_min = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    price_max = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    def __str__(self):
        return self.url[:50]+"..." if len(self.url) > 50 else self.url

class Product(models.Model):
    sku = models.CharField(max_length=255, unique=True, null=False, blank=False)
    ref_no = models.CharField(max_length=100, null=False, blank=False)
    brand = models.CharField(max_length=255 , null=False, blank=False)
    model = models.CharField(max_length=255, null=False, blank=False)
    color = models.CharField(max_length=50, null=True, blank=True)
    material = models.CharField(max_length=50, null=True, blank=True)
    diameter = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    measurement_unit = models.CharField(max_length=6, null=True, blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=False, blank=False)
    currency = models.CharField(max_length=3, null=False, blank=False)
    gender = models.CharField(max_length=15, null=True, blank=True)
    profit_margin = models.DecimalField(max_digits=10, decimal_places=2)
    MARGIN_CHOICES = [
        ('percentage', 'Percentage'),
        ('fixed', 'Fixed'),
    ]
    margin_type = models.CharField(max_length=10, choices=MARGIN_CHOICES, default='percentage')
    source = models.ForeignKey(ScraperSource, on_delete=models.CASCADE, null=False, blank=False)
    url = models.CharField(max_length=2083, unique=True, null=False, blank=False)
    description = models.TextField(null=True, blank=True)
    details = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.sku:
            sku_parts = ['LC', 
             (self.brand.replace(' ', '_') if self.brand else ''), 
             (self.color.replace(' ', '_') if self.color else ''), 
             (str(self.diameter) if self.diameter is not None else '') + (self.measurement_unit if self.measurement_unit is not None else ''), 
             str(self.id).zfill(6)]
            self.sku = '-'.join(part for part in sku_parts if part)
            super().save(*args, **kwargs)

    def __str__(self):
        return (" ".join(part for part in [self.brand, self.model, self.color, str(self.diameter) + self.measurement_unit if self.diameter and self.measurement_unit else None] if part))+' '+self.sku

class WoocommerceProduct(models.Model):
    product = models.OneToOneField(Product, related_name='woocommerce_product', on_delete=models.CASCADE)
    woocommerce_id = models.IntegerField(null=True, blank=True) 
    sent_to_woocommerce = models.BooleanField(default=False)
    last_sent = models.DateTimeField(null=True, blank=True)

    def to_woocommerce_product(self,request):
        images = []
        imageModel=self.product.images.filter(is_official=True).first()
        if imageModel:
            # Get the directory path from the image_folder field
            dir_path = '/media/images/'+self.product.ref_no
            image_files = json.loads(imageModel.images)
            for image_file in image_files:
                # Replace the \ with / and remove the media part of the path
                url_path = dir_path + '/' + image_file
                print("url path: "+ url_path)
                image_name = os.path.splitext(image_file)[0].replace('_', ' ')
                print(str(request.build_absolute_uri(url_path)))
                #hello
                images.append({
                    "src": str(request.build_absolute_uri(url_path)),
                    "name": image_name,
                    "alt": image_name
                })
    
        attributes = []
        details = json.loads(self.product.details)
        for key, value in details.items():
            attributes.append({
                "name": key,
                "options": [value],
                "visible": "true"
            })
        tracking = self.product.batch_serial_tracking.first()
        scraper_source = self.product.source
        if tracking is not None:
            attributes.append({
                "name": "Batch Number",
                "options": [tracking.batch_number],
                "visible": "true"
            })
            attributes.append({
                "name": "Serial Number",
                "options": [tracking.serial_number],
                "visible": "true"
            })
            warranty = tracking.warranty if tracking.warranty != '' else scraper_source.warranty
            warranty_extension = tracking.warranty_extension if tracking.warranty_extension != '' else scraper_source.warranty_extension
            return_timeline = tracking.return_timeline if tracking.return_timeline != '' else scraper_source.return_timeline
            
            if warranty != '':
                attributes.append({
                    "name": "Warranty",
                    "options": [warranty],
                    "visible": "true"
                })
            if warranty_extension != '':
                attributes.append({
                    "name": "Warranty Extension",
                    "options": [warranty_extension],
                    "visible": "true"
                })
            if return_timeline != '':
                attributes.append({
                    "name": "Return Timeline",
                    "options": [return_timeline],
                    "visible": "true"
                })
        profit_margin = self.product.profit_margin if self.product.profit_margin != 0.00 else self.product.source.profit_margin
        if self.product.margin_type == 'percentage':
            regular_price = self.product.price + self.product.price * (profit_margin / 100)
        elif self.product.margin_type == 'fixed':
            regular_price = self.product.price + profit_margin
        return {
            "name": " ".join(part for part in [self.product.brand, self.product.model, self.product.color, str(self.product.diameter) + self.product.measurement_unit if self.product.diameter and self.product.measurement_unit else None] if part),
            "type": "simple",
            "regular_price": str(regular_price),
            "description": self.product.description,
            "sku": self.product.sku,
            "images": images,
            "attributes": attributes,
            "stock_status": 'instock' if self.product.inventory_tracking.first().stock_available else 'outofstock',
            # Add other fields as needed
        }
    
    def delete(self, *args, **kwargs):
        # Initialize the WooCommerce API client
        scraper_settings = WoocommerceSetting.objects.filter(enable=True)
        for settings in scraper_settings:
            print("Starting remove_all_products_from_woocommerce function")
            wcapi = API(
                url=settings.store_url,
                consumer_key=settings.woocommerce_api_key,
                consumer_secret=settings.woocommerce_api_secret,
                wp_api=True,
                version="wc/v3",
                timeout=10
            )
            # Delete the product from WooCommerce   
            wcapi.delete(f"products/{self.woocommerce_id}")
            # Call the superclass's delete method
        super().delete(*args, **kwargs)
    
    def __str__(self):
        return ''
    

class BatchSerialTracking(models.Model):
    product = models.ForeignKey(Product, related_name='batch_serial_tracking', on_delete=models.CASCADE)
    batch_number = models.CharField(max_length=14)
    serial_number = models.CharField(max_length=50,unique=True)
    warranty = models.TextField(blank=True)
    warranty_extension = models.TextField(blank=True)
    return_timeline = models.TextField(blank=True)

    def __str__(self):
        return ''

class InventoryTracking(models.Model):
    product = models.ForeignKey(Product, related_name='inventory_tracking', on_delete=models.CASCADE)
    stock_available = models.BooleanField(default=True)
    last_checked = models.DateTimeField(auto_now=True)

    def __str__(self):
        return ''

class Image(models.Model):
    product = models.ForeignKey(Product, related_name='images', on_delete=models.CASCADE)
    images = models.TextField(null=True, blank=True)
    is_official = models.BooleanField(default=False)
    
    def __str__(self):
        return ''

class PriceHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    old_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    new_price = models.DecimalField(max_digits=10, decimal_places=2)
    change_date = models.DateTimeField(auto_now=True)

    def price_change(self):
        if self.old_price == 0:
            return 0
        return ((self.new_price - self.old_price) / self.old_price) * 100

    def __str__(self):
        return self.product.sku
    
class Proxy(models.Model):
    ip = models.GenericIPAddressField()
    port = models.IntegerField()
    username = models.CharField(max_length=255,null=True,blank=True)
    password = models.CharField(max_length=255,null=True,blank=True)
    enable = models.BooleanField(default=True)

    def __str__(self):
        return self.ip
    