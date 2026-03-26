from django.db import models
from django.urls import reverse
from netbox.models import NetBoxModel
from dcim.models import Device
from utilities.choices import ChoiceSet


# ============================================================
# PILLAR 1: Centralized Image Repository
# ============================================================

class DeploymentModeChoices(models.TextChoices):
    CAMPUS = 'campus', 'Campus / Traditional'
    SDWAN = 'sdwan', 'SD-WAN'
    UNIVERSAL = 'universal', 'Universal (Both)'


class HardwareGroup(NetBoxModel):
    """
    Groups devices based on criteria (platform, device types, version ranges).
    Used to easily map images to a fleet or segment of hardware.
    """
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    platforms = models.ManyToManyField(
        'dcim.Platform', blank=True,
        related_name='hardware_groups'
    )
    device_types = models.ManyToManyField(
        'dcim.DeviceType', blank=True,
        related_name='hardware_groups'
    )
    min_version = models.CharField(max_length=50, blank=True, help_text="Minimum current software version to match")
    max_version = models.CharField(max_length=50, blank=True, help_text="Maximum current software version to match")
    deployment_mode = models.CharField(
        max_length=20,
        choices=DeploymentModeChoices.choices,
        default=DeploymentModeChoices.UNIVERSAL,
        help_text='Network deployment context for this group'
    )
    is_static = models.BooleanField(
        default=False,
        help_text='If true, membership logic is controlled by a Python class and UI matching criteria are ignored.'
    )
    manual_includes = models.ManyToManyField(
        'dcim.Device', blank=True,
        related_name='swim_manual_groups',
        help_text='Manually force devices into this group'
    )
    manual_excludes = models.ManyToManyField(
        'dcim.Device', blank=True,
        related_name='swim_excluded_groups',
        help_text='Manually exclude devices from this group'
    )
    description = models.TextField(blank=True)
    connection_priority = models.CharField(
        max_length=100,
        default="scrapli,netmiko,unicon",
        help_text="Comma-separated list defining sequence of connection libraries to attempt (e.g. 'scrapli,netmiko,unicon')"
    )
    workflow_template = models.ForeignKey(
        'WorkflowTemplate', 
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name='hardware_groups',
        help_text="The core Upgrade Lifecycle workflow assigned to all hardware in this group."
    )

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_swim:hardwaregroup', args=[self.pk])

    def get_matching_devices(self):
        from dcim.models import Device
        base_qs = Device.objects.none()
        if self.is_static:
            pass
        else:
            kwargs = {}
            if self.platforms.exists():
                kwargs['platform__in'] = self.platforms.all()
            if self.device_types.exists():
                kwargs['device_type__in'] = self.device_types.all()
            
            # Enforce Application logic: Hardware groups with strict deploy modes filter strictly
            if self.deployment_mode != DeploymentModeChoices.UNIVERSAL:
                kwargs['custom_field_data__deployment_mode'] = self.deployment_mode

            # STRICTNESS: Prevent empty groups from wildcard matching the entire database.
            if not self.platforms.exists() and not self.device_types.exists():
                # If neither are defined, do NOT wildcard match all devices. 
                return Device.objects.filter(pk__in=[i.pk for i in self.manual_includes.all()])

            if kwargs:
                base_qs = Device.objects.filter(**kwargs)
        base_pks = set(base_qs.values_list('pk', flat=True))
        included_pks = set(self.manual_includes.values_list('pk', flat=True))
        excluded_pks = set(self.manual_excludes.values_list('pk', flat=True))
        final_pks = (base_pks | included_pks) - excluded_pks
        return Device.objects.filter(pk__in=final_pks)


class FileServer(NetBoxModel):
    class ProtocolChoices(models.TextChoices):
        TFTP = 'tftp', 'TFTP'
        FTP = 'ftp', 'FTP'
        SFTP = 'sftp', 'SFTP'
        HTTP = 'http', 'HTTP'
        HTTPS = 'https', 'HTTPS'
        SCP = 'scp', 'SCP'

    name = models.CharField(max_length=100, unique=True)
    protocol = models.CharField(max_length=20, choices=ProtocolChoices.choices)
    ip_address = models.CharField(max_length=255, help_text="Server IP or Hostname")
    port = models.PositiveIntegerField(null=True, blank=True, help_text="Optional custom port")
    username = models.CharField(max_length=100, blank=True, help_text="Username for authentication")
    password = models.CharField(max_length=100, blank=True, help_text="Password for authentication")
    base_path = models.CharField(max_length=255, blank=True, help_text="Root directory on server")
    regions = models.ManyToManyField('dcim.Region', blank=True, related_name='swim_file_servers')
    sites = models.ManyToManyField('dcim.Site', blank=True, related_name='swim_file_servers')
    devices = models.ManyToManyField('dcim.Device', blank=True, related_name='swim_file_servers')
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_protocol_display()})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_swim:fileserver', args=[self.pk])


class SoftwareImage(NetBoxModel):
    class ImageTypeChoices(models.TextChoices):
        SOFTWARE = 'software', 'Software Image'
        SMU = 'smu', 'Software Maintenance Update (SMU)'
        ROMMON = 'rommon', 'ROMMON Image'

    image_name = models.CharField(max_length=255)
    image_file_name = models.CharField(max_length=255)
    version = models.CharField(max_length=50)
    image_type = models.CharField(max_length=20, choices=ImageTypeChoices.choices, default=ImageTypeChoices.SOFTWARE)
    file_server = models.ForeignKey(FileServer, on_delete=models.SET_NULL, related_name='images', null=True, blank=True)
    platform = models.ForeignKey('dcim.Platform', on_delete=models.CASCADE, related_name='software_images')
    device_types = models.ManyToManyField('dcim.DeviceType', related_name='software_images', blank=True)
    hardware_groups = models.ManyToManyField('HardwareGroup', related_name='software_images', blank=True)
    deployment_mode = models.CharField(max_length=20, choices=DeploymentModeChoices.choices, default=DeploymentModeChoices.UNIVERSAL)
    min_source_version = models.CharField(max_length=50, blank=True)
    max_source_version = models.CharField(max_length=50, blank=True)
    file_size_bytes = models.BigIntegerField(null=True, blank=False)
    hash_md5 = models.CharField(max_length=32, blank=False)
    hash_sha256 = models.CharField(max_length=64, blank=True)
    hash_sha512 = models.CharField(max_length=128, blank=False)
    release_notes_url = models.URLField(blank=True)
    min_ram_mb = models.IntegerField(null=True, blank=True)
    min_flash_mb = models.IntegerField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['platform', '-version']
        unique_together = ('platform', 'version', 'image_type', 'deployment_mode')

    def __str__(self):
        return f"{self.platform} — {self.image_name}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_swim:softwareimage', args=[self.pk])


class GoldenImage(NetBoxModel):
    device_types = models.ManyToManyField('dcim.DeviceType', related_name='golden_images', blank=True)
    hardware_groups = models.ManyToManyField('HardwareGroup', related_name='golden_images', blank=True)
    deployment_mode = models.CharField(max_length=20, choices=DeploymentModeChoices.choices, default=DeploymentModeChoices.CAMPUS)
    image = models.ForeignKey(SoftwareImage, on_delete=models.CASCADE, related_name='golden_designations')
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['deployment_mode']

    def __str__(self):
        dt_names = ', '.join(str(dt) for dt in self.device_types.all()[:3]) or 'Any'
        hg_names = ', '.join(str(hg) for hg in self.hardware_groups.all()[:3]) or 'Any'
        return f"Golden: {dt_names} / {hg_names} ({self.get_deployment_mode_display()})"

    def get_absolute_url(self):
        return reverse('plugins:netbox_swim:goldenimage', args=[self.pk])


class ComplianceStatus(models.TextChoices):
    COMPLIANT = 'compliant', 'Compliant'
    NON_COMPLIANT = 'non_compliant', 'Non-Compliant'
    UNKNOWN = 'unknown', 'Unknown'
    ERROR = 'error', 'Error'


class DeviceCompliance(NetBoxModel):
    device = models.OneToOneField(Device, on_delete=models.CASCADE, related_name='swim_compliance')
    status = models.CharField(max_length=20, choices=ComplianceStatus.choices, default=ComplianceStatus.UNKNOWN)
    current_version = models.CharField(max_length=100, blank=True)
    expected_version = models.CharField(max_length=100, blank=True)
    last_checked = models.DateTimeField(null=True, blank=True)
    detail = models.TextField(blank=True)

    class Meta:
        ordering = ['device']

    def __str__(self):
        return f"{self.device} — {self.get_status_display()}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_swim:devicecompliance', args=[self.pk])

class ValidationCheck(NetBoxModel):
    """
    A specific Genie or CLI command check.
    """
    class CategoryChoices(models.TextChoices):
        GENIE = 'genie', 'Genie Feature (pyATS)'
        COMMAND = 'command', 'CLI Command'
        SCRIPT = 'script', 'Python Script Path'

    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=CategoryChoices.choices, default=CategoryChoices.GENIE)
    command = models.CharField(max_length=255, help_text="e.g. 'bgp', 'ospf', or 'show ip int brief'")
    
    # Is it meant specifically for Pre, Post, or Both?
    class PhaseChoices(models.TextChoices):
        PRE = 'pre', 'Pre-Check Only'
        POST = 'post', 'Post-Check Only'
        BOTH = 'both', 'Both Pre & Post'
    phase = models.CharField(max_length=10, choices=PhaseChoices.choices, default=PhaseChoices.BOTH)
    
    def __str__(self):
        return f"{self.name} [{self.get_category_display()}]"

    def get_absolute_url(self):
        return reverse('plugins:netbox_swim:validationcheck', args=[self.pk])


class CheckTemplate(NetBoxModel):
    """
    A reusable template grouping multiple ValidationChecks.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    checks = models.ManyToManyField(ValidationCheck, related_name='templates')

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_swim:checktemplate', args=[self.pk])


class WorkflowTemplate(NetBoxModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('plugins:netbox_swim:workflowtemplate', args=[self.pk])


class WorkflowStep(NetBoxModel):
    class ActionTypes(models.TextChoices):
        READINESS = 'readiness', 'Readiness Evaluation'
        PRECHECK = 'precheck', 'Pre-Upgrade Validation'
        DISTRIBUTE = 'distribution', 'Distribute Image'
        ACTIVATE = 'activation', 'Activate / Reboot'
        WAIT = 'wait', 'Wait Timer'
        PING = 'ping', 'Ping Reachability'
        POSTCHECK = 'postcheck', 'Post-Upgrade Validation'
        VERIFICATION = 'verification', 'Verify Software Version'
        REPORT = 'report', 'Generate Report'

    template = models.ForeignKey(WorkflowTemplate, on_delete=models.CASCADE, related_name='steps')
    order = models.PositiveIntegerField()
    action_type = models.CharField(max_length=20, choices=ActionTypes.choices)
    extra_config = models.JSONField(default=dict, blank=True)

    class Meta:
        unique_together = ('template', 'order')
        ordering = ['order']

    def __str__(self):
        return f"{self.template.name} - Step {self.order} ({self.get_action_type_display()})"

    def get_absolute_url(self):
        return self.template.get_absolute_url()


class UpgradeJob(NetBoxModel):
    class StatusChoices(models.TextChoices):
        PENDING = 'pending', 'Pending'
        SCHEDULED = 'scheduled', 'Scheduled'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    template = models.ForeignKey(WorkflowTemplate, on_delete=models.SET_NULL, null=True, related_name='jobs')
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='upgrade_jobs')
    target_image = models.ForeignKey(SoftwareImage, on_delete=models.SET_NULL, null=True)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.PENDING)
    scheduled_time = models.DateTimeField(
        null=True, blank=True,
        help_text='If set, the job will not execute until this date/time. Leave blank for immediate execution.'
    )
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    job_log = models.JSONField(default=list, blank=True)
    extra_config = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Upgrade {self.device} -> {self.target_image.version if self.target_image else '?'}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_swim:upgradejob', args=[self.pk])


class JobLog(NetBoxModel):
    job = models.ForeignKey(UpgradeJob, on_delete=models.CASCADE, related_name='logs')
    action_type = models.CharField(max_length=50)
    step = models.CharField(max_length=100, blank=True, null=True)
    is_success = models.BooleanField(default=True)
    log_output = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        status = '✓' if self.is_success else '✗'
        return f"[{status}] {self.action_type} — Job #{self.job_id}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_swim:joblog', args=[self.pk])


# ============================================================
# PILLAR 5: Network Synchronization & Drift
# ============================================================

class SyncJob(NetBoxModel):
    """ Consolidated record of a Bulk Sync Operation. """
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=30, default='running')
    connection_library = models.CharField(max_length=50, default='scrapli')
    max_concurrency = models.PositiveIntegerField(default=5)
    selected_device_count = models.PositiveIntegerField(default=0)
    failed_device_count = models.PositiveIntegerField(default=0)
    summary_logs = models.JSONField(default=list, blank=True, null=True)

    class Meta:
        ordering = ('-start_time',)

    def __str__(self):
        return f"Bulk Sync #{self.pk}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_swim:syncjob', args=[self.pk])


class DeviceSyncRecord(NetBoxModel):
    class StatusChoices(ChoiceSet):
        CHOICES = [
            ('pending', 'Pending Approval', 'orange'),
            ('applied', 'Applied Manually', 'green'),
            ('auto_applied', 'Auto-Applied', 'blue'),
            ('failed', 'Failed', 'red'),
            ('syncing', 'Syncing...', 'blue'),
            ('no_change', 'No Configuration Drift', 'grey'),
        ]

    device = models.ForeignKey('dcim.Device', on_delete=models.CASCADE, related_name='swim_sync_records')
    sync_job = models.ForeignKey(SyncJob, on_delete=models.SET_NULL, null=True, blank=True, related_name='device_records')
    status = models.CharField(max_length=30, choices=StatusChoices, default='pending')
    detected_diff = models.JSONField(default=dict, blank=True, null=True)
    live_facts = models.JSONField(default=dict, blank=True, null=True, help_text="Raw device facts collected by library")
    log_messages = models.JSONField(default=list, blank=True, null=True)
    job_id = models.UUIDField(null=True, blank=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        ordering = ('-created',)

    def __str__(self):
        return f"Sync Record: {self.device.name}"

    def get_absolute_url(self):
        return reverse('plugins:netbox_swim:devicesyncrecord', args=[self.pk])

    def approve(self):
        if self.status != 'pending' or not self.detected_diff:
            return False
        if 'hostname' in self.detected_diff:
            self.device.name = self.detected_diff['hostname']['new']
        if 'serial' in self.detected_diff:
            self.device.serial = self.detected_diff['serial']['new']
        if 'model' in self.detected_diff:
            from dcim.models import DeviceType
            target_model = self.detected_diff['model']['new']
            new_dt = (
                DeviceType.objects.filter(model=target_model).first()
                or DeviceType.objects.filter(model__iexact=target_model).first()
                or DeviceType.objects.filter(model__icontains=target_model.split('-')[0]).first()
            )
            if new_dt:
                self.device.device_type = new_dt
        if 'part_number' in self.detected_diff:
            from dcim.models import DeviceType
            target_pn = self.detected_diff['part_number']['new']
            matched_dt = (
                DeviceType.objects.filter(part_number=target_pn).first()
                or DeviceType.objects.filter(part_number__iexact=target_pn).first()
                or DeviceType.objects.filter(part_number__icontains=target_pn.split('-')[0]).first()
            )
            if matched_dt and 'model' not in self.detected_diff:
                # Only update device_type from part_number if model didn't already change it
                self.device.device_type = matched_dt
        if 'platform' in self.detected_diff:
            from dcim.models import Platform
            target_platform = self.detected_diff['platform']['new']
            new_platform = (
                Platform.objects.filter(name=target_platform).first()
                or Platform.objects.filter(name__iexact=target_platform).first()
                or Platform.objects.filter(slug__icontains=target_platform.lower().split()[0]).first()
            )
            if new_platform:
                self.device.platform = new_platform
        if 'platform_manufacturer' in self.detected_diff and self.device.platform:
            from dcim.models import Manufacturer
            mfr_name = self.detected_diff['platform_manufacturer']['new']
            mfr = (
                Manufacturer.objects.filter(name=mfr_name).first()
                or Manufacturer.objects.filter(name__iexact=mfr_name).first()
                or Manufacturer.objects.filter(slug__iexact=mfr_name.lower()).first()
            )
            if mfr and not self.device.platform.manufacturer:
                self.device.platform.manufacturer = mfr
                self.device.platform.save(update_fields=['manufacturer'])
        for cf_key in ['software_version', 'tacacs_source_interface', 'tacacs_source_ip', 'vrf']:
            if cf_key in self.detected_diff:
                self.device.custom_field_data[cf_key] = self.detected_diff[cf_key]['new']
        self.device.save()
        self.status = 'applied'
        self.save()
        return True


# ============================================================
# Compliance Trend Snapshots
# ============================================================

class ComplianceSnapshot(models.Model):
    """
    Stores a daily snapshot of compliance counts for trend charting.
    Captured after sync jobs complete or via a scheduled task.
    """
    date = models.DateField(unique=True)
    total_devices = models.IntegerField(default=0)
    compliant = models.IntegerField(default=0)
    non_compliant = models.IntegerField(default=0)
    ahead = models.IntegerField(default=0)
    unknown = models.IntegerField(default=0)

    class Meta:
        ordering = ['date']

    def __str__(self):
        return f"Snapshot {self.date}: {self.compliant}C / {self.non_compliant}NC"

