import django_tables2 as tables
from netbox.tables import NetBoxTable, ChoiceFieldColumn, columns
from . import models
from .models import (
    SoftwareImage,
    FileServer, GoldenImage, DeviceCompliance,
    WorkflowTemplate, UpgradeJob, JobLog, HardwareGroup,
    DeviceSyncRecord, SyncJob
)


class HardwareGroupTable(NetBoxTable):
    name = tables.Column(linkify=True)
    deployment_mode = ChoiceFieldColumn()
    platforms = columns.ManyToManyColumn(linkify_item=True)
    device_types = columns.ManyToManyColumn(linkify_item=True)

    class Meta(NetBoxTable.Meta):
        model = HardwareGroup
        fields = ('pk', 'id', 'name', 'slug', 'platforms', 'device_types', 'deployment_mode', 'min_version', 'max_version', 'description', 'created', 'last_updated')
        default_columns = ('name', 'platforms', 'device_types', 'deployment_mode', 'min_version', 'max_version', 'description')


class FileServerTable(NetBoxTable):
    name = tables.Column(linkify=True)
    protocol = ChoiceFieldColumn()

    class Meta(NetBoxTable.Meta):
        model = FileServer
        fields = ('pk', 'id', 'name', 'protocol', 'ip_address', 'base_path', 'actions')
        default_columns = ('name', 'protocol', 'ip_address', 'base_path')


class SoftwareImageTable(NetBoxTable):
    image_name = tables.Column(linkify=True)
    platform = tables.Column(linkify=True)
    image_type = ChoiceFieldColumn()
    deployment_mode = ChoiceFieldColumn()

    class Meta(NetBoxTable.Meta):
        model = SoftwareImage
        fields = (
            'pk', 'id', 'platform', 'image_name', 'version',
            'image_type', 'deployment_mode', 'file_server', 'hardware_groups', 'image_file_name',
            'min_source_version', 'max_source_version',
            'file_size_bytes', 'hash_md5', 'created', 'last_updated',
        )
        default_columns = (
            'platform', 'image_name', 'version', 'image_type',
            'deployment_mode', 'file_server', 'image_file_name'
        )


class GoldenImageTable(NetBoxTable):
    device_types = columns.ManyToManyColumn(linkify_item=True)
    hardware_groups = columns.ManyToManyColumn(linkify_item=True)
    deployment_mode = ChoiceFieldColumn()
    image = tables.Column(linkify=True)

    class Meta(NetBoxTable.Meta):
        model = GoldenImage
        fields = ('pk', 'id', 'device_types', 'hardware_groups', 'deployment_mode', 'image', 'description', 'created', 'last_updated')
        default_columns = ('device_types', 'hardware_groups', 'deployment_mode', 'image', 'description')


class DeviceComplianceTable(NetBoxTable):
    device = tables.Column(linkify=True)
    status = ChoiceFieldColumn()

    class Meta(NetBoxTable.Meta):
        model = DeviceCompliance
        fields = (
            'pk', 'id', 'device', 'status', 'current_version',
            'expected_version', 'last_checked', 'detail',
        )
        default_columns = ('device', 'status', 'current_version', 'expected_version', 'last_checked')


class WorkflowTemplateTable(NetBoxTable):
    name = tables.Column(linkify=True)

    class Meta(NetBoxTable.Meta):
        model = WorkflowTemplate
        fields = ('pk', 'id', 'name', 'status', 'description', 'device', 'target_image', 'tags')
        default_columns = ('name', 'device', 'status', 'target_image')


class ValidationCheckTable(NetBoxTable):
    name = tables.Column(linkify=True)
    class Meta(NetBoxTable.Meta):
        model = models.ValidationCheck
        fields = ('pk', 'id', 'name', 'category', 'command', 'phase', 'tags')
        default_columns = ('pk', 'name', 'category', 'command', 'phase')

class CheckTemplateTable(NetBoxTable):
    name = tables.Column(linkify=True)
    class Meta(NetBoxTable.Meta):
        model = models.CheckTemplate
        fields = ('pk', 'id', 'name', 'description', 'tags')
        default_columns = ('pk', 'name', 'description')

class UpgradeJobTable(NetBoxTable):
    device = tables.Column(linkify=True)
    target_image = tables.Column(linkify=True)
    template = tables.Column(linkify=True)
    status = ChoiceFieldColumn()

    class Meta(NetBoxTable.Meta):
        model = UpgradeJob
        fields = (
            'pk', 'id', 'device', 'target_image', 'template',
            'status', 'scheduled_time', 'start_time', 'end_time',
            'created', 'last_updated',
        )
        default_columns = ('device', 'target_image', 'status', 'scheduled_time')


class JobLogTable(NetBoxTable):
    job = tables.Column(linkify=True)
    action_type = tables.Column(linkify=True)
    is_success = columns.BooleanColumn()

    class Meta(NetBoxTable.Meta):
        model = JobLog
        fields = ('pk', 'id', 'job', 'action_type', 'step', 'is_success', 'log_output', 'timestamp')
        default_columns = ('job', 'action_type', 'step', 'is_success', 'timestamp')



class DeviceSyncRecordTable(NetBoxTable):
    device = tables.Column(linkify=True)
    status = ChoiceFieldColumn()
    live_facts = tables.TemplateColumn(
        template_code='''
            {% if record.live_facts %}
                {% for key, val in record.live_facts.items %}
                    {% if val %}
                    <strong>{{ key }}:</strong> <span class="text-secondary">{{ val }}</span><br>
                    {% endif %}
                {% endfor %}
            {% else %}
                <span class="text-muted small">No data gathered</span>
            {% endif %}
        ''',
        verbose_name='Live Network Facts',
        orderable=False
    )
    old_values = tables.TemplateColumn(
        template_code='''
            {% if record.detected_diff %}
                {% for key, val in record.detected_diff.items %}
                    <strong>{{ key }}:</strong> <span class="text-danger">{{ val.old|default:"None" }}</span><br>
                {% endfor %}
            {% else %}
                <span class="text-success small fw-bold">✓ Matches Live</span>
            {% endif %}
        ''',
        verbose_name='Old Values',
        orderable=False
    )
    new_values = tables.TemplateColumn(
        template_code='''
            {% if record.detected_diff %}
                {% for key, val in record.detected_diff.items %}
                    <strong>{{ key }}:</strong> <span class="text-success">{{ val.new|default:"None" }}</span><br>
                {% endfor %}
            {% else %}
                <span class="text-muted">—</span>
            {% endif %}
        ''',
        verbose_name='New Discovered Diff',
        orderable=False
    )
    actions = columns.ActionsColumn(actions=('delete',))
    
    class Meta(NetBoxTable.Meta):
        model = DeviceSyncRecord
        fields = ('pk', 'id', 'device', 'status', 'live_facts', 'old_values', 'new_values', 'created', 'actions')
        default_columns = ('pk', 'device', 'status', 'live_facts', 'old_values', 'new_values', 'created', 'actions')

class SyncJobTable(NetBoxTable):
    pk = tables.Column(linkify=True)
    status = tables.Column()
    start_time = tables.Column()
    actions = columns.ActionsColumn(actions=('delete',))
    
    class Meta(NetBoxTable.Meta):
        model = SyncJob
        fields = ('pk', 'status', 'start_time', 'end_time', 'selected_device_count', 'failed_device_count', 'actions')
        default_columns = ('pk', 'status', 'start_time', 'selected_device_count', 'failed_device_count', 'actions')


# =================================================================
# Compliance Dashboard Table (non-model, powered by device queryset)
# =================================================================

class ComplianceDashboardTable(tables.Table):
    """
    A standalone django-tables2 table that renders compliance data.
    Each row is a dict, not a model instance, so we use accessors.
    """
    pk = tables.CheckBoxColumn(accessor='device_pk', attrs={
        'td__input': {'name': 'pk', 'value': tables.A('device_pk')},
    })
    device_name = tables.TemplateColumn(
        template_code='<a href="{{ record.device_url }}">{{ record.device_name }}</a>',
        verbose_name='Device',
        orderable=True,
    )
    site = tables.Column(accessor='site_name', verbose_name='Site', orderable=True)
    platform = tables.Column(accessor='platform_name', verbose_name='Platform', orderable=True)
    device_type = tables.Column(accessor='device_type_name', verbose_name='Device Type', orderable=True)
    hw_group_name = tables.TemplateColumn(
        template_code='''
            {% if record.hw_group_url %}
            <a href="{{ record.hw_group_url }}">{{ record.hw_group_name }}</a>
            {% else %}
            <span class="text-muted">No Group</span>
            {% endif %}
        ''',
        verbose_name='Hardware Group',
        orderable=True,
    )
    current_version = tables.TemplateColumn(
        template_code='''
            {% if record.current_version %}
            <code>{{ record.current_version }}</code>
            {% else %}
            <span class="text-muted">Not Synced</span>
            {% endif %}
        ''',
        verbose_name='Running Version',
        orderable=True,
    )
    golden_version = tables.TemplateColumn(
        template_code='''
            {% if record.golden_version %}
            <code>{{ record.golden_version }}</code>
            {% else %}
            <span class="text-muted">No Baseline</span>
            {% endif %}
        ''',
        verbose_name='Golden Version',
        orderable=True,
    )
    gap_display = tables.Column(accessor='gap_display', verbose_name='Version Gap', orderable=False)
    severity = tables.TemplateColumn(
        template_code='''
            {% if record.severity_css == "orange" %}
            <span class="badge" style="background-color: #fd7e14; color: #fff;">{{ record.severity }}</span>
            {% elif record.severity_css == "dark" %}
            <span class="badge text-bg-dark">{{ record.severity }}</span>
            {% else %}
            <span class="badge text-bg-{{ record.severity_css }}">{{ record.severity }}</span>
            {% endif %}
        ''',
        verbose_name='Severity',
        orderable=True,
    )

    class Meta:
        attrs = {'class': 'table table-hover object-list'}
        row_attrs = {'class': 'object-row'}
        orderable = True

