from datetime import datetime,timedelta
from django.urls import reverse
import statistics
from django.urls import reverse
from django.utils import timezone  # Add this line
import math
from django.http import HttpResponse, HttpResponseRedirect, JsonResponse
from django.shortcuts import render, redirect
from home.forms import RegistrationForm, LoginForm, UserPasswordChangeForm, UserPasswordResetForm, UserSetPasswordForm
from django.contrib.auth.views import LoginView, PasswordChangeView, PasswordResetConfirmView, PasswordResetView
from django.views.generic import CreateView
from django.contrib.auth import logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from dateutil.relativedelta import relativedelta
from .tasks import run_scraper, send_all_products_to_woocommerce, remove_all_products_from_woocommerce
from django.views.decorators.http import require_GET
from django.db.models import Avg, Count, F, FloatField, Case, When
from django.db.models.functions import ExtractMonth
from .models import *

# Authentication
class UserRegistrationView(CreateView):
  template_name = 'accounts/auth-signup.html'
  form_class = RegistrationForm
  success_url = '/accounts/login/'

class UserLoginView(LoginView):
  template_name = 'accounts/auth-signin.html'
  form_class = LoginForm

class UserPasswordResetView(PasswordResetView):
  template_name = 'accounts/auth-reset-password.html'
  form_class = UserPasswordResetForm

class UserPasswrodResetConfirmView(PasswordResetConfirmView):
  template_name = 'accounts/auth-password-reset-confirm.html'
  form_class = UserSetPasswordForm

class UserPasswordChangeView(PasswordChangeView):
  template_name = 'accounts/auth-change-password.html'
  form_class = UserPasswordChangeForm

def logout_view(request):
  logout(request)
  return redirect('/accounts/login/')

@login_required(login_url='/accounts/login/')
def profile(request):
  context = {
    'segment': 'profile',
  }
  return render(request, 'pages/profile.html', context)

def is_staff_or_admin(user):
    return user.is_staff or user.is_superuser

@login_required(login_url='/accounts/login/')
def start_scraper(request):
  run_scraper(request)
  return HttpResponse("Scraper started")

@login_required(login_url='/accounts/login/')
def start_scraper_delay(request):
  run_scraper(request).delay()
  return HttpResponse("Scraper started")

@login_required(login_url='/accounts/login/')
def start_sending(request):
  send_all_products_to_woocommerce(request)
  return HttpResponse("Sending Products to WooCommerce started")

@login_required(login_url='/accounts/login/')
def start_removing(request):
  remove_all_products_from_woocommerce(request)
  return HttpResponse("Removing Products from WooCommerce started")

@login_required(login_url='/accounts/login/')
def index(request):
  sources = ScraperSource.objects.all()
  now = timezone.now()

  product_count = Product.objects.count()
  product_percentage = math.log(product_count + 1, 100000) * 100

  out_of_stock_products = InventoryTracking.objects.filter(stock_available=False).count()
  out_of_stock_percentage = (out_of_stock_products / product_count) * 100 if product_count else 0

  newproductsinterval = now - timedelta(days=7)
  new_products = Product.objects.filter(created_at__gte=newproductsinterval).count()
  new_products_percentage = (new_products / product_count) * 100 if product_count else 0

  start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
  start_of_week = start_of_today - timedelta(days=start_of_today.weekday())

  today_records = PriceHistory.objects.filter(change_date__gte=start_of_today)
  week_records = PriceHistory.objects.filter(change_date__gte=start_of_week)
  all_records = PriceHistory.objects.all()
  
  context = {
    'product_count': product_count,
    'product_percentage': product_percentage,
    'out_of_stock_products': out_of_stock_products, 
    'out_of_stock_percentage': out_of_stock_percentage,
    'new_products': new_products, 
    'new_products_percentage': new_products_percentage,
    'today_records': today_records,
    'week_records': week_records,
    'all_records': all_records,
    'segment': 'index',
    'sources': sources
  }
  return render(request, "pages/index.html", context)

def get_date_from_interval(interval):
  if interval == "1 week":
    return datetime.now() - timedelta(weeks=1)
  elif interval == "1 month":
    return datetime.now() - relativedelta(months=1)
  elif interval == "6 month":
    return datetime.now() - relativedelta(months=6)
  elif interval == "1 year":
    return datetime.now() - relativedelta(years=1)
  elif interval == "All":
    return None
  else:
    raise ValueError(f"Invalid interval: {interval}")

def get_top_products_by_price(interval):
  date = get_date_from_interval(interval)
  query = Product.objects
  if date is not None:
    query = query.filter(pricehistory__change_date__gte=date)
  products = query.all()

  # Calculate average price change for each product
  avg_price_changes = {}
  for product in products:
    price_changes = [ph.price_change() for ph in product.pricehistory_set.all()]
    avg_price_change = sum(price_changes) / len(price_changes) if price_changes else 0
    if product.sku not in avg_price_changes:
      avg_price_changes[product.sku] = avg_price_change
    else:
      old_avg_price_change = avg_price_changes[product.sku]
      new_avg_price_change = (old_avg_price_change + avg_price_change) / 2
      avg_price_changes[product.sku] = new_avg_price_change

  # Sort products by average price change
  sorted_products = sorted(avg_price_changes.items(), key=lambda x: x[1], reverse=True)

  # Get the top 5 products
  top_5_products = sorted_products[:5]

  # Convert the top 5 products to a list of dictionaries
  top_5_products_list = [{"sku": sku, "change": round(avg_price_change, 2)} for sku, avg_price_change in top_5_products]

  return top_5_products_list

def get_top_products_by_popularity(interval):
  date = get_date_from_interval(interval)
  query = Product.objects
  if date is not None:
    query = query.filter(created_at__gte=date)
  products = query.values('ref_no').annotate(count=Count('ref_no')).order_by('-count')[:5]

  # Convert QuerySet to a list of dictionaries
  products_list = list(products)

  return products_list

@require_GET
def top_products(request):
  # Get the filter and month from the request parameters
  filter = request.GET.get('filter', 'Price')
  interval = request.GET.get('interval', '1 month')

  # Get the top 5 products based on the filter and month
  if filter == 'Price':
    products = get_top_products_by_price(interval)
  else:
    products = get_top_products_by_popularity(interval)

  products_json = products
  return JsonResponse(products_json, safe=False)

@require_GET
def source_radar(request):
  # Define the start date as 12 months ago
  start_date = datetime.now() - timedelta(days=365)

  # Get the data for the source radar graph
  data = Product.objects.filter(created_at__gte=start_date).annotate(month=ExtractMonth('created_at')).values('source__name', 'month').annotate(count=Count('id')).order_by('source__name', 'month')

  # Convert the queryset to a dictionary
  data_dict = {}
  for item in data:
    if item['source__name'] not in data_dict:
      data_dict[item['source__name']] = [0]*12
    data_dict[item['source__name']][item['month']-1] = item['count']

  return JsonResponse(data_dict, safe=False)

@require_GET
def product_source_distribution(request):
  # Get the data for the source distribution graph
  data = Product.objects.values('source__name').annotate(count=Count('id')).order_by('source__name')

  # Convert the queryset to a dictionary
  data_dict = {item['source__name']: item['count'] for item in data}

  return JsonResponse(data_dict, safe=False)

@require_GET
def overall_price_change(request):
  # Define the start date as 12 months ago
  start_date = datetime.now() - timedelta(days=365)

  # Get the average price change for each month
  data = PriceHistory.objects.filter(change_date__gte=start_date).annotate(
    month=ExtractMonth('change_date'),
    price_change=Case(
      When(old_price=0, then=0),
      default=((F('new_price') - F('old_price')) / F('old_price')) * 100,
      output_field=FloatField()
    )
  ).values('month').annotate(
    avg_price_change=Avg('price_change')
  ).order_by('month')

  # Initialize the price change data
  price_change = [0]*12
  for item in data:
    price_change[item['month']-1] = item['avg_price_change']

  # Return the price change data
  return JsonResponse({'price_change': price_change}, safe=False)

@login_required(login_url='/accounts/login/')
def price_analysis(request):
  brands = Product.objects.values_list('brand', flat=True).distinct()
  models = Product.objects.values_list('model', flat=True).distinct()
  return render(request, "pages/price_analysis.html", {'brands': brands, 'models': models})

@login_required(login_url='/accounts/login/')
def autocomplete_ref_no(request):
  term = request.GET.get('term')
  ref_nos = Product.objects.filter(ref_no__icontains=term).values_list('ref_no', flat=True).distinct()
  return JsonResponse(list(ref_nos), safe=False)

@login_required(login_url='/accounts/login/')
def get_models(request):
  brand = request.GET.get('brand', None)
  if brand is not None:
    models = list(Product.objects.filter(brand=brand).values_list('model', flat=True).distinct())
    return JsonResponse(models, safe=False)
  else:
    return JsonResponse([], safe=False)

@login_required(login_url='/accounts/login/')
def get_brand(request):
  model = request.GET.get('model', None)
  if model is not None:
    brand = Product.objects.filter(model=model).values_list('brand', flat=True).first()
    return JsonResponse({'brand': brand})
  else:
    return JsonResponse({'brand': None})

@login_required(login_url='/accounts/login/')
def product_analysis(request):
  ref_no = request.GET.get('ref_no')
  brand = request.GET.get('brand')
  model = request.GET.get('model')
  print(dict(request.session))  # print the entire session data
  interval = request.GET.get('interval')
  if interval:
      print("interval")
      if request.session['ref_no'] is not None:
        ref_no = request.session['ref_no']
        products = Product.objects.filter(ref_no=ref_no)
      elif request.session['model'] is not None:
        model = request.session['model']
        products = Product.objects.filter(model=model)
      elif request.session['brand'] is not None:
        brand = request.session['brand']
        products = Product.objects.filter(brand=brand)
        print("session brand")
      else:
        return JsonResponse({
          'error': 'No ref_no, brand, or model provided',
          'interval': interval,
          'session': {
            'ref_no': request.session.get('ref_no'),
            'brand': request.session.get('brand'),
            'model': request.session.get('model'),
          }
        }, status=400)
  elif ref_no:
      request.session['ref_no'] = ref_no
      request.session['brand'] = None
      request.session['model'] = None
      products = Product.objects.filter(ref_no=ref_no)
  elif model:
      request.session['model'] = model
      request.session['brand'] = None
      request.session['ref_no'] = None
      products = Product.objects.filter(model=model)
  elif brand:
      request.session['brand'] = brand
      request.session['model'] = None
      request.session['ref_no'] = None
      products = Product.objects.filter(brand=brand)
  else:
      return JsonResponse({
        'error': 'No ref_no, brand, or model provided',
        'ref_no': ref_no,
        'brand': brand,
        'model': model,
        'interval': interval,
        'session': {
          'ref_no': request.session.get('ref_no'),
          'brand': request.session.get('brand'),
          'model': request.session.get('model'),
        }
      }, status=400)
  if not interval:
    interval = '1 month'
    
  return perform_analysis(products, interval)

def get_periods(start_date, end_date, period_length):
    period_start = start_date
    while period_start < end_date:
        period_end = period_start + timedelta(days=period_length)
        yield period_start, period_end
        period_start = period_end


def perform_analysis(products, interval):

  if not products.exists():
    return JsonResponse({'error': 'No products found with the provided ref_no/brand/model'}, status=404)

  analysis_results = []
  combined_prices = []
  # combined_price_changes_percentage = []

  number = None
  unit = None  

  # Handle the 'All' option
  if interval == 'All':
    price_histories_query = PriceHistory.objects.filter(product__in=products)
  else:
    # Parse the interval into a number and a unit (e.g., '1 month' -> 1, 'month')
    number, unit = interval.split()
    number = int(number)
    # Calculate the datetime for the start of the interval
    if unit == 'day':
      start_date = timezone.now() - relativedelta(days=number)
    elif unit == 'week':
      start_date = timezone.now() - relativedelta(weeks=number)
    elif unit == 'month':
      start_date = timezone.now() - relativedelta(months=number)
    elif unit == 'year':
      start_date = timezone.now() - relativedelta(years=number)
    else:
      return JsonResponse({'error': 'Invalid interval unit'}, status=400)

    # Fetch price histories that have a change_date within the interval
    price_histories_query = PriceHistory.objects.filter(product__in=products, change_date__gte=start_date)
  
  source_distribution = {}
  for product in products:
    price_histories = price_histories_query.filter(product=product).order_by('change_date').values('change_date', 'old_price', 'new_price')
    
    # Calculate price change percentages
    price_changes = []
    prices = []  # Collect all prices for this product

    
    # Add initial product price and creation date if it's within the interval or if the interval is 'All'
    if interval == 'All' or product.created_at >= start_date:
        # Get the old_price of the first ordered PriceHistory record
      first_price_history = price_histories.first()
      if first_price_history:
        initial_price = first_price_history['old_price']
      else:
        initial_price = product.price  # Fallback to product.price if there are no price histories
          
      price_changes.append({'date': product.created_at, 'price_change_percentage': 0, 'old_price' : 0, 'new_price': initial_price})
      combined_prices.append(initial_price)
      # combined_price_changes_percentage.append(decimal.Decimal(0))
      prices.append(initial_price)
      

    for history in price_histories:
      old_price = history['old_price']
      new_price = history['new_price']
      if old_price != 0:
        price_change_percentage = round(((new_price - old_price) / old_price) * 100, 2)
      else:
        price_change_percentage = 0
      price_changes.append({'date': history['change_date'], 'price_change_percentage': price_change_percentage, 'old_price' : old_price, 'new_price': new_price})
      combined_prices.append(new_price)
      # combined_price_changes_percentage.append(price_change_percentage)
      
      prices.append(history['new_price'])  # Add new price to prices
    if not price_changes:
       continue

    source_name = product.source.name
    if source_name not in source_distribution:
      source_distribution[source_name] = 0
    source_distribution[source_name] += 1
    if prices:
      product_mean_price = round(statistics.mean(prices), 2)
    else:
      product_mean_price = product.price
    
    first_image= None
    try:
        imageModel = product.images.first()
        
        if imageModel:
            image_files = json.loads(imageModel.images)
            # If there are image files, return the name of the first one
            if image_files:
                 first_image = image_files[0]
    except FileNotFoundError:
        print("FileNotFoundError")  # Debug print statement
        pass
    
    analysis_results.append({
      'product_ref_no': product.ref_no,
      'product_first_image': first_image,
      'product_sku': product.sku,
      'product_current_price': str(product.price),
      'product_source': product.source.name,
      'product_url': product.url,
      'product_mean_price': product_mean_price,
      'price_changes': price_changes,
      'admin_product_change_url': reverse('admin:home_product_change', args=[product.id])
    })

  min_max_prices = []
  # Get all price changes for all products
  all_price_changes = price_histories_query.order_by('change_date').values('change_date', 'new_price')

  # Calculate min and max prices for each period
  if interval == 'All':
    start_date = timezone.now() - relativedelta(months=3)
    period_length = (timezone.now() - start_date).days
  elif unit == 'day':
    period_length = 2  # hours
  elif unit == 'week':
    period_length = 1  # day
  elif unit == 'month':
    period_length = 7  # week
  elif unit == 'year':
    period_length = 30  # month
  else:
    return JsonResponse({'error': 'Invalid interval unit'}, status=400)
  
  for period_start, period_end in get_periods(start_date, timezone.now(), period_length):
    period_price_changes = [pc for pc in all_price_changes if period_start <= pc['change_date'] < period_end]
    if period_price_changes:
      min_price = min(pc['new_price'] for pc in period_price_changes)
      max_price = max(pc['new_price'] for pc in period_price_changes)
      if unit == 'day':
        period_start = period_start.time()
        period_end = period_end.time()
      elif unit != 'day' or interval == 'All':
        period_start = period_start.date()
        period_end = period_end.date()
      min_max_prices.append({
        'period': f"{period_start} to {period_end}",
        'min_price': min_price,
        'max_price': max_price,
      })
  # Calculate combined mean and median
  # if combined_price_changes_percentage:
  #   combined_mean_price_change_percentage = round(statistics.mean(combined_price_changes_percentage), 2)
  #   combined_median_price_change_percentage = round(statistics.median(combined_price_changes_percentage), 2)
  # else:
  #   combined_mean_price_change_percentage = combined_median_price_change_percentage = 0
  
  # Calculate combined mean and median
  if combined_prices:
    combined_mean_price_change = round(statistics.mean(combined_prices), 2)
    combined_median_price_change = round(statistics.median(combined_prices), 2)
    combined_min_price_change = round(min(combined_prices), 2)
    combined_max_price_change = round(max(combined_prices), 2)
    combined_std_dev_price_change = round(statistics.stdev(combined_prices), 2) if len(combined_prices) > 1 else 0
  else:
    combined_mean_price_change = combined_median_price_change = combined_min_price_change = combined_max_price_change = combined_std_dev_price_change = 0
  
  # Return results including combined statistics
  return JsonResponse({
        # 'combined_mean_price_change_percentage': combined_mean_price_change_percentage,
        # 'combined_median_price_change_percentage': combined_median_price_change_percentage,
        'combined_mean_price_change': combined_mean_price_change,
        'combined_median_price_change': combined_median_price_change,
        'combined_min_price_change': combined_min_price_change,
        'combined_max_price_change': combined_max_price_change,
        'combined_std_dev_price_change': combined_std_dev_price_change,
        'analysis_results': analysis_results,
        'source_distribution': source_distribution,
        'min_max_prices': min_max_prices,
    }, safe=False)


@login_required(login_url='/accounts/login/')
def search_images(request):
    ref_no = request.GET.get('ref_no', '')
    products = Product.objects.filter(ref_no=ref_no)
    sku = request.GET.get('sku', '')
    selected_product = Product.objects.filter(sku=sku).first()
    selected_image_model = Image.objects.filter(product=selected_product).first()
    selected_images = []
    if selected_image_model:
      selected_images = json.loads(selected_image_model.images)
    image_files = {}
    if ref_no:
      image_record = Image.objects.filter(product__ref_no=ref_no).first()
      if image_record:
        # Convert list of image names to JSON string correctly before saving
        image_files = json.loads(image_record.images)
      else:
          messages.error(request, 'Directory not found.')
    return render(request, 'pages/image_management.html', {'ref_no': ref_no,'sku': sku, 'image_files': image_files, 'products': products, 'selected_images': selected_images})

@login_required(login_url='/accounts/login/')
def set_image_order(request):
  if request.method == 'POST':
    ref_no = request.POST.get('ref_no', '')
    image_order_str = request.POST.get('image_order', '[]')
    try:
      image_order = json.loads(image_order_str)
      # Ensure image_order is a list of strings
      if not all(isinstance(item, str) for item in image_order):
        raise ValueError("Image order must be a list of strings.")
    except ValueError as e:
      return JsonResponse({'status': 'error', 'message': 'Invalid image order format.'})

    image_record = Image.objects.filter(product__ref_no=ref_no).first()
    if image_record:
      # Convert list of image names to JSON string correctly before saving
      image_record.images = json.dumps(image_order)
      image_record.save()
      return JsonResponse({'status': 'success', 'message': 'Order set successfully.'})
    else:
      return JsonResponse({'status': 'error', 'message': 'Image record not found.'})
  else:
    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)


@login_required(login_url='/accounts/login/')
def delete_image_file(request, image_file):
  ref_no = request.GET.get('ref_no', '')
  redirect_url = reverse('search_images')
  if ref_no:
    file_path = os.path.join(settings.MEDIA_ROOT,'images', ref_no, image_file)
    if os.path.isfile(file_path):
      os.remove(file_path)
      messages.success(request, 'Image file deleted successfully.')
    else:
      messages.error(request, 'Image file not found.')
    products = Product.objects.filter(ref_no=ref_no)
    for product in products:
      imageModel = Image.objects.filter(product=product).first()
      if imageModel:
        images = json.loads(imageModel.images)
        if image_file in images:
            images.remove(image_file)
            imageModel.images = json.dumps(images)
            imageModel.save()
            messages.success(request, 'Image record deleted successfully.')
    # delete from image model logice goes here
    redirect_url += '?ref_no=' + ref_no
  return HttpResponseRedirect(redirect_url)

@login_required(login_url='/accounts/login/')
def upload_images(request):
  if request.method == 'POST':
    image_files = request.FILES.getlist('image_files')
    ref_no = request.GET.get('ref_no', '')
    if ref_no:
      
      image_names = []
      for image_file in image_files:
        image_names.append(image_file.name)
        # Construct the full path for the image file
        full_path = os.path.join(settings.MEDIA_ROOT, 'images', ref_no, image_file.name)

        # Write the image file to the full path
        with open(full_path, 'wb+') as destination:
          for chunk in image_file.chunks():
            destination.write(chunk)
        # Append the filename to the images field in the Image model
      products = Product.objects.filter(ref_no=ref_no)
      for product in products:
        imageModel = Image.objects.filter(product=product).first()
        if imageModel:
          images = json.loads(imageModel.images)
          images.extend(image_names)
          imageModel.images = json.dumps(images)
          imageModel.save()
          
      messages.success(request, 'Image files uploaded successfully.')

  url = reverse('search_images')
  params = f'ref_no={ref_no}'
  return HttpResponseRedirect(url + '?' + params)

@login_required(login_url='/accounts/login/')
def delete_all_images(request):
    # Image.objects.all().delete()
    messages.success(request, 'All images deleted successfully.')
    return redirect('search_images')



