import django_filters
from netbox.filtersets import NetBoxModelFilterSet
from dcim.models import Platform, Device, DeviceType
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
        fields = ('id', 'name', 'protocol', 'ip_address', 'base_path')


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
        field_name='device_type',
        queryset=DeviceType.objects.all(),
        label='Device Type (ID)',
    )
    deployment_mode = django_filters.MultipleChoiceFilter(
        choices=DeploymentModeChoices.choices,
    )

    class Meta:
        model = GoldenImage
        fields = ('id', 'device_type', 'deployment_mode')


class DeviceComplianceFilterSet(NetBoxModelFilterSet):
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device',
        queryset=Device.objects.all(),
        label='Device (ID)',
    )
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
        fields = ('id', 'device', 'status')


class WorkflowTemplateFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = WorkflowTemplate
        fields = ('id', 'name', 'is_active')


class UpgradeJobFilterSet(NetBoxModelFilterSet):
    device_id = django_filters.ModelMultipleChoiceFilter(
        field_name='device',
        queryset=Device.objects.all(),
        label='Device (ID)',
    )
    status = django_filters.MultipleChoiceFilter(
        choices=UpgradeJob.StatusChoices.choices,
    )

    class Meta:
        model = UpgradeJob
        fields = ('id', 'device', 'target_image', 'template', 'status')


class DeviceSyncRecordFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = DeviceSyncRecord
        fields = ('id', 'device', 'status')

class SyncJobFilterSet(NetBoxModelFilterSet):
    class Meta:
        model = SyncJob
        fields = ('id', 'status')
