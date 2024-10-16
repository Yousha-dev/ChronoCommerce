from rest_framework import serializers
from home.models import Product, Image, InventoryTracking, BatchSerialTracking

class ImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Image
        fields = ['images', 'is_official']

class InventoryTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = InventoryTracking
        fields = ['stock_available']

class BatchSerialTrackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = BatchSerialTracking
        fields = ['batch_number', 'serial_number', 'warranty', 'return_timeline']

class ProductSerializer(serializers.ModelSerializer):
    image = ImageSerializer(many=True, read_only=True)
    inventory_tracking = InventoryTrackingSerializer(many=True, read_only=True)
    batch_serial_tracking = BatchSerialTrackingSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = ['sku', 'ref_no', 'brand', 'model', 'color', 'diameter', 'gender', 'measurement_unit', 'price', 'currency', 'details', 'source', 'url', 'image', 'inventory_tracking', 'batch_serial_tracking']