import os
import sys
import django
from django.utils import timezone

# Setup Django environment
sys.path.append('/opt/netbox/netbox')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'netbox.settings')
django.setup()

from dcim.models import Platform, Manufacturer, DeviceType, DeviceRole, Site, Device, Region
from netbox_swim.models import (
    SoftwareImage, GoldenImage, DeviceCompliance,
    WorkflowTemplate, WorkflowStep, UpgradeJob,
    DeploymentModeChoices, HardwareGroup, FileServer
)

def seed():
    print("--- Seeding Granular SWIM Data ---")

    # 1. MANUFACTURER & PLATFORM
    cisco, _ = Manufacturer.objects.get_or_create(name='Cisco', slug='cisco')
    
    ios_xe, _ = Platform.objects.get_or_create(name='Cisco IOS-XE', slug='cisco-ios-xe', manufacturer=cisco)
    nx_os, _ = Platform.objects.get_or_create(name='Cisco NX-OS', slug='cisco-nx-os', manufacturer=cisco)

    # 2. DEVICE TYPES (Hardware Models)
    cat9300, _ = DeviceType.objects.get_or_create(manufacturer=cisco, model='Catalyst 9300-48P', slug='c9300-48p')
    n9k, _ = DeviceType.objects.get_or_create(manufacturer=cisco, model='Nexus 9300-FX3', slug='n9k-fx3')

    # 2.5 HARDWARE GROUPS (Grouping Criteria)
    group_campus, _ = HardwareGroup.objects.get_or_create(
        name='Campus-Core-Segment',
        slug='campus-core-segment',
        defaults={
            'description': 'All campus core switches running 16.x or 17.x',
            'deployment_mode': DeploymentModeChoices.CAMPUS
        }
    )
    group_campus.platforms.add(ios_xe)
    group_campus.device_types.add(cat9300)

    group_sdwan, _ = HardwareGroup.objects.get_or_create(
        name='SDWAN-Edge-Segment',
        slug='sdwan-edge-segment',
        defaults={
            'description': 'SD-WAN Edge hardware',
            'deployment_mode': DeploymentModeChoices.SDWAN
        }
    )
    group_sdwan.platforms.add(ios_xe)
    group_sdwan.device_types.add(cat9300)

    # 3. SOFTWARE IMAGES (Granular Mapping)
    # Campus Image
    img_campus, _ = SoftwareImage.objects.get_or_create(
        image_name='Cat9k-Campus-17.09.04',
        defaults={
            'version': '17.9.4',
            'image_type': 'software',
            'platform': ios_xe,
            'deployment_mode': DeploymentModeChoices.CAMPUS,
            'image_file_name': 'cat9k_iosxe.17.09.04.SPA.bin',
            'hash_md5': 'a1b2c3d4e5f6',
            'min_flash_mb': 4096,
        }
    )
    img_campus.device_types.add(cat9300)
    img_campus.hardware_groups.add(group_campus)

    # SD-WAN Image
    img_sdwan, _ = SoftwareImage.objects.get_or_create(
        image_name='Cat9k-SDWAN-17.09.04',
        defaults={
            'version': '17.9.4',
            'image_type': 'software',
            'platform': ios_xe,
            'deployment_mode': DeploymentModeChoices.SDWAN,
            'image_file_name': 'cat9k_sdwan.17.09.04.SPA.bin',
            'hash_md5': 'f1e2d3c4b5a6',
            'min_flash_mb': 8192,
        }
    )
    img_sdwan.device_types.add(cat9300)
    img_sdwan.hardware_groups.add(group_sdwan)

    # Nexus Image
    img_nxos, _ = SoftwareImage.objects.get_or_create(
        image_name='NX-OS-10.2(3)F',
        defaults={
            'version': '10.2(3)F',
            'image_type': 'software',
            'platform': nx_os,
            'deployment_mode': DeploymentModeChoices.UNIVERSAL,
            'image_file_name': 'nxos64-cs.10.2.3.F.bin',
            'hash_md5': 'nxos-hash-123',
        }
    )
    img_nxos.device_types.add(n9k)

    print("Software Images & Hardware Mapping created.")

    # 4. GOLDEN IMAGES (Hardware + Deployment Context)
    GoldenImage.objects.get_or_create(
        hardware_group=group_campus,
        deployment_mode=DeploymentModeChoices.CAMPUS,
        defaults={'image': img_campus, 'description': 'Standardized Campus image for the whole group.'}
    )
    GoldenImage.objects.get_or_create(
        hardware_group=group_sdwan,
        deployment_mode=DeploymentModeChoices.SDWAN,
        defaults={'image': img_sdwan, 'description': 'Standardized SD-WAN image for the whole group.'}
    )
    GoldenImage.objects.get_or_create(
        device_type=n9k,
        deployment_mode=DeploymentModeChoices.CAMPUS,
        defaults={'image': img_nxos, 'description': 'Nexus Standard (Individual mapping).'}
    )
    print("Golden Images created.")

    # 5. SITE & DEVICES
    # Sites & Regions
    site_sj, _ = Site.objects.get_or_create(name='San Jose', slug='sanjose')
    region_west, _ = Region.objects.get_or_create(name='US-West', slug='us-west')
    site_sj.region = region_west
    site_sj.save()

    # --- File Servers ---
    srv_tftp, _ = FileServer.objects.get_or_create(
        name='SJ-TFTP-SRV',
        defaults={
            'protocol': 'tftp',
            'ip_address': '10.1.1.50',
            'base_path': '/tftpboot/',
            'description': 'Main TFTP server for San Jose Site'
        }
    )
    srv_tftp.sites.add(site_sj)

    srv_global, _ = FileServer.objects.get_or_create(
        name='Global-HTTPS-SRV',
        defaults={
            'protocol': 'https',
            'ip_address': 'repo.example.com',
            'base_path': '/images/',
            'description': 'Global repository for all regions'
        }
    )
    srv_global.regions.add(region_west)

    role_core, _ = DeviceRole.objects.get_or_create(name='Campus Core', slug='campus-core', color='00ff00')
    role_sdwan, _ = DeviceRole.objects.get_or_create(name='SD-WAN Edge', slug='sdwan-edge', color='0000ff')
    
    # Campus Device
    dev_campus, _ = Device.objects.get_or_create(
        name='SJ-CAMPUS-01',
        defaults={
            'device_type': cat9300,
            'role': role_core,
            'site': site_sj,
            'platform': ios_xe,
            'status': 'active',
            'custom_field_data': {
                'deployment_mode': 'campus',
                'software_version': '17.6.5'
            }
        }
    )

    # SD-WAN Device
    dev_sdwan, _ = Device.objects.get_or_create(
        name='SJ-SDWAN-01',
        defaults={
            'device_type': cat9300,
            'role': role_sdwan,
            'site': site_sj,
            'platform': ios_xe,
            'status': 'active',
            'custom_field_data': {
                'deployment_mode': 'sdwan',
                'software_version': '17.3.1'
            }
        }
    )

    print("Mock Devices created.")

    # 6. DEVICE COMPLIANCE
    # Campus Compliance (Running old)
    DeviceCompliance.objects.get_or_create(
        device=dev_campus,
        defaults={
            'status': 'non_compliant',
            'current_version': '17.6.5',
            'expected_version': '17.9.4',
            'last_checked': timezone.now()
        }
    )
    # SD-WAN Compliance (Running old)
    DeviceCompliance.objects.get_or_create(
        device=dev_sdwan,
        defaults={
            'status': 'non_compliant',
            'current_version': '17.3.1',
            'expected_version': '17.9.4',
            'last_checked': timezone.now()
        }
    )
    print("Compliance Records created.")

    # 7. WORKFLOW TEMPLATES
    tmpl_campus, _ = WorkflowTemplate.objects.get_or_create(
        name='Standard Campus Upgrade',
        defaults={'description': 'Standard upgrade flow for campus switches.'}
    )
    tmpl_sdwan, _ = WorkflowTemplate.objects.get_or_create(
        name='Standard SD-WAN Upgrade',
        defaults={'description': 'Upgrade flow with SD-WAN specific orchestration.'}
    )

    for tmpl in [tmpl_campus, tmpl_sdwan]:
        steps = [
            {'order': 10, 'action_type': 'precheck'},
            {'order': 20, 'action_type': 'distribute'},
            {'order': 30, 'action_type': 'activate'},
            {'order': 40, 'action_type': 'postcheck'},
        ]
        for s_info in steps:
            WorkflowStep.objects.get_or_create(
                template=tmpl,
                action_type=s_info['action_type'],
                defaults={'order': s_info['order']}
            )

    # 8. UPGRADE JOBS
    UpgradeJob.objects.get_or_create(
        device=dev_campus,
        target_image=img_campus,
        defaults={
            'template': tmpl_campus,
            'status': 'pending',
            'scheduled_time': timezone.now()
        }
    )
    UpgradeJob.objects.get_or_create(
        device=dev_sdwan,
        target_image=img_sdwan,
        defaults={
            'template': tmpl_sdwan,
            'status': 'pending',
            'scheduled_time': timezone.now()
        }
    )
    print("Upgrade Jobs created.")
    print("--- Seeding Complete ---")

if __name__ == "__main__":
    seed()
