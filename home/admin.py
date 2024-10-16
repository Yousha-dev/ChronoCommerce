from .models import WoocommerceSetting, ScraperSource, ScraperUrl, Product, WoocommerceProduct, BatchSerialTracking, InventoryTracking, Image, PriceHistory, Proxy
from django.contrib import admin
from django.contrib.admin import SimpleListFilter
from django.utils.translation import gettext_lazy as _
from django.db.models import F

# Register your models here.

# class ScraperSourceAdmin(admin.ModelAdmin):
#     list_filter = ['scrape_interval', 'profit_margin', 'enable']
#     search_fields = ['name']

# class ScraperUrlAdmin(admin.ModelAdmin):
#     list_filter = ['source']
#     search_fields = ['url', 'source__name']

class ScraperUrlInline(admin.TabularInline):
    model = ScraperUrl
    extra = 0  # Number of extra forms to display

class ScraperSourceAdmin(admin.ModelAdmin):
    list_filter = ['scrape_interval', 'profit_margin', 'enable']
    search_fields = ['name']
    inlines = [ScraperUrlInline]


# class ProductAdmin(admin.ModelAdmin):
#     list_filter = ['brand', 'color', 'gender', 'currency', 'source']
#     search_fields = ['sku', 'ref_no', 'brand', 'model', 'color', 'source__name', 'url']
#     readonly_fields = ['created_at', 'last_updated']

# class WoocommerceProductAdmin(admin.ModelAdmin):
#     list_filter = ['sent_to_woocommerce', 'last_sent']
#     search_fields = ['product__sku']
#     readonly_fields = ['last_sent']

# class BatchSerialTrackingAdmin(admin.ModelAdmin):
#     # list_filter = ['batch_number']
#     search_fields = ['product__sku', 'batch_number', 'serial_number']

# class InventoryTrackingAdmin(admin.ModelAdmin):
#     list_filter = [('last_checked', admin.DateFieldListFilter),'stock_available']
#     search_fields = ['product__sku']
#     readonly_fields = ['last_checked']

# class ImageAdmin(admin.ModelAdmin):
#     list_filter = ['is_official']
#     search_fields = ['product__sku', 'image_folder']

class WoocommerceProductInline(admin.TabularInline):
    model = WoocommerceProduct
    readonly_fields = ['woocommerce_id', 'sent_to_woocommerce', 'last_sent']
    can_delete = False
    max_num = 1

    def has_delete_permission(self, request, obj=None):
        return False

class BatchSerialTrackingInline(admin.TabularInline):
    model = BatchSerialTracking
    extra = 0
    

class InventoryTrackingInline(admin.TabularInline):
    model = InventoryTracking
    readonly_fields = ['last_checked']
    max_num = 1

    def has_delete_permission(self, request, obj=None):
        return False

class ImageInline(admin.TabularInline):
    model = Image
    max_num = 1

    def has_delete_permission(self, request, obj=None):
        return False

class BrandListFilter(admin.SimpleListFilter):
    title = 'brand'
    parameter_name = 'brand'

    def lookups(self, request, model_admin):
        queryset = model_admin.model.objects.all()
        if 'brand' in request.GET:
            queryset = queryset.filter(brand=request.GET['brand'])
        if 'model' in request.GET:
            queryset = queryset.filter(model=request.GET['model'])
        if 'color' in request.GET:
            queryset = queryset.filter(color=request.GET['color'])
        if 'diameter' in request.GET:
            queryset = queryset.filter(diameter=request.GET['diameter'])
        if 'gender' in request.GET:
            queryset = queryset.filter(gender=request.GET['gender'])
        if 'source' in request.GET:
            queryset = queryset.filter(source=request.GET['source'])
        return [(brand if brand else None, brand if brand else 'Empty') for brand in queryset.values_list('brand', flat=True).distinct()]

    def queryset(self, request, queryset):
        if self.value() == 'Empty':
            return queryset.filter(brand__isnull=True)
        elif self.value():
            return queryset.filter(brand=self.value())
        else:
            return queryset

class ModelListFilter(admin.SimpleListFilter):
    title = 'model'
    parameter_name = 'model'

    def lookups(self, request, model_admin):
        queryset = model_admin.model.objects.all()
        if 'brand' in request.GET:
            queryset = queryset.filter(brand=request.GET['brand'])
        if 'model' in request.GET:
            queryset = queryset.filter(model=request.GET['model'])
        if 'color' in request.GET:
            queryset = queryset.filter(color=request.GET['color'])
        if 'diameter' in request.GET:
            queryset = queryset.filter(diameter=request.GET['diameter'])
        if 'gender' in request.GET:
            queryset = queryset.filter(gender=request.GET['gender'])
        if 'model' in request.GET:
            queryset = queryset.filter(model=request.GET['model'])
        if 'source' in request.GET:
            queryset = queryset.filter(source=request.GET['source'])
        return [(model if model else None, model if model else 'Empty') for model in queryset.values_list('model', flat=True).distinct()]

    def queryset(self, request, queryset):
        if self.value() == 'Empty':
            return queryset.filter(model__isnull=True)
        elif self.value():
            return queryset.filter(model=self.value())
        else:
            return queryset

class ColorListFilter(admin.SimpleListFilter):
    title = 'color'
    parameter_name = 'color'

    def lookups(self, request, model_admin):
        queryset = model_admin.model.objects.all()
        if 'brand' in request.GET:
            queryset = queryset.filter(brand=request.GET['brand'])
        if 'model' in request.GET:
            queryset = queryset.filter(model=request.GET['model'])
        if 'color' in request.GET:
            queryset = queryset.filter(color=request.GET['color'])
        if 'diameter' in request.GET:
            queryset = queryset.filter(diameter=request.GET['diameter'])
        if 'gender' in request.GET:
            queryset = queryset.filter(gender=request.GET['gender'])
        if 'source' in request.GET:
            queryset = queryset.filter(source=request.GET['source'])
        return [(color if color else None, color if color else 'Empty') for color in queryset.values_list('color', flat=True).distinct()]

    def queryset(self, request, queryset):
        if self.value() == 'Empty':
            return queryset.filter(color__isnull=True)
        elif self.value():
            return queryset.filter(color=self.value())
        else:
            return queryset

class GenderListFilter(admin.SimpleListFilter):
    title = 'gender'
    parameter_name = 'gender'

    def lookups(self, request, model_admin):
        queryset = model_admin.model.objects.all()
        if 'brand' in request.GET:
            queryset = queryset.filter(brand=request.GET['brand'])
        if 'model' in request.GET:
            queryset = queryset.filter(model=request.GET['model'])
        if 'color' in request.GET:
            queryset = queryset.filter(color=request.GET['color'])
        if 'diameter' in request.GET:
            queryset = queryset.filter(diameter=request.GET['diameter'])
        if 'gender' in request.GET:
            queryset = queryset.filter(gender=request.GET['gender'])
        if 'source' in request.GET:
            queryset = queryset.filter(source=request.GET['source'])
        return [(gender if gender else None, gender if gender else 'Empty') for gender in queryset.values_list('gender', flat=True).distinct()]

    def queryset(self, request, queryset):
        if self.value() == 'Empty':
            return queryset.filter(gender__isnull=True)
        elif self.value():
            return queryset.filter(gender=self.value())
        else:
            return queryset

class SourceListFilter(admin.SimpleListFilter):
    title = 'source'
    parameter_name = 'source'

    def lookups(self, request, model_admin):
        queryset = model_admin.model.objects.all()
        if 'brand' in request.GET:
            queryset = queryset.filter(brand=request.GET['brand'])
        if 'model' in request.GET:
            queryset = queryset.filter(model=request.GET['model'])
        if 'color' in request.GET:
            queryset = queryset.filter(color=request.GET['color'])
        if 'diameter' in request.GET:
            queryset = queryset.filter(diameter=request.GET['diameter'])
        if 'gender' in request.GET:
            queryset = queryset.filter(gender=request.GET['gender'])
        if 'source' in request.GET:
            queryset = queryset.filter(source=request.GET['source'])
        sources = queryset.values_list('source', flat=True).distinct()
        return [(source.id if source.id else None, source.name if source.name else 'Empty') for source in ScraperSource.objects.filter(id__in=sources)]

    def queryset(self, request, queryset):
        if self.value() == 'Empty':
            return queryset.filter(source__id__isnull=True)
        elif self.value():
            return queryset.filter(source=self.value())
        else:
            return queryset
        
class DiameterListFilter(admin.SimpleListFilter):
    title = 'diameter'
    parameter_name = 'diameter'

    def lookups(self, request, model_admin):
        queryset = model_admin.get_queryset(request)
        if 'brand' in request.GET:
            queryset = queryset.filter(brand=request.GET['brand'])
        if 'model' in request.GET:
            queryset = queryset.filter(model=request.GET['model'])
        if 'color' in request.GET:
            queryset = queryset.filter(color=request.GET['color'])
        if 'diameter' in request.GET:
            queryset = queryset.filter(diameter=request.GET['diameter'])
        if 'gender' in request.GET:
            queryset = queryset.filter(gender=request.GET['gender'])
        if 'source' in request.GET:
            queryset = queryset.filter(source=request.GET['source'])
        return [(diameter if diameter else None, diameter if diameter else 'Empty') for diameter in queryset.values_list('diameter', flat=True).distinct()]
    
    def queryset(self, request, queryset):
        if self.value() == 'Empty':
            return queryset.filter(diameter__isnull=True)
        elif self.value():
            return queryset.filter(diameter=self.value())
        else:
            return queryset

class ProductAdmin(admin.ModelAdmin):
    list_filter = [BrandListFilter, ModelListFilter, ColorListFilter, DiameterListFilter, GenderListFilter, SourceListFilter]
    search_fields = ['sku', 'ref_no', 'brand', 'model', 'color', 'diameter', 'source__name', 'url']
    readonly_fields = ['created_at', 'last_updated']
    inlines = [WoocommerceProductInline, BatchSerialTrackingInline, InventoryTrackingInline, ImageInline]

class PriceChangeFilter(SimpleListFilter):
    title = _('price change')
    parameter_name = 'price_change'

    def lookups(self, request, model_admin):
        return (
            ('positive', _('Positive')),
            ('negative', _('Negative')),
        )

    def queryset(self, request, queryset):
        if self.value() == 'positive':
            return queryset.filter(old_price__lt=F('new_price'))
        elif self.value() == 'negative':
            return queryset.filter(old_price__gt=F('new_price'))

class PriceHistoryAdmin(admin.ModelAdmin):
    list_filter = [PriceChangeFilter, ('change_date', admin.DateFieldListFilter)]
    search_fields = ['product__sku', 'change_date']
    readonly_fields = ['product', 'old_price', 'new_price', 'change_date']

class ProxyAdmin(admin.ModelAdmin):
    list_filter = ['enable']
    search_fields = ['ip']

admin.site.register(WoocommerceSetting)
admin.site.register(ScraperSource, ScraperSourceAdmin)
# admin.site.register(ScraperUrl, ScraperUrlAdmin)
admin.site.register(Product, ProductAdmin)
# admin.site.register(WoocommerceProduct, WoocommerceProductAdmin)
# admin.site.register(BatchSerialTracking, BatchSerialTrackingAdmin)
# admin.site.register(InventoryTracking, InventoryTrackingAdmin)
# admin.site.register(Image, ImageAdmin)
admin.site.register(PriceHistory, PriceHistoryAdmin)
admin.site.register(Proxy, ProxyAdmin)