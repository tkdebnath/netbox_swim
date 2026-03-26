import django_filters
from netbox.filtersets import NetBoxModelFilterSet
from dcim.models import Platform, Device, DeviceType, Region, Site, DeviceRole
from .models import (
    SoftwareImage, GoldenImage, DeviceCompliance,
    WorkflowTemplate, UpgradeJob, DeploymentModeChoices, HardwareGroup,
    FileServer, DeviceSyncRecord, SyncJob
)


class HardwareGroupFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = HardwareGroup
        fields = ('id', 'name', 'slug', 'min_version', 'max_version', 'deployment_mode')


class FileServerFilterSet(NetBoxModelFilterSet):
    protocol = django_filters.MultipleChoiceFilter(
        choices=FileServer.ProtocolChoices.choices,
    )

    class Meta:
        model = FileServer
        fields = ('id', 'name', 'protocol', 'ip_address', 'base_path', 'priority', 'is_global_default')


class SoftwareImageFilterSet(NetBoxModelFilterSet):
    platform_id = django_filters.ModelMultipleChoiceFilter(
        field_name='platform',
        queryset=Platform.objects.all(),
        label='Platform (ID)',
    )
    image_type = django_filters.MultipleChoiceFilter(
        choices=SoftwareImage.ImageTypeChoices.choices,
    )

    class Meta:
        model = SoftwareImage
        fields = (
            'id', 'image_name', 'version', 'image_type', 'platform',
            'deployment_mode', 'image_file_name'
        )


class GoldenImageFilterSet(NetBoxModelFilterSet):
    device_type_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device_types',
        queryset=DeviceType.objects.all(),
        label='Device Type (ID)',
    )
    deployment_mode = django_filters.MultipleChoiceFilter(
        choices=DeploymentModeChoices.choices,
    )

    class Meta:
        model = GoldenImage
        fields = ('id', 'deployment_mode')


# ============================================================
# Helper: Generate standard lookup variant filters for related
# text fields, matching NetBox's device endpoint convention.
#   _ie  = iexact  (case-insensitive exact)
#   _ic  = icontains (case-insensitive contains)
#   _nic = NOT icontains
#   _isw = istartswith
#   _iew = iendswith
# ============================================================
def _text_filters(field_path, label):
    """Return a dict of CharFilter instances for standard lookup variants."""
    return {
        '': django_filters.CharFilter(field_name=field_path, lookup_expr='iexact', label=f'{label}'),
        '_ie': django_filters.CharFilter(field_name=field_path, lookup_expr='iexact', label=f'{label} (IE)'),
        '_ic': django_filters.CharFilter(field_name=field_path, lookup_expr='icontains', label=f'{label} (IC)'),
        '_nic': django_filters.CharFilter(field_name=field_path, lookup_expr='icontains', exclude=True, label=f'{label} (NIC)'),
        '_isw': django_filters.CharFilter(field_name=field_path, lookup_expr='istartswith', label=f'{label} (ISW)'),
        '_iew': django_filters.CharFilter(field_name=field_path, lookup_expr='iendswith', label=f'{label} (IEW)'),
    }


class DeviceComplianceFilterSet(NetBoxModelFilterSet):
    # -- ID filters --
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device', queryset=Device.objects.all(), label='Device (ID)',
    )
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__site', queryset=Site.objects.all(), label='Site (ID)',
    )
    region_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__site__region', queryset=Region.objects.all(), label='Region (ID)',
    )
    device_type_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__device_type', queryset=DeviceType.objects.all(), label='Device Type (ID)',
    )
    role_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__role', queryset=DeviceRole.objects.all(), label='Role (ID)',
    )
    platform_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__platform', queryset=Platform.objects.all(), label='Platform (ID)',
    )
    # -- Text lookup variants --
    device = django_filters.CharFilter(field_name='device__name', lookup_expr='iexact', label='Device')
    device_ie = django_filters.CharFilter(field_name='device__name', lookup_expr='iexact', label='Device (IE)')
    device_ic = django_filters.CharFilter(field_name='device__name', lookup_expr='icontains', label='Device (IC)')
    device_nic = django_filters.CharFilter(field_name='device__name', lookup_expr='icontains', exclude=True, label='Device (NIC)')
    device_isw = django_filters.CharFilter(field_name='device__name', lookup_expr='istartswith', label='Device (ISW)')
    device_iew = django_filters.CharFilter(field_name='device__name', lookup_expr='iendswith', label='Device (IEW)')

    site = django_filters.CharFilter(field_name='device__site__name', lookup_expr='iexact', label='Site')
    site_ic = django_filters.CharFilter(field_name='device__site__name', lookup_expr='icontains', label='Site (IC)')
    site_isw = django_filters.CharFilter(field_name='device__site__name', lookup_expr='istartswith', label='Site (ISW)')

    device_type = django_filters.CharFilter(field_name='device__device_type__model', lookup_expr='iexact', label='Device Type')
    device_type_ic = django_filters.CharFilter(field_name='device__device_type__model', lookup_expr='icontains', label='Device Type (IC)')

    role = django_filters.CharFilter(field_name='device__role__name', lookup_expr='iexact', label='Role')
    role_ic = django_filters.CharFilter(field_name='device__role__name', lookup_expr='icontains', label='Role (IC)')

    platform = django_filters.CharFilter(field_name='device__platform__name', lookup_expr='iexact', label='Platform')
    platform_ic = django_filters.CharFilter(field_name='device__platform__name', lookup_expr='icontains', label='Platform (IC)')

    status = django_filters.MultipleChoiceFilter(
        choices=[
            ('compliant', 'Compliant'),
            ('non_compliant', 'Non-Compliant'),
            ('unknown', 'Unknown'),
            ('error', 'Error'),
        ],
    )

    class Meta:
        model = DeviceCompliance
        fields = ('id', 'status')


class WorkflowTemplateFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = WorkflowTemplate
        fields = ('id', 'name', 'is_active')


class UpgradeJobFilterSet(NetBoxModelFilterSet):
    # -- ID filters --
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device', queryset=Device.objects.all(), label='Device (ID)',
    )
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__site', queryset=Site.objects.all(), label='Site (ID)',
    )
    region_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__site__region', queryset=Region.objects.all(), label='Region (ID)',
    )
    device_type_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__device_type', queryset=DeviceType.objects.all(), label='Device Type (ID)',
    )
    role_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__role', queryset=DeviceRole.objects.all(), label='Role (ID)',
    )
    platform_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__platform', queryset=Platform.objects.all(), label='Platform (ID)',
    )
    template_id = django_filters.ModelMultipleChoiceFilter(
        field_name='template', queryset=WorkflowTemplate.objects.all(), label='Workflow Template (ID)',
    )
    # -- Text lookup variants (device) --
    device = django_filters.CharFilter(field_name='device__name', lookup_expr='iexact', label='Device')
    device_ie = django_filters.CharFilter(field_name='device__name', lookup_expr='iexact', label='Device (IE)')
    device_ic = django_filters.CharFilter(field_name='device__name', lookup_expr='icontains', label='Device (IC)')
    device_nic = django_filters.CharFilter(field_name='device__name', lookup_expr='icontains', exclude=True, label='Device (NIC)')
    device_isw = django_filters.CharFilter(field_name='device__name', lookup_expr='istartswith', label='Device (ISW)')
    device_iew = django_filters.CharFilter(field_name='device__name', lookup_expr='iendswith', label='Device (IEW)')
    # -- Text lookup variants (site) --
    site = django_filters.CharFilter(field_name='device__site__name', lookup_expr='iexact', label='Site')
    site_ic = django_filters.CharFilter(field_name='device__site__name', lookup_expr='icontains', label='Site (IC)')
    site_isw = django_filters.CharFilter(field_name='device__site__name', lookup_expr='istartswith', label='Site (ISW)')
    # -- Text lookup variants (region) --
    region = django_filters.CharFilter(field_name='device__site__region__name', lookup_expr='iexact', label='Region')
    region_ic = django_filters.CharFilter(field_name='device__site__region__name', lookup_expr='icontains', label='Region (IC)')
    # -- Text lookup variants (device type) --
    device_type = django_filters.CharFilter(field_name='device__device_type__model', lookup_expr='iexact', label='Device Type')
    device_type_ic = django_filters.CharFilter(field_name='device__device_type__model', lookup_expr='icontains', label='Device Type (IC)')
    # -- Text lookup variants (role) --
    role = django_filters.CharFilter(field_name='device__role__name', lookup_expr='iexact', label='Role')
    role_ic = django_filters.CharFilter(field_name='device__role__name', lookup_expr='icontains', label='Role (IC)')
    # -- Text lookup variants (platform) --
    platform = django_filters.CharFilter(field_name='device__platform__name', lookup_expr='iexact', label='Platform')
    platform_ic = django_filters.CharFilter(field_name='device__platform__name', lookup_expr='icontains', label='Platform (IC)')
    # -- Status / scheduling --
    status = django_filters.MultipleChoiceFilter(
        choices=UpgradeJob.StatusChoices.choices,
    )
    scheduled = django_filters.BooleanFilter(
        field_name='scheduled_time', lookup_expr='isnull', exclude=True, label='Has Scheduled Time',
    )

    class Meta:
        model = UpgradeJob
        fields = ('id', 'status')


class DeviceSyncRecordFilterSet(NetBoxModelFilterSet):
    # -- ID filters --
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device', queryset=Device.objects.all(), label='Device (ID)',
    )
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__site', queryset=Site.objects.all(), label='Site (ID)',
    )
    region_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__site__region', queryset=Region.objects.all(), label='Region (ID)',
    )
    device_type_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__device_type', queryset=DeviceType.objects.all(), label='Device Type (ID)',
    )
    role_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__role', queryset=DeviceRole.objects.all(), label='Role (ID)',
    )
    platform_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device__platform', queryset=Platform.objects.all(), label='Platform (ID)',
    )
    sync_job_id = django_filters.ModelMultipleChoiceFilter(
        field_name='sync_job', queryset=SyncJob.objects.all(), label='Sync Job (ID)',
    )
    # -- Text lookup variants --
    device = django_filters.CharFilter(field_name='device__name', lookup_expr='iexact', label='Device')
    device_ie = django_filters.CharFilter(field_name='device__name', lookup_expr='iexact', label='Device (IE)')
    device_ic = django_filters.CharFilter(field_name='device__name', lookup_expr='icontains', label='Device (IC)')
    device_nic = django_filters.CharFilter(field_name='device__name', lookup_expr='icontains', exclude=True, label='Device (NIC)')
    device_isw = django_filters.CharFilter(field_name='device__name', lookup_expr='istartswith', label='Device (ISW)')
    device_iew = django_filters.CharFilter(field_name='device__name', lookup_expr='iendswith', label='Device (IEW)')

    site = django_filters.CharFilter(field_name='device__site__name', lookup_expr='iexact', label='Site')
    site_ic = django_filters.CharFilter(field_name='device__site__name', lookup_expr='icontains', label='Site (IC)')

    device_type = django_filters.CharFilter(field_name='device__device_type__model', lookup_expr='iexact', label='Device Type')
    device_type_ic = django_filters.CharFilter(field_name='device__device_type__model', lookup_expr='icontains', label='Device Type (IC)')

    role = django_filters.CharFilter(field_name='device__role__name', lookup_expr='iexact', label='Role')
    role_ic = django_filters.CharFilter(field_name='device__role__name', lookup_expr='icontains', label='Role (IC)')

    platform = django_filters.CharFilter(field_name='device__platform__name', lookup_expr='iexact', label='Platform')
    platform_ic = django_filters.CharFilter(field_name='device__platform__name', lookup_expr='icontains', label='Platform (IC)')

    status = django_filters.MultipleChoiceFilter(
        choices=[(k, v) for k, v, *c in DeviceSyncRecord.StatusChoices.CHOICES],
    )

    class Meta:
        model = DeviceSyncRecord
        fields = ('id', 'status')


class JobLogFilterSet(NetBoxModelFilterSet):
    job_id = django_filters.ModelMultipleChoiceFilter(
        field_name='job', queryset=UpgradeJob.objects.all(), label='Upgrade Job (ID)',
    )
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='job__device', queryset=Device.objects.all(), label='Device (ID)',
    )
    device = django_filters.CharFilter(field_name='job__device__name', lookup_expr='iexact', label='Device')
    device_ic = django_filters.CharFilter(field_name='job__device__name', lookup_expr='icontains', label='Device (IC)')
    device_isw = django_filters.CharFilter(field_name='job__device__name', lookup_expr='istartswith', label='Device (ISW)')

    action_type = django_filters.CharFilter(lookup_expr='iexact', label='Action Type')
    action_type_ic = django_filters.CharFilter(field_name='action_type', lookup_expr='icontains', label='Action Type (IC)')
    is_success = django_filters.BooleanFilter(label='Success')

    class Meta:
        from .models import JobLog
        model = JobLog
        fields = ('id', 'action_type', 'is_success')


class SyncJobFilterSet(NetBoxModelFilterSet):
    status = django_filters.MultipleChoiceFilter(
        choices=[
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
    )

    class Meta:
        model = SyncJob
        fields = ('id', 'status', 'connection_library')


class ComplianceDashboardFilterSet(django_filters.FilterSet):
    """
    Filters Device objects for the Compliance Dashboard.
    Also includes a virtual 'severity' filter handled in the view.
    """
    q = django_filters.CharFilter(
        method='search',
        label='Search',
    )
    site_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site',
        queryset=Site.objects.all(),
        label='Site',
    )
    region_id = django_filters.ModelMultipleChoiceFilter(
        field_name='site__region',
        queryset=Region.objects.all(),
        label='Region',
    )
    platform_id = django_filters.ModelMultipleChoiceFilter(
        field_name='platform',
        queryset=Platform.objects.all(),
        label='Platform',
    )
    device_type_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device_type',
        queryset=DeviceType.objects.all(),
        label='Device Type',
    )
    role_id = django_filters.ModelMultipleChoiceFilter(
        field_name='role',
        queryset=DeviceRole.objects.all(),
        label='Role',
    )
    severity = django_filters.ChoiceFilter(
        method='filter_severity',
        label='Severity',
        choices=[
            ('', '---------'),
            ('Compliant', 'Compliant'),
            ('Ahead', 'Ahead'),
            ('Low', 'Low'),
            ('Medium', 'Medium'),
            ('High', 'High'),
            ('Critical', 'Critical'),
            ('Unknown', 'Unknown'),
        ],
    )
    hardware_group = django_filters.ModelChoiceFilter(
        method='filter_hw_group',
        label='Hardware Group',
        queryset=HardwareGroup.objects.all(),
    )

    class Meta:
        model = Device
        fields = ['q', 'site_id', 'region_id', 'platform_id', 'device_type_id', 'role_id']

    def search(self, queryset, name, value):
        if not value.strip():
            return queryset
        return queryset.filter(name__icontains=value)

    def filter_severity(self, queryset, name, value):
        # Handled post-query in the view (virtual filter)
        return queryset

    def filter_hw_group(self, queryset, name, value):
        # Handled post-query in the view (virtual filter)
        return queryset

