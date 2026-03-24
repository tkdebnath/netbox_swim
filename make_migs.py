import os
import sys

# Add netbox to system path to import settings
sys.path.append('/opt/netbox/netbox')
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "netbox.settings")

import django
django.setup()

from django.core.management import call_command
call_command("makemigrations", "netbox_swim")
