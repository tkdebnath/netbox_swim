from rest_framework.decorators import action
from rest_framework.response import Response
from netbox.api.viewsets import NetBoxModelViewSet
from .. import models, filtersets
from . import serializers



class HardwareGroupViewSet(NetBoxModelViewSet):
    queryset = models.HardwareGroup.objects.prefetch_related('platforms', 'device_types', 'tags')
    serializer_class = serializers.HardwareGroupSerializer
    filterset_class = filtersets.HardwareGroupFilterSet


class SoftwareImageViewSet(NetBoxModelViewSet):
    queryset = models.SoftwareImage.objects.prefetch_related('platform', 'tags')
    serializer_class = serializers.SoftwareImageSerializer
    filterset_class = filtersets.SoftwareImageFilterSet


class FileServerViewSet(NetBoxModelViewSet):
    queryset = models.FileServer.objects.prefetch_related('regions', 'sites', 'devices', 'tags')
    serializer_class = serializers.FileServerSerializer
    filterset_class = filtersets.FileServerFilterSet


class GoldenImageViewSet(NetBoxModelViewSet):
    queryset = models.GoldenImage.objects.prefetch_related('platform', 'image', 'tags')
    serializer_class = serializers.GoldenImageSerializer
    filterset_class = filtersets.GoldenImageFilterSet


class DeviceComplianceViewSet(NetBoxModelViewSet):
    queryset = models.DeviceCompliance.objects.prefetch_related('device', 'tags')
    serializer_class = serializers.DeviceComplianceSerializer
    filterset_class = filtersets.DeviceComplianceFilterSet


class WorkflowTemplateViewSet(NetBoxModelViewSet):
    queryset = models.WorkflowTemplate.objects.prefetch_related('tags')
    serializer_class = serializers.WorkflowTemplateSerializer
    filterset_class = filtersets.WorkflowTemplateFilterSet

class ValidationCheckViewSet(NetBoxModelViewSet):
    queryset = models.ValidationCheck.objects.prefetch_related('tags')
    serializer_class = serializers.ValidationCheckSerializer
    # filterset_class = filtersets.ValidationCheckFilterSet

class CheckTemplateViewSet(NetBoxModelViewSet):
    queryset = models.CheckTemplate.objects.prefetch_related('checks', 'tags')
    serializer_class = serializers.CheckTemplateSerializer
    # filterset_class = filtersets.CheckTemplateFilterSet


class WorkflowStepViewSet(NetBoxModelViewSet):
    queryset = models.WorkflowStep.objects.prefetch_related('template', 'tags')
    serializer_class = serializers.WorkflowStepSerializer


class UpgradeJobViewSet(NetBoxModelViewSet):
    queryset = models.UpgradeJob.objects.prefetch_related('template', 'device', 'target_image', 'tags')
    serializer_class = serializers.UpgradeJobSerializer
    filterset_class = filtersets.UpgradeJobFilterSet

    @action(detail=True, methods=['post'])
    def run(self, request, pk=None):
        """Enqueue the upgrade job for processing by a background worker."""
        job = self.get_object()
        if job.status in [
            models.UpgradeJob.StatusChoices.RUNNING,
            models.UpgradeJob.StatusChoices.COMPLETED,
            models.UpgradeJob.StatusChoices.DISTRIBUTING,
            models.UpgradeJob.StatusChoices.ACTIVATING,
        ]:
            return Response({"error": f"Job is already {job.get_status_display()}."}, status=400)

        # Handle optional payload from API
        conn_override = request.data.get('connection_priority') or request.data.get('connection_module')
        if conn_override:
            if not isinstance(job.extra_config, dict):
                job.extra_config = {}
            job.extra_config['connection_priority_override'] = conn_override
            job.save()

        from ..engine import execute_upgrade_job
        execute_upgrade_job.delay(job.id)

        return Response({"status": "Upgrade job enqueued successfully."})
        
    @action(detail=True, methods=['get'])
    def dry_run(self, request, pk=None):
        """Returns a static linear execution prediction of what the step Engine will do"""
        job = self.get_object()
        from ..engine import generate_pipeline_plan
        plan = generate_pipeline_plan(job.id)
        return Response({"pipeline_plan": plan})

    @action(detail=False, methods=['post'])
    def execute_bulk_remediation(self, request):
        """API Endpoint: Pass {'device_ids': [1,2,3]} to queue Upgrade Jobs"""
        device_ids = request.data.get('device_ids', [])
        connection_library = request.data.get('connection_library', 'scrapli')
        execution_mode = request.data.get('execution_mode', 'execute')
        
        if not device_ids:
            return Response({"error": "No device_ids provided"}, status=400)
            
        import django_rq
        from ..engine import execute_bulk_remediation
        
        dry_run = execution_mode == 'dry_run'
        mock_run = execution_mode == 'mock_run'
        
        # Enqueue the background task
        django_rq.enqueue(
            execute_bulk_remediation, 
            device_ids, 
            connection_library=connection_library,
            dry_run=dry_run,
            mock_run=mock_run
        )
        
        return Response({
            "status": "Auto-Remediation Initiated",
            "devices_targeted": len(device_ids)
        })

class JobLogViewSet(NetBoxModelViewSet):
    queryset = models.JobLog.objects.prefetch_related('job', 'step', 'tags')
    serializer_class = serializers.JobLogSerializer


class SyncJobViewSet(NetBoxModelViewSet):
    queryset = models.SyncJob.objects.prefetch_related('device_records', 'tags')
    serializer_class = serializers.SyncJobSerializer


class DeviceSyncRecordViewSet(NetBoxModelViewSet):
    queryset = models.DeviceSyncRecord.objects.prefetch_related('device', 'sync_job', 'tags')
    serializer_class = serializers.DeviceSyncRecordSerializer

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Manually approve the diffs for this record."""
        record = self.get_object()
        if record.approve():
            return Response({"status": "Sync Record Applied to NetBox Device Successfully."})
        return Response({"error": "Failed to apply (Record may not be in pending status)"}, status=400)
