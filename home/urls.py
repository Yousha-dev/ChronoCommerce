from django.urls import path, re_path
from django.contrib.auth import views as auth_views
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
  # Authentication
  path('accounts/register/', views.UserRegistrationView.as_view(), name='register'),
  path('accounts/login/', views.UserLoginView.as_view(), name='login'),
  path('accounts/logout/', views.logout_view, name='logout'),

  path('accounts/password-change/', views.UserPasswordChangeView.as_view(), name='password_change'),
  path('accounts/password-change-done/', auth_views.PasswordChangeDoneView.as_view(
      template_name='accounts/auth-password-change-done.html'
  ), name="password_change_done"),

  path('accounts/password-reset/', views.UserPasswordResetView.as_view(), name='password_reset'),
  path('accounts/password-reset-confirm/<uidb64>/<token>/',
    views.UserPasswrodResetConfirmView.as_view(), name="password_reset_confirm"
  ),
  path('accounts/password-reset-done/', auth_views.PasswordResetDoneView.as_view(
    template_name='accounts/auth-password-reset-done.html'
  ), name='password_reset_done'),
  path('accounts/password-reset-complete/', auth_views.PasswordResetCompleteView.as_view(
    template_name='accounts/auth-password-reset-complete.html'
  ), name='password_reset_complete'),

  #Scraper
  path('start-scraper/', views.start_scraper, name='start_scraper'),
  path('start-scraper-delay/', views.start_scraper_delay, name='start_scraper-delay'),
  path('start-sending/', views.start_sending, name='start_sending'),
  path('start-removing/', views.start_removing, name='start_removing'),

  #Home
  path('', views.index, name='index'),
  path('top_products/', views.top_products, name='top_products'),
  path('source_radar/', views.source_radar, name='source_radar'),
  path('product_source_distribution/', views.product_source_distribution, name='product_source_distribution'),
  path('overall_price_change/', views.overall_price_change, name='overall_price_change'),

  #Price Analysis
  path('price_analysis/', views.price_analysis, name='price_analysis'),
  path('autocomplete_ref_no/', views.autocomplete_ref_no, name='autocomplete_ref_no'),
  path('get_models/', views.get_models, name='get_models'),
  path('get_brand/', views.get_brand, name='get_brand'),
  path('product_analysis/', views.product_analysis, name='product_analysis'),

  #Others
  path('profile/', views.profile, name='profile'),
  
  path('images/search/', views.search_images, name='search_images'),
  path('set_image_order/', views.set_image_order, name='set_image_order'),
  re_path(r'^delete_image_file/(?P<image_file>.+)/$', views.delete_image_file, name='delete_image_file'),
  path('images/upload/', views.upload_images, name='upload_images'),
  path('images/delete_all/', views.delete_all_images, name='delete_all_images'),

] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)