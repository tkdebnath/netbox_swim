from django import forms
from netbox.forms import NetBoxModelForm, NetBoxModelImportForm
from utilities.forms.fields import DynamicModelChoiceField, DynamicModelMultipleChoiceField
from dcim.models import Platform, Device, DeviceType, Region, Site
from . import models


class HardwareGroupForm(NetBoxModelForm):
    platforms = DynamicModelMultipleChoiceField(
        queryset=Platform.objects.all(),
        required=False,
    )
    device_types = DynamicModelMultipleChoiceField(
        queryset=DeviceType.objects.all(),
        required=False,
    )

    class Meta:
        model = models.HardwareGroup
        fields = (
            'name', 'platforms',
            'device_types',
            'deployment_mode',
            'workflow_template', 'connection_priority',
            'min_version', 'max_version', 'description', 'tags',
        )

# --- CSV Import Forms ---
class HardwareGroupCSVForm(NetBoxModelImportForm):
    class Meta:
        model = models.HardwareGroup
        fields = ('name', 'slug', 'deployment_mode', 'min_version', 'max_version', 'description')

class FileServerCSVForm(NetBoxModelImportForm):
    class Meta:
        model = models.FileServer
        fields = ('name', 'protocol', 'ip_address', 'base_path', 'username', 'password', 'port', 'description')

class SoftwareImageCSVForm(NetBoxModelImportForm):
    class Meta:
        model = models.SoftwareImage
        fields = ('image_name', 'version', 'image_type', 'deployment_mode', 'image_file_name', 'file_size_bytes', 'hash_md5', 'description')

class GoldenImageCSVForm(NetBoxModelImportForm):
    class Meta:
        model = models.GoldenImage
        fields = ('deployment_mode', 'description')

class WorkflowTemplateCSVForm(NetBoxModelImportForm):
    class Meta:
        model = models.WorkflowTemplate
        fields = ('name', 'description', 'is_active')


class FileServerForm(NetBoxModelForm):
    regions = DynamicModelMultipleChoiceField(
        queryset=Region.objects.all(),
        required=False,
    )
    sites = DynamicModelMultipleChoiceField(
        queryset=Site.objects.all(),
        required=False,
    )
    devices = DynamicModelMultipleChoiceField(
        queryset=Device.objects.all(),
        required=False,
    )

    class Meta:
        model = models.FileServer
        fields = (
            'name', 'protocol', 'ip_address', 'port', 'username', 'password',
            'base_path', 'regions', 'sites', 'devices', 'description', 'tags',
        )


class SoftwareImageForm(NetBoxModelForm):
    platform = DynamicModelChoiceField(queryset=Platform.objects.all())
    device_types = DynamicModelMultipleChoiceField(
        queryset=DeviceType.objects.all(),
        required=False,
    )
    hardware_groups = DynamicModelMultipleChoiceField(
        queryset=models.HardwareGroup.objects.all(),
        required=False,
    )

    class Meta:
        model = models.SoftwareImage
        fields = (
            'image_name', 'image_file_name', 'version', 'image_type',
            'file_server', 'platform', 'device_types', 'hardware_groups', 'deployment_mode',
            'min_source_version', 'max_source_version',
            'file_size_bytes', 'hash_md5', 'hash_sha256',
            'hash_sha512', 'release_notes_url', 'min_ram_mb',
            'min_flash_mb', 'description', 'tags',
        )


class GoldenImageForm(NetBoxModelForm):
    device_type = DynamicModelChoiceField(queryset=DeviceType.objects.all(), required=False)
    hardware_group = DynamicModelChoiceField(queryset=models.HardwareGroup.objects.all(), required=False)
    image = DynamicModelChoiceField(queryset=models.SoftwareImage.objects.all())

    class Meta:
        model = models.GoldenImage
        fields = ('device_type', 'hardware_group', 'deployment_mode', 'image', 'description', 'tags')


class WorkflowTemplateForm(NetBoxModelForm):
    class Meta:
        model = models.WorkflowTemplate
        fields = ('name', 'description', 'is_active', 'tags')


# ============================================================
# Device Sync (Bulk Actions)
# ============================================================

from django import forms as django_forms
from utilities.forms.fields import DynamicModelMultipleChoiceField, DynamicModelChoiceField
from dcim import models as dcim_models

class BulkSyncForm(django_forms.Form):
    region = DynamicModelMultipleChoiceField(
        queryset=dcim_models.Region.objects.all(),
        required=False,
        label='Region'
    )
    site = DynamicModelMultipleChoiceField(
        queryset=dcim_models.Site.objects.all(),
        required=False,
        query_params={
            'region_id': '$region'
        },
        label='Site'
    )
    device_role = DynamicModelMultipleChoiceField(
        queryset=dcim_models.DeviceRole.objects.all(),
        required=False,
        label='Role'
    )
    device = DynamicModelMultipleChoiceField(
        queryset=dcim_models.Device.objects.all(),
        required=False,
        query_params={
            'site_id': '$site',
            'role_id': '$device_role',
            'has_primary_ip': 'true'
        },
        label='Specific Device(s)',
        help_text='If left blank, ALL devices in the selected sites/regions with a primary IP will be synced.'
    )
    has_primary_ip = django_forms.BooleanField(
        required=False,
        initial=True,
        label="Must Have Primary IP",
        help_text="Only attempt to sync devices that have a primary IP configured."
    )
    auto_update = django_forms.BooleanField(
        required=False,
        label="Auto-Apply Updates",
        help_text="If unchecked, changes are held as Pending Records for your review."
    )
    max_concurrency = django_forms.IntegerField(
        required=False,
        initial=5,
        min_value=1,
        max_value=20,
        label="Concurrency Limit",
        help_text="Maximum simultaneous SSH connections to open across the network."
    )
    connection_library = django_forms.ChoiceField(
        choices=[
            ('scrapli', 'Scrapli (Fastest)'),
            ('netmiko', 'Netmiko (Traditional)'),
            ('unicon', 'Unicon (Comprehensive/pyATS)'),
        ],
        initial='scrapli',
        required=False,
        label='Connection Library',
        help_text='Choose the transport module to use for this sync batch.'
    )

class BulkUpgradeForm(django_forms.Form):
    region = DynamicModelMultipleChoiceField(
        queryset=dcim_models.Region.objects.all(),
        required=False,
        label='Region'
    )
    site = DynamicModelMultipleChoiceField(
        queryset=dcim_models.Site.objects.all(),
        required=False,
        query_params={
            'region_id': '$region'
        },
        label='Site'
    )
    device_role = DynamicModelMultipleChoiceField(
        queryset=dcim_models.DeviceRole.objects.all(),
        required=False,
        label='Role'
    )
    device = DynamicModelMultipleChoiceField(
        queryset=dcim_models.Device.objects.all(),
        required=False,
        query_params={
            'site_id': '$site',
            'role_id': '$device_role',
            'has_primary_ip': 'true'
        },
        label='Specific Device(s)',
        help_text='If left blank, ALL Non-Compliant matching devices will be scheduled for Upgrade.'
    )
    connection_library = django_forms.ChoiceField(
        choices=[
            ('scrapli', 'Scrapli (Default & Fastest)'),
            ('netmiko', 'Netmiko (Broadest Support)'),
            ('unicon', 'pyATS Unicon')
        ],
        required=False,
        initial='scrapli',
        label="Execution Driver Override"
    )
    execution_mode = django_forms.ChoiceField(
        choices=(
            ('execute', 'Execute Run (Full Live Execution)'),
            ('dry_run', 'Dry Run (Real Read, Mock Write)'),
            ('mock_run', 'Mock Run (Fully Simulated)'),
        ),
        required=True,
        initial='execute',
        widget=django_forms.RadioSelect(attrs={'class': 'list-unstyled'}),
        label="Execution Mode",
        help_text="Select the execution mode for this workflow."
    )
    scheduled_time = django_forms.DateTimeField(
        required=False,
        label='Schedule For (Maintenance Window)',
        help_text='Leave blank to execute immediately. Set a future date/time to defer execution to a maintenance window.',
        widget=django_forms.DateTimeInput(attrs={
            'type': 'datetime-local',
            'class': 'form-control',
        }),
    )


class UpgradeJobForm(NetBoxModelForm):
    device = DynamicModelChoiceField(queryset=Device.objects.all())
    target_image = DynamicModelChoiceField(
        queryset=models.SoftwareImage.objects.all(),
        required=False,
    )
    template = DynamicModelChoiceField(
        queryset=models.WorkflowTemplate.objects.all(),
        required=False,
    )

    class Meta:
        model = models.UpgradeJob
        fields = (
            'device', 'target_image', 'template', 'status',
            'scheduled_time', 'start_time', 'tags',
        )
        widgets = {
            'scheduled_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }

class WorkflowStepForm(NetBoxModelForm):
    template = DynamicModelChoiceField(queryset=models.WorkflowTemplate.objects.all())
    
    connection_library = django_forms.ChoiceField(
        choices=[
            ('auto', 'Auto (From Hardware Group)'),
            ('scrapli', 'Scrapli'),
            ('netmiko', 'Netmiko'),
            ('unicon', 'pyATS Unicon'),
            ('requests', 'HTTP / Requests API'),
        ],
        required=False,
        initial='auto',
        label="Execution Driver Override",
        help_text="Explicitly override the backend script driver for this specific step.",
    )

    wait_duration = django_forms.IntegerField(
        required=False,
        label="Wait Duration (Seconds)",
        help_text="Used specifically for 'Wait Timer' steps. (e.g. 300)"
    )
    ping_target = forms.CharField(
        required=False,
        label="Ping Target IP (Optional)",
        help_text="Used for 'Ping Reachability' steps. If blank, targets the Device's Primary IP."
    )
    check_template = forms.ModelChoiceField(
        queryset=models.CheckTemplate.objects.all(),
        required=False,
        label="Validation Check Template",
        help_text="Used specifically for 'Pre-Upgrade' or 'Post-Upgrade' validations."
    )

    class Meta:
        model = models.WorkflowStep
        fields = ('template', 'order', 'action_type', 'connection_library', 'wait_duration', 'ping_target', 'check_template', 'extra_config')
        widgets = {
            'extra_config': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.extra_config:
            self.initial['connection_library'] = self.instance.extra_config.get('connection_library', 'auto')
            self.initial['wait_duration'] = self.instance.extra_config.get('duration')
            self.initial['ping_target'] = self.instance.extra_config.get('target_ip')
            self.initial['check_template'] = self.instance.extra_config.get('check_template_id')

    def save(self, *args, **kwargs):
        step = super().save(commit=False)
        # Force a dict if None
        if not step.extra_config or not isinstance(step.extra_config, dict):
            step.extra_config = {}
        
        # Write the selected override into the JSON payload Native dict
        lib = self.cleaned_data.get('connection_library')
        if lib and lib != 'auto':
            step.extra_config['connection_library'] = lib
        else:
            step.extra_config.pop('connection_library', None)

        dur = self.cleaned_data.get('wait_duration')
        if dur:
            step.extra_config['duration'] = dur
        else:
            step.extra_config.pop('duration', None)

        tgt = self.cleaned_data.get('ping_target')
        if tgt:
            step.extra_config['target_ip'] = tgt
        else:
            step.extra_config.pop('target_ip', None)
            
        tpl = self.cleaned_data.get('check_template')
        if tpl:
            step.extra_config['check_template_id'] = tpl.pk
        else:
            step.extra_config.pop('check_template_id', None)
        
        step.save()
        return step

class ValidationCheckForm(NetBoxModelForm):
    class Meta:
        model = models.ValidationCheck
        fields = ('name', 'description', 'category', 'command', 'phase', 'tags')

class ValidationCheckCSVForm(NetBoxModelImportForm):
    class Meta:
        model = models.ValidationCheck
        fields = ('name', 'description', 'category', 'command', 'phase')

class CheckTemplateForm(NetBoxModelForm):
    checks = forms.ModelMultipleChoiceField(
        queryset=models.ValidationCheck.objects.all(),
        required=False
    )
    class Meta:
        model = models.CheckTemplate
        fields = ('name', 'description', 'checks', 'tags')

class CheckTemplateCSVForm(NetBoxModelImportForm):
    class Meta:
        model = models.CheckTemplate
        fields = ('name', 'description')
