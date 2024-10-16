from http import HTTPStatus
from django.http import Http404, JsonResponse
from rest_framework import status
import requests
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.generics import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from django.db.models import Count
from random import randint
from django.utils import timezone
from api.serializers import *
from home.models import Proxy, WoocommerceSetting, WoocommerceProduct
from woocommerce import API

try:

    from home.models import Product

except:
    pass

class CheckProductURLAPIView(APIView):
    def get(self, request, woocommerce_id, format=None):
        try:
            wc_product = WoocommerceProduct.objects.get(woocommerce_id=woocommerce_id)
        except WoocommerceProduct.DoesNotExist:
            return JsonResponse({'error': 'Product not found'}, status=status.HTTP_404_NOT_FOUND)
    
        proxies=None
        try:
            count = Proxy.objects.filter(enable=True).aggregate(count=Count('id'))['count']
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
    
            response = requests.get(wc_product.product.url, proxies=proxies, timeout=10, verify=False)
            if response.status_code == 200:
                return JsonResponse({'accessible': True})
            else:
                scraper_settings = WoocommerceSetting.objects.filter(enable=True)
                for settings in scraper_settings:
                    print("Starting remove_all_products_from_woocommerce function")
                    wcapi = API(
                        url=settings.store_url,
                        consumer_key=settings.woocommerce_api_key,
                        consumer_secret=settings.woocommerce_api_secret,
                        wp_api=True,
                        version="wc/v3",
                        timeout=30
                    )
                    # Update the InventoryTracking model
                    inventory_tracking = InventoryTracking.objects.get(product=wc_product.product)
                    inventory_tracking.stock_available = False
                    inventory_tracking.last_checked = timezone.now()
                    inventory_tracking.save()
                    
                    # Update the WooCommerce product
                    wcapi.put(f"products/{wc_product.woocommerce_id}", {'stock_status': 'outofstock'})

                return JsonResponse({'accessible': False})
        except (requests.exceptions.RequestException, ValueError) as e:
            return JsonResponse({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ProductView(APIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ProductSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(data={
                **serializer.errors,
                'success': False
            }, status=HTTPStatus.BAD_REQUEST)
        serializer.save()
        return Response(data={
            'message': 'Record Created.',
            'success': True
        }, status=HTTPStatus.OK)

    def get(self, request, pk=None):
        if not pk:
            return Response({
                'data': [ProductSerializer(instance=obj).data for obj in Product.objects.all()],
                'success': True
            }, status=HTTPStatus.OK)
        try:
            obj = get_object_or_404(Product, pk=pk)
        except Http404:
            return Response(data={
                'message': 'object with given id not found.',
                'success': False
            }, status=HTTPStatus.NOT_FOUND)
        return Response({
            'data': ProductSerializer(instance=obj).data,
            'success': True
        }, status=HTTPStatus.OK)

    def put(self, request, pk):
        try:
            obj = get_object_or_404(Product, pk=pk)
        except Http404:
            return Response(data={
                'message': 'object with given id not found.',
                'success': False
            }, status=HTTPStatus.NOT_FOUND)
        serializer = ProductSerializer(instance=obj, data=request.data, partial=True)
        if not serializer.is_valid():
            return Response(data={
                **serializer.errors,
                'success': False
            }, status=HTTPStatus.BAD_REQUEST)
        serializer.save()
        return Response(data={
            'message': 'Record Updated.',
            'success': True
        }, status=HTTPStatus.OK)

    def delete(self, request, pk):
        try:
            obj = get_object_or_404(Product, pk=pk)
        except Http404:
            return Response(data={
                'message': 'object with given id not found.',
                'success': False
            }, status=HTTPStatus.NOT_FOUND)
        obj.delete()
        return Response(data={
            'message': 'Record Deleted.',
            'success': True
        }, status=HTTPStatus.OK)

