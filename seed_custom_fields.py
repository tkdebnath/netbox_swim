import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from extras.models import CustomField
from extras.choices import CustomFieldTypeChoices
from django.contrib.contenttypes.models import ContentType
from dcim.models import Device

def create_swim_custom_fields():
    device_obj = ContentType.objects.get_for_model(Device)

    # 1. Deployment Mode Context
    cf_deploy, created = CustomField.objects.get_or_create(
        name='swim_deployment_mode',
        defaults={
            'type': CustomFieldTypeChoices.TYPE_SELECT,
            'label': 'SWIM Deployment Mode',
            'description': 'Explicitly binds a device to a specific Deployment Architecture (e.g. SD-WAN vs Campus)',
            'weight': 100,
            'required': False,
        }
    )
    if created:
        cf_deploy.content_types.add(device_obj)
        cf_deploy.choices = ['campus', 'sdwan', 'universal']
        cf_deploy.save()
        print("[SUCCESS] Seeding Custom Field: swim_deployment_mode")

    # 2. Last Sync Status
    cf_sync_status, created = CustomField.objects.get_or_create(
        name='swim_last_sync_status',
        defaults={
            'type': CustomFieldTypeChoices.TYPE_TEXT,
            'label': 'SWIM Last Sync Status',
            'description': 'Latest compliance Sync result (Success / Error)',
            'weight': 110,
            'required': False,
        }
    )
    if created:
        cf_sync_status.content_types.add(device_obj)
        print("[SUCCESS] Seeding Custom Field: swim_last_sync_status")

    # 3. Last Sync Timestamp
    cf_sync_time, created = CustomField.objects.get_or_create(
        name='swim_last_sync_time',
        defaults={
            'type': CustomFieldTypeChoices.TYPE_DATETIME,
            'label': 'SWIM Last Sync Time',
            'description': 'Timestamp of last successfully processed NetBox Device state alignment',
            'weight': 120,
            'required': False,
        }
    )
    if created:
        cf_sync_time.content_types.add(device_obj)
        print("[SUCCESS] Seeding Custom Field: swim_last_sync_time")

if __name__ == '__main__':
    create_swim_custom_fields()
    print("\n[COMPLETE] All native SWIM Custom Fields established onto dcim._device mappings.")
