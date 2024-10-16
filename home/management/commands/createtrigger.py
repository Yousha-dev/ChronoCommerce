from django.core.management.base import BaseCommand
from django.db import connection

class Command(BaseCommand):
    help = 'Create database trigger'

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TRIGGER track_price_change
                AFTER UPDATE ON home_product
                WHEN OLD.price != NEW.price
                BEGIN
                    INSERT INTO home_pricehistory(product_id, old_price, new_price, change_date)
                    VALUES (NEW.id, OLD.price, NEW.price, datetime('now'));
                END;
            """)