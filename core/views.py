# views.py
from django.http import Http404
from django.views import View

class Raise404View(View):
    def get(self, request, *args, **kwargs):
        raise Http404