import re
import django.utils.cache

# DRF compatibility shim for Django 6+ where cc_delim_re was removed from django.utils.cache
if not hasattr(django.utils.cache, 'cc_delim_re'):
    django.utils.cache.cc_delim_re = re.compile(r'\s*,\s*')
