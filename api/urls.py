from django.urls import re_path, path
from django.views.decorators.csrf import csrf_exempt

from api.views import *


urlpatterns = [

	re_path("product/((?P<pk>\d+)/)?", csrf_exempt(ProductView.as_view())),
    path('check_product_url/<int:woocommerce_id>/', CheckProductURLAPIView.as_view(), name='check_product_url'),

]