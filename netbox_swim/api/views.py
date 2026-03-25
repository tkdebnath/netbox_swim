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
        """API Endpoint: Pass {'device_ids': [1,2,3], 'scheduled_time': '2026-03-30T02:00:00Z'} to queue Upgrade Jobs"""
        device_ids = request.data.get('device_ids', [])
        connection_library = request.data.get('connection_library', 'scrapli')
        execution_mode = request.data.get('execution_mode', 'execute')
        scheduled_time_str = request.data.get('scheduled_time')
        
        if not device_ids:
            return Response({"error": "No device_ids provided"}, status=400)
        
        # Parse scheduled_time if provided
        scheduled_time = None
        if scheduled_time_str:
            try:
                import dateutil.parser
                scheduled_time = dateutil.parser.isoparse(scheduled_time_str)
            except (ValueError, TypeError):
                return Response({"error": "Invalid scheduled_time format. Use ISO-8601 (e.g., '2026-03-30T02:00:00Z')."}, status=400)
            
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
            mock_run=mock_run,
            scheduled_time=scheduled_time,
        )
        
        response_data = {
            "status": "Auto-Remediation Scheduled" if scheduled_time else "Auto-Remediation Initiated",
            "devices_targeted": len(device_ids),
        }
        if scheduled_time:
            response_data["scheduled_time"] = scheduled_time.isoformat()
        
        return Response(response_data)

    @action(detail=True, methods=['get'])
    def download_checks(self, request, pk=None):
        """
        Download the precheck/postcheck/diff ZIP archive for this upgrade job.
        File name: <devicename>_checks_<ddmmyy>.zip
            
        Returns the file as a streaming ZIP download via the API.
        Uses the same 3-tier strategy as the UI view:
        1. Cached archive from disk
        2. Regenerate from filesystem check files
        3. Fallback from database JobLog entries
        """
        import os
        import io
        import zipfile
        import json
        from django.http import HttpResponse, Http404
        from django.conf import settings
        from django.utils import timezone as tz
        
        job = self.get_object()
        base_media = getattr(settings, 'MEDIA_ROOT', '/opt/netbox/netbox/media')
        
        # --- Tier 1: Serve cached archive from disk ---
        archive_meta = job.extra_config.get('checks_archive', {})
        if archive_meta.get('filename'):
            archive_path = os.path.join(base_media, 'swim', 'checks', archive_meta['filename'])
            if os.path.exists(archive_path):
                with open(archive_path, 'rb') as f:
                    response = HttpResponse(f.read(), content_type='application/zip')
                    response['Content-Disposition'] = f'attachment; filename="{archive_meta["filename"]}"'
                    return response
        
        # --- Tier 2: Regenerate from filesystem ---
        from ..engine import _generate_checks_archive
        try:
            new_meta = _generate_checks_archive(job)
            if new_meta:
                job.extra_config['checks_archive'] = new_meta
                job.save()
                archive_path = os.path.join(base_media, 'swim', 'checks', new_meta['filename'])
                if os.path.exists(archive_path):
                    with open(archive_path, 'rb') as f:
                        response = HttpResponse(f.read(), content_type='application/zip')
                        response['Content-Disposition'] = f'attachment; filename="{new_meta["filename"]}"'
                        return response
        except Exception:
            pass
        
        # --- Tier 3: Build ZIP from database log entries ---
        device_name = job.device.name or f"device_{job.device.pk}"
        safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in device_name)
        date_str = (job.end_time or job.start_time or tz.now()).strftime('%d%m%y')
        filename = f"{safe_name}_checks_{date_str}.zip"
        
        logs = job.logs.all().order_by('timestamp')
        if not logs.exists():
            return Response({"error": "No check logs available for this job."}, status=404)
        
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for log in logs:
                safe_action = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in log.action_type)
                ts = log.timestamp.strftime('%H%M%S') if log.timestamp else '000000'
                entry_name = f"{safe_action}_{ts}.txt"
                
                header = f"Action: {log.action_type}\n"
                header += f"Step: {log.step or 'N/A'}\n"
                header += f"Result: {'SUCCESS' if log.is_success else 'FAILED'}\n"
                header += f"Timestamp: {log.timestamp}\n"
                header += f"{'=' * 60}\n\n"
                
                zf.writestr(entry_name, header + (log.log_output or 'No output captured.'))
            
            if job.job_log:
                zf.writestr('engine_timeline.json', json.dumps(job.job_log, indent=2, default=str))
        
        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=['get'])
    def download_fragment(self, request, pk=None):
        """
        Dynamically zip and download a specific folder layer (precheck, postcheck, diffs) via REST API.
        Takes `?fragment=precheck` as a query parameter.
        """
        import os
        import io
        import zipfile
        from django.http import HttpResponse
        from django.conf import settings
        from django.utils import timezone as tz

        fragment = request.query_params.get('fragment')
        if not fragment or fragment not in ['precheck', 'postcheck', 'diffs']:
            return Response({"error": "Query param '?fragment=' is missing or invalid. Use [precheck, postcheck, diffs]."}, status=400)

        job = self.get_object()
        base_media = getattr(settings, 'MEDIA_ROOT', '/opt/netbox/netbox/media')
        target_dir = os.path.join(base_media, 'swim', 'checks', str(job.id), fragment)

        if not os.path.exists(target_dir):
            return Response({"error": f"Folder '{fragment}' does not exist on disk for this job."}, status=404)

        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(target_dir):
                for f in files:
                    file_path = os.path.join(root, f)
                    arcname = os.path.relpath(file_path, target_dir)
                    zf.write(file_path, arcname)

        buffer.seek(0)
        device_name = getattr(job.device, 'name', f"device_{job.id}")
        filename = f"{device_name}_{fragment}_{tz.now().strftime('%d%m%y')}.zip"
        
        response = HttpResponse(buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

    @action(detail=True, methods=['get'])
    def download_logs(self, request, pk=None):
        """
        Return the Execution Log Timeline as a downloadable, formatted plain text file.
        """
        from django.http import HttpResponse
        from django.utils import timezone as tz

        job = self.get_object()
        logs = job.logs.all().order_by('order', 'timestamp')

        content = []
        content.append(f"EXECUTION LOGS FOR UPGRADE JOB: {job.id}")
        content.append(f"Device: {getattr(job.device, 'name', 'Unknown')}")
        content.append(f"Start Time: {job.start_time}")
        content.append(f"Status: {job.status.upper()}")
        content.append(f"{'='*50}\n")

        for log in logs:
            status_flag = "[SUCCESS]" if log.is_success else "[FAILED]" if log.is_success is False else "[INFO]"
            content.append(f"[{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {status_flag} STEP: {log.get_action_display()}")
            if log.log_output:
                content.append(f"{'-'*40}\n{log.log_output.strip()}\n{'-'*40}\n")
            else:
                content.append("")

        device_name = getattr(job.device, 'name', f"device_{job.id}")
        filename = f"{device_name}_execution_logs_{tz.now().strftime('%d%m%y')}.txt"
        
        response = HttpResponse('\n'.join(content), content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

class JobLogViewSet(NetBoxModelViewSet):
    queryset = models.JobLog.objects.select_related('job')
    serializer_class = serializers.JobLogSerializer
    filterset_class = filtersets.JobLogFilterSet


class SyncJobViewSet(NetBoxModelViewSet):
    queryset = models.SyncJob.objects.prefetch_related('device_records', 'tags')
    serializer_class = serializers.SyncJobSerializer


class DeviceSyncRecordViewSet(NetBoxModelViewSet):
    queryset = models.DeviceSyncRecord.objects.prefetch_related('device', 'sync_job', 'tags')
    serializer_class = serializers.DeviceSyncRecordSerializer
    filterset_class = filtersets.DeviceSyncRecordFilterSet

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Manually approve the diffs for this record."""
        record = self.get_object()
        if record.approve():
            return Response({"status": "Sync Record Applied to NetBox Device Successfully."})
        return Response({"error": "Failed to apply (Record may not be in pending status)"}, status=400)


# ============================================================
# pyATS Testbed Generation API
# ============================================================

from rest_framework.views import APIView

class TestbedGenerateAPIView(APIView):
    """
    Generate a pyATS testbed YAML from NetBox device inventory.
    
    GET /api/plugins/swim/testbed/generate/
    
    Query Parameters:
        site_id       - Filter devices by site (repeatable)
        platform_id   - Filter devices by platform (repeatable)
        role_id       - Filter devices by role (repeatable)
        device_id     - Specific device IDs (repeatable)
        profile       - Credential env var prefix (e.g., TACACS)
        format        - 'yaml' (default, file download) or 'json' (structured response)
    """
    def get(self, request):
        from django.http import HttpResponse
        from dcim.models import Device
        from ..testbed import generate_testbed_yaml, testbed_dict_to_yaml
        
        devices = Device.objects.filter(status='active')
        
        site_ids = request.GET.getlist('site_id')
        platform_ids = request.GET.getlist('platform_id')
        role_ids = request.GET.getlist('role_id')
        device_ids = request.GET.getlist('device_id')
        credential_profile = request.GET.get('profile', '').strip()
        output_format = request.GET.get('format', 'yaml')
        
        if site_ids:
            devices = devices.filter(site_id__in=site_ids)
        if platform_ids:
            devices = devices.filter(platform_id__in=platform_ids)
        if role_ids:
            devices = devices.filter(role_id__in=role_ids)
        if device_ids:
            devices = devices.filter(pk__in=device_ids)
        
        devices = devices.select_related(
            'primary_ip', 'platform', 'device_type__manufacturer', 'site', 'role'
        )
        
        testbed_dict = generate_testbed_yaml(
            devices,
            credential_profile=credential_profile if credential_profile else None,
        )
        
        if output_format == 'json':
            return Response({
                'device_count': len(testbed_dict.get('devices', {})),
                'testbed': testbed_dict,
            })
        
        # Default: YAML file download
        yaml_content = testbed_dict_to_yaml(testbed_dict)
        response = HttpResponse(yaml_content, content_type='text/yaml')
        response['Content-Disposition'] = 'attachment; filename="testbed.yaml"'
        return response

