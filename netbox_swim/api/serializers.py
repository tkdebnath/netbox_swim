from rest_framework import serializers
from netbox.api.serializers import NetBoxModelSerializer
from ..models import (
    SoftwareImage, GoldenImage, DeviceCompliance,
    WorkflowTemplate, WorkflowStep, UpgradeJob, JobLog,
    HardwareGroup, FileServer, DeviceSyncRecord, SyncJob,
    ValidationCheck, CheckTemplate
)
from dcim.api.serializers import PlatformSerializer, DeviceTypeSerializer, RegionSerializer, SiteSerializer, DeviceSerializer

class HardwareGroupSerializer(NetBoxModelSerializer):
    platforms = PlatformSerializer(many=True, required=False, nested=True)
    device_types = DeviceTypeSerializer(many=True, required=False, nested=True)
    class Meta:
        model = HardwareGroup
        fields = (
            'id', 'display', 'name', 'slug', 'platforms', 'device_types',
            'min_version', 'max_version', 'deployment_mode', 'is_static',
            'manual_includes', 'manual_excludes', 'connection_priority',
            'workflow_template', 'description',
            'tags', 'custom_fields', 'created', 'last_updated',
        )

class FileServerSerializer(NetBoxModelSerializer):
    regions = RegionSerializer(many=True, required=False, nested=True)
    sites = SiteSerializer(many=True, required=False, nested=True)
    devices = DeviceSerializer(many=True, required=False, nested=True)
    class Meta:
        model = FileServer
        fields = (
            'id', 'display', 'name', 'protocol', 'ip_address', 'port',
            'username', 'password', 'base_path', 'regions', 'sites', 'devices',
            'description', 'tags', 'custom_fields', 'created', 'last_updated',
        )

class SoftwareImageSerializer(NetBoxModelSerializer):
    platform = PlatformSerializer(required=False, nested=True)
    device_types = DeviceTypeSerializer(many=True, required=False, nested=True)
    class Meta:
        model = SoftwareImage
        fields = (
            'id', 'display', 'image_name', 'image_file_name', 'version',
            'image_type', 'file_server', 'platform', 'device_types', 'hardware_groups',
            'deployment_mode', 'min_source_version', 'max_source_version',
            'file_size_bytes', 'hash_md5',
            'hash_sha256', 'hash_sha512', 'release_notes_url',
            'min_ram_mb', 'min_flash_mb', 'description',
            'tags', 'custom_fields', 'created', 'last_updated',
        )


class GoldenImageSerializer(NetBoxModelSerializer):
    class Meta:
        model = GoldenImage
        fields = (
            'id', 'display', 'device_types', 'hardware_groups', 'deployment_mode',
            'image', 'description', 'tags', 'custom_fields', 'created', 'last_updated',
        )

class DeviceComplianceSerializer(NetBoxModelSerializer):
    class Meta:
        model = DeviceCompliance
        fields = (
            'id', 'display', 'device', 'status', 'current_version',
            'expected_version', 'last_checked', 'detail',
            'tags', 'custom_fields', 'created', 'last_updated',
        )


class WorkflowTemplateSerializer(NetBoxModelSerializer):
    class Meta:
        model = WorkflowTemplate
        fields = (
            'id', 'display', 'name', 'description', 'is_active',
            'tags', 'custom_fields', 'created', 'last_updated',
        )


class WorkflowStepSerializer(NetBoxModelSerializer):
    class Meta:
        model = WorkflowStep
        fields = (
            'id', 'display', 'template', 'order', 'action_type',
            'extra_config', 'tags', 'custom_fields', 'created', 'last_updated',
        )


class UpgradeJobSerializer(NetBoxModelSerializer):
    class Meta:
        model = UpgradeJob
        fields = (
            'id', 'display', 'template', 'device', 'target_image',
            'status', 'scheduled_time', 'start_time', 'end_time', 'extra_config',
            'tags', 'custom_fields', 'created', 'last_updated',
        )


class JobLogSerializer(NetBoxModelSerializer):
    class Meta:
        model = JobLog
        fields = (
            'id', 'display', 'job', 'step', 'action_type',
            'is_success', 'log_output', 'timestamp',
            'tags', 'custom_fields', 'created', 'last_updated',
        )

class SyncJobSerializer(NetBoxModelSerializer):
    class Meta:
        model = SyncJob
        fields = (
            'id', 'display', 'start_time', 'end_time', 'status',
            'connection_library', 'max_concurrency', 'selected_device_count',
            'failed_device_count', 'summary_logs',
            'tags', 'custom_fields', 'created', 'last_updated',
        )

class DeviceSyncRecordSerializer(NetBoxModelSerializer):
    class Meta:
        model = DeviceSyncRecord
        fields = (
            'id', 'display', 'device', 'sync_job', 'status', 'detected_diff',
            'live_facts', 'log_messages', 'job_id', 'is_active',
            'tags', 'custom_fields', 'created', 'last_updated',
        )

class ValidationCheckSerializer(NetBoxModelSerializer):
    class Meta:
        model = ValidationCheck
        fields = (
            'id', 'display', 'name', 'description', 'category',
            'command', 'phase',
            'tags', 'custom_fields', 'created', 'last_updated',
        )

class CheckTemplateSerializer(NetBoxModelSerializer):
    checks = ValidationCheckSerializer(many=True, read_only=True)
    class Meta:
        model = CheckTemplate
        fields = (
            'id', 'display', 'name', 'description', 'checks',
            'tags', 'custom_fields', 'created', 'last_updated',
        )
