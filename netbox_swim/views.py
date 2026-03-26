from netbox.views import generic
from django.views.generic import View
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from dcim.models import Device
import django_rq
from . import forms, models, tables, filtersets

# ============================================================
# Dashboard
# ============================================================

class DashboardView(PermissionRequiredMixin, View):
    permission_required = 'netbox_swim.view_softwareimage'
    def get(self, request):
        return render(request, 'netbox_swim/dashboard.html', {
            'hardware_group_count': models.HardwareGroup.objects.count(),
            'software_images_count': models.SoftwareImage.objects.count(),
            'file_server_count': models.FileServer.objects.count(),
            'golden_image_count': models.GoldenImage.objects.count(),
            'compliant_count': models.DeviceCompliance.objects.filter(status='compliant').count(),
            'non_compliant_count': models.DeviceCompliance.objects.filter(status='non_compliant').count(),
            'upgrade_jobs_count': models.UpgradeJob.objects.count(),
            'job_log_count': models.JobLog.objects.count(),
            'sync_jobs_count': models.SyncJob.objects.count(),
            'workflow_template_count': models.WorkflowTemplate.objects.count(),
            'check_template_count': models.CheckTemplate.objects.count(),
            'validation_check_count': models.ValidationCheck.objects.count(),
            'device_sync_record_count': models.DeviceSyncRecord.objects.count(),
        })

# ============================================================
# Device Sync Action
# ============================================================

class DeviceSyncExecuteView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'netbox_swim.change_devicesyncrecord'
    def post(self, request, pk):
        device = get_object_or_404(Device, pk=pk)
        
        from .engine import _sync_device_logic
        from .models import SyncJob
        
        # Create a single-device SyncJob for tracking
        sync_job = SyncJob.objects.create(
            connection_library='scrapli', # Default
            max_concurrency=1,
            selected_device_count=1,
            summary_logs=[f"Starting single-device sync for {device.name}."]
        )
        
        django_rq.enqueue(
            _sync_device_logic, 
            device.pk, 
            sync_job_id=sync_job.id
        )
        
        messages.success(request, f"Device sync initiated for {device.name}. Tracking via Sync Job #{sync_job.pk}")
        
        return redirect(device.get_absolute_url())

class BulkSyncFormView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'netbox_swim.change_devicesyncrecord'
    def get(self, request):
        form = forms.BulkSyncForm()
        return render(request, 'netbox_swim/bulksync.html', {
            'form': form,
            'tab': 'bulk_sync',
        })

    def post(self, request):
        form = forms.BulkSyncForm(request.POST)
        if form.is_valid():
            # Apply filters
            devices = Device.objects.all()
            if form.cleaned_data.get('region'):
                devices = devices.filter(site__region__in=form.cleaned_data['region'])
            if form.cleaned_data.get('site'):
                devices = devices.filter(site__in=form.cleaned_data['site'])
            if form.cleaned_data.get('device_role'):
                devices = devices.filter(role__in=form.cleaned_data['device_role'])
            if form.cleaned_data.get('device'):
                devices = devices.filter(pk__in=form.cleaned_data['device'])
            
            if form.cleaned_data.get('has_primary_ip'):
                devices = devices.exclude(primary_ip4__isnull=True, primary_ip6__isnull=True)

            auto_update = form.cleaned_data.get('auto_update', False)

            if not devices.exists():
                messages.warning(request, "No devices matched your criteria.")
                return render(request, 'netbox_swim/bulksync.html', {'form': form})

            # Aggregate device IDs and enqueue the batched ThreadPoolEngine job
            from .engine import execute_bulk_sync_batch
            
            device_ids = [d.pk for d in devices]
            max_concurrency = form.cleaned_data.get('max_concurrency', 5)
            connection_library = form.cleaned_data.get('connection_library', 'scrapli')
            
            # Enqueue a single background job that handles concurrent connections internally
            if device_ids:
                django_rq.enqueue(
                    execute_bulk_sync_batch, 
                    device_ids, 
                    auto_update=auto_update, 
                    max_concurrency=max_concurrency,
                    connection_library=connection_library
                )
            
            count = len(device_ids)
            
            messages.success(request, f"Successfully queued {count} devices for synchronization.")
            return redirect('plugins:netbox_swim:hardwaregroup_list') # Redirect somewhere safe for now

        return render(request, 'netbox_swim/bulksync.html', {'form': form})

class BulkUpgradeFormView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'netbox_swim.add_upgradejob'
    def get(self, request):
        form = forms.BulkUpgradeForm()
        return render(request, 'netbox_swim/bulkupgrade.html', {
            'form': form,
            'tab': 'bulk_upgrade',
        })

    def post(self, request):
        form = forms.BulkUpgradeForm(request.POST)
        if form.is_valid():
            # Apply filters
            devices = Device.objects.all()
            if form.cleaned_data.get('region'):
                devices = devices.filter(site__region__in=form.cleaned_data['region'])
            if form.cleaned_data.get('site'):
                devices = devices.filter(site__in=form.cleaned_data['site'])
            if form.cleaned_data.get('device_role'):
                devices = devices.filter(role__in=form.cleaned_data['device_role'])
            if form.cleaned_data.get('device'):
                devices = devices.filter(pk__in=form.cleaned_data['device'])
            
            if form.cleaned_data.get('has_primary_ip'):
                devices = devices.exclude(primary_ip4__isnull=True, primary_ip6__isnull=True)

            if not devices.exists():
                messages.warning(request, "No devices matched your criteria.")
                return render(request, 'netbox_swim/bulkupgrade.html', {'form': form})

            from .engine import execute_bulk_remediation
            
            device_ids = [d.pk for d in devices]
            connection_library = form.cleaned_data.get('connection_library', 'scrapli')
            execution_mode = form.cleaned_data.get('execution_mode', 'execute')
            scheduled_time = form.cleaned_data.get('scheduled_time')
            
            dry_run = execution_mode == 'dry_run'
            mock_run = execution_mode == 'mock_run'
            
            if device_ids:
                django_rq.enqueue(
                    execute_bulk_remediation, 
                    device_ids, 
                    connection_library=connection_library,
                    dry_run=dry_run,
                    mock_run=mock_run,
                    scheduled_time=scheduled_time,
                )
            
            count = len(device_ids)
            if scheduled_time:
                formatted = scheduled_time.strftime('%b %d, %Y at %H:%M %Z')
                messages.success(request, f"Successfully scheduled {count} devices for auto-remediation at {formatted}.")
            else:
                messages.success(request, f"Successfully queued {count} devices for immediate auto-remediation.")
            return redirect('plugins:netbox_swim:upgradejob_list') 

        return render(request, 'netbox_swim/bulkupgrade.html', {'form': form})

# ============================================================
# PILLAR 0: Hardware Grouping (Grouping Criteria)
# ============================================================

class HardwareGroupListView(generic.ObjectListView):
    queryset = models.HardwareGroup.objects.all()
    table = tables.HardwareGroupTable
    filterset = filtersets.HardwareGroupFilterSet

class HardwareGroupView(generic.ObjectView):
    queryset = models.HardwareGroup.objects.all()
    template_name = 'netbox_swim/hardwaregroup.html'

class HardwareGroupEditView(generic.ObjectEditView):
    queryset = models.HardwareGroup.objects.all()
    form = forms.HardwareGroupForm

class HardwareGroupDeleteView(generic.ObjectDeleteView):
    queryset = models.HardwareGroup.objects.all()

class HardwareGroupBulkImportView(generic.BulkImportView):
    queryset = models.HardwareGroup.objects.all()
    model_form = forms.HardwareGroupCSVForm
    table = tables.HardwareGroupTable


# ============================================================
# PILLAR 1: Software Images
# ============================================================

class SoftwareImageListView(generic.ObjectListView):
    queryset = models.SoftwareImage.objects.all()
    table = tables.SoftwareImageTable
    filterset = filtersets.SoftwareImageFilterSet

class SoftwareImageView(generic.ObjectView):
    queryset = models.SoftwareImage.objects.all()

class SoftwareImageEditView(generic.ObjectEditView):
    queryset = models.SoftwareImage.objects.all()
    form = forms.SoftwareImageForm

class SoftwareImageDeleteView(generic.ObjectDeleteView):
    queryset = models.SoftwareImage.objects.all()

class SoftwareImageBulkImportView(generic.BulkImportView):
    queryset = models.SoftwareImage.objects.all()
    model_form = forms.SoftwareImageCSVForm
    table = tables.SoftwareImageTable


# ============================================================
# PILLAR 1b: File Servers
# ============================================================

class FileServerListView(generic.ObjectListView):
    queryset = models.FileServer.objects.all()
    table = tables.FileServerTable
    filterset = filtersets.FileServerFilterSet

class FileServerView(generic.ObjectView):
    queryset = models.FileServer.objects.all()
    template_name = 'netbox_swim/fileserver.html'

class FileServerEditView(generic.ObjectEditView):
    queryset = models.FileServer.objects.all()
    form = forms.FileServerForm

class FileServerDeleteView(generic.ObjectDeleteView):
    queryset = models.FileServer.objects.all()

class FileServerBulkImportView(generic.BulkImportView):
    queryset = models.FileServer.objects.all()
    model_form = forms.FileServerCSVForm
    table = tables.FileServerTable


# ============================================================
# PILLAR 2: Golden Image
# ============================================================

class GoldenImageListView(generic.ObjectListView):
    queryset = models.GoldenImage.objects.all()
    table = tables.GoldenImageTable
    filterset = filtersets.GoldenImageFilterSet

class GoldenImageView(generic.ObjectView):
    queryset = models.GoldenImage.objects.all()

class GoldenImageEditView(generic.ObjectEditView):
    queryset = models.GoldenImage.objects.all()
    form = forms.GoldenImageForm

class GoldenImageDeleteView(generic.ObjectDeleteView):
    queryset = models.GoldenImage.objects.all()

class GoldenImageBulkImportView(generic.BulkImportView):
    queryset = models.GoldenImage.objects.all()
    model_form = forms.GoldenImageCSVForm
    table = tables.GoldenImageTable


# ============================================================
# PILLAR 2b: Device Compliance
# ============================================================

class DeviceComplianceListView(generic.ObjectListView):
    queryset = models.DeviceCompliance.objects.all()
    table = tables.DeviceComplianceTable
    filterset = filtersets.DeviceComplianceFilterSet

class DeviceComplianceView(generic.ObjectView):
    queryset = models.DeviceCompliance.objects.all()


# --- Validation Check & Templates ---

class ValidationCheckListView(generic.ObjectListView):
    queryset = models.ValidationCheck.objects.all()
    table = tables.ValidationCheckTable

class ValidationCheckView(generic.ObjectView):
    queryset = models.ValidationCheck.objects.all()

class ValidationCheckEditView(generic.ObjectEditView):
    queryset = models.ValidationCheck.objects.all()
    form = forms.ValidationCheckForm

class ValidationCheckDeleteView(generic.ObjectDeleteView):
    queryset = models.ValidationCheck.objects.all()

class ValidationCheckBulkImportView(generic.BulkImportView):
    queryset = models.ValidationCheck.objects.all()
    model_form = forms.ValidationCheckCSVForm
    table = tables.ValidationCheckTable

class ValidationCheckBulkEditView(generic.BulkEditView):
    queryset = models.ValidationCheck.objects.all()
    # filterset = filtersets.ValidationCheckFilterSet
    table = tables.ValidationCheckTable
    form = forms.ValidationCheckForm

class ValidationCheckBulkDeleteView(generic.BulkDeleteView):
    queryset = models.ValidationCheck.objects.all()
    table = tables.ValidationCheckTable

class CheckTemplateListView(generic.ObjectListView):
    queryset = models.CheckTemplate.objects.all()
    table = tables.CheckTemplateTable

class CheckTemplateView(generic.ObjectView):
    queryset = models.CheckTemplate.objects.all()

class CheckTemplateEditView(generic.ObjectEditView):
    queryset = models.CheckTemplate.objects.all()
    form = forms.CheckTemplateForm

class CheckTemplateDeleteView(generic.ObjectDeleteView):
    queryset = models.CheckTemplate.objects.all()

class CheckTemplateBulkImportView(generic.BulkImportView):
    queryset = models.CheckTemplate.objects.all()
    model_form = forms.CheckTemplateCSVForm
    table = tables.CheckTemplateTable

class CheckTemplateBulkEditView(generic.BulkEditView):
    queryset = models.CheckTemplate.objects.all()
    # filterset = filtersets.CheckTemplateFilterSet
    table = tables.CheckTemplateTable
    form = forms.CheckTemplateForm 

class CheckTemplateBulkDeleteView(generic.BulkDeleteView):
    queryset = models.CheckTemplate.objects.all()
    table = tables.CheckTemplateTable


class DeviceComplianceEditView(generic.ObjectEditView):
    queryset = models.DeviceCompliance.objects.all()
    form = forms.DeviceComplianceForm

class DeviceComplianceDeleteView(generic.ObjectDeleteView):
    queryset = models.DeviceCompliance.objects.all()


# ============================================================
# PILLAR 3 & 4: Workflow Templates
# ============================================================

class WorkflowTemplateListView(generic.ObjectListView):
    queryset = models.WorkflowTemplate.objects.all()
    table = tables.WorkflowTemplateTable
    filterset = filtersets.WorkflowTemplateFilterSet

class WorkflowTemplateView(generic.ObjectView):
    queryset = models.WorkflowTemplate.objects.all()

class WorkflowTemplateEditView(generic.ObjectEditView):
    queryset = models.WorkflowTemplate.objects.all()
    form = forms.WorkflowTemplateForm

class WorkflowTemplateDeleteView(generic.ObjectDeleteView):
    queryset = models.WorkflowTemplate.objects.all()

class WorkflowTemplateBulkImportView(generic.BulkImportView):
    queryset = models.WorkflowTemplate.objects.all()
    model_form = forms.WorkflowTemplateCSVForm
    table = tables.WorkflowTemplateTable


# ============================================================
# PILLAR 3 & 4: Upgrade Jobs
# ============================================================

class UpgradeJobListView(generic.ObjectListView):
    queryset = models.UpgradeJob.objects.all()
    table = tables.UpgradeJobTable
    filterset = filtersets.UpgradeJobFilterSet

class UpgradeJobView(generic.ObjectView):
    queryset = models.UpgradeJob.objects.all()

    def get_extra_context(self, request, instance):
        """Build a full pipeline lineage / lifecycle context for the detail template."""
        context = {}
        device = instance.device
        target_image = instance.target_image
        template = instance.template

        # ----- 1. Hardware Group Matching -----
        matched_hg = None
        match_criteria = {}
        from .models import HardwareGroup
        for hg in HardwareGroup.objects.prefetch_related('platforms', 'device_types', 'tags'):
            if device in hg.get_matching_devices():
                matched_hg = hg
                # Determine WHY it matched
                if hg.platforms.exists() and device.platform in hg.platforms.all():
                    match_criteria['Platform'] = str(device.platform)
                if hg.device_types.exists() and device.device_type in hg.device_types.all():
                    match_criteria['Device Type'] = str(device.device_type)
                if hg.min_version or hg.max_version:
                    match_criteria['Version Range'] = f"{hg.min_version or '*'} → {hg.max_version or '*'}"
                if hg.deployment_mode:
                    match_criteria['Deployment Mode'] = hg.get_deployment_mode_display()
                if not match_criteria:
                    match_criteria['Catch-All'] = 'Matched by default (no specific criteria filtered it out)'
                break

        context['matched_hg'] = matched_hg
        context['match_criteria'] = match_criteria

        # ----- 2. Connection Module -----
        conn_priority = 'scrapli,netmiko,unicon'  # default
        if matched_hg:
            conn_priority = matched_hg.connection_priority or conn_priority
        job_override = None
        if instance.extra_config:
            job_override = instance.extra_config.get('connection_priority_override') or instance.extra_config.get('connection_priority')
        if job_override:
            conn_priority = job_override

        priority_list = [lib.strip() for lib in conn_priority.split(',')]
        context['connection_priority'] = priority_list
        context['connection_primary'] = priority_list[0] if priority_list else 'unknown'
        context['connection_override'] = job_override

        # ----- 3. Platform Detection -----
        platform_slug = getattr(device.platform, 'slug', None) or 'unknown'
        platform_name = str(device.platform) if device.platform else 'Unknown'
        # Map platform to parser engines
        parser_engines = []
        if 'cisco' in platform_slug.lower() or 'ios' in platform_slug.lower():
            parser_engines = ['Genie (pyATS)', 'TextFSM (NTC Templates)']
        elif 'paloalto' in platform_slug.lower() or 'panos' in platform_slug.lower():
            parser_engines = ['XML API (PAN-OS)']
        elif 'juniper' in platform_slug.lower() or 'junos' in platform_slug.lower():
            parser_engines = ['PyEZ', 'TextFSM']
        else:
            parser_engines = ['TextFSM (Generic)']

        context['platform_slug'] = platform_slug
        context['platform_name'] = platform_name
        context['parser_engines'] = parser_engines

        # ----- 4. Config Context -----
        ctx = device.get_config_context() or {}
        swim_ctx = ctx.get('swim', {})
        context['config_context'] = swim_ctx
        context['has_config_context'] = bool(swim_ctx)

        # ----- 5. File Server -----
        context['file_server'] = None
        context['download_url'] = None
        if target_image and getattr(target_image, 'file_server', None):
            fs = target_image.file_server
            context['file_server'] = fs
            context['download_url'] = f"{fs.protocol}://{fs.ip_address}/{fs.base_path}/{target_image.image_file_name}"

        # ----- 6. Golden Image -----
        golden = None
        if matched_hg:
            gi_qs = matched_hg.golden_images.all()
            if gi_qs.exists():
                golden = gi_qs.first()
        context['golden_image'] = golden

        # ----- 7. Workflow Steps Sequence -----
        steps_detail = []
        if template:
            for step in template.steps.all().order_by('order'):
                # Per-step connection override
                step_conn = conn_priority
                step_override = step.extra_config.get('connection_priority_override') if step.extra_config else None
                if step_override:
                    step_conn = step_override
                step_priority_list = [lib.strip() for lib in step_conn.split(',')]
                primary_lib = step_priority_list[0] if step_priority_list else 'unknown'

                # Map to predicted class
                action = step.action_type
                class_map = {
                    'readiness': f'Readiness{platform_name.replace(" ", "")}{primary_lib.capitalize()}',
                    'distribution': f'Cisco Distribute{primary_lib.capitalize()}',
                    'activation': f'Cisco Activate{primary_lib.capitalize()}',
                    'precheck': f'Cisco Checks{primary_lib.capitalize()}',
                    'postcheck': f'Cisco Checks{primary_lib.capitalize()}',
                }
                predicted_class = class_map.get(action, f'{action.capitalize()}Handler')

                steps_detail.append({
                    'order': step.order,
                    'name': step.get_action_type_display(),
                    'action_type': action,
                    'primary_lib': primary_lib,
                    'fallback_libs': step_priority_list[1:] if len(step_priority_list) > 1 else [],
                    'predicted_class': predicted_class,
                    'has_override': bool(step_override),
                    'check_template': getattr(step, 'check_template', None),
                })

        context['workflow_steps'] = steps_detail

        # ----- 8. Execution Mode -----
        context['dry_run'] = instance.extra_config.get('dry_run', False) if instance.extra_config else False
        context['mock_run'] = instance.extra_config.get('mock_run', False) if instance.extra_config else False

        # ----- 9. pyATS Testbed (single device) -----
        try:
            from .testbed import generate_testbed_yaml, testbed_dict_to_yaml
            testbed_dict = generate_testbed_yaml([device])
            context['testbed_yaml'] = testbed_dict_to_yaml(testbed_dict)
            context['testbed_device_count'] = len(testbed_dict.get('devices', {}))
        except Exception as e:
            context['testbed_yaml'] = None
            context['testbed_error'] = str(e)

        return context

class UpgradeJobEditView(generic.ObjectEditView):
    queryset = models.UpgradeJob.objects.all()
    form = forms.UpgradeJobForm

class UpgradeJobDeleteView(generic.ObjectDeleteView):
    queryset = models.UpgradeJob.objects.all()

class WorkflowStepEditView(generic.ObjectEditView):
    queryset = models.WorkflowStep.objects.all()
    form = forms.WorkflowStepForm

class WorkflowStepDeleteView(generic.ObjectDeleteView):
    queryset = models.WorkflowStep.objects.all()


# ============================================================
# Job Logs (per-step execution logs)
# ============================================================

class JobLogListView(generic.ObjectListView):
    queryset = models.JobLog.objects.select_related('job').order_by('-timestamp')
    table = tables.JobLogTable
    filterset = filtersets.JobLogFilterSet

class JobLogView(generic.ObjectView):
    queryset = models.JobLog.objects.select_related('job')
    template_name = 'netbox_swim/joblog.html'


class UpgradeJobDownloadFragmentView(generic.ObjectView):
    """
    Zips and downloads a specific folder (precheck, postcheck, diffs) for a job in-memory.
    """
    queryset = models.UpgradeJob.objects.all()

    def get(self, request, pk, fragment):
        import os
        import io
        import zipfile
        from django.http import HttpResponse, Http404
        from django.conf import settings
        from django.utils import timezone as tz

        job = self.get_object()
        base_media = getattr(settings, 'MEDIA_ROOT', '/opt/netbox/netbox/media')
        target_dir = os.path.join(base_media, 'swim', 'checks', str(job.id), fragment)

        if not os.path.exists(target_dir):
            raise Http404(f"Folder '{fragment}' does not exist for this job.")

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


class UpgradeJobDownloadLogsView(generic.ObjectView):
    """
    Downloads the execution timeline (JobLogs) as a formatted plain text file.
    """
    queryset = models.UpgradeJob.objects.all()

    def get(self, request, pk):
        from django.http import HttpResponse
        from django.utils import timezone as tz

        job = self.get_object()
        logs = models.JobLog.objects.filter(job=job).order_by('timestamp')

        content = []
        content.append(f"EXECUTION LOGS FOR UPGRADE JOB: {job.id}")
        content.append(f"Device: {getattr(job.device, 'name', 'Unknown')}")
        content.append(f"Start Time: {job.start_time}")
        content.append(f"Status: {job.status.upper()}")
        content.append(f"{'='*50}\n")

        for log in logs:
            status_flag = "[SUCCESS]" if log.is_success else "[FAILED]" if log.is_success is False else "[INFO]"
            content.append(f"[{log.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {status_flag} STEP: {log.action_type}")
            if log.log_output:
                content.append(f"{'-'*40}\n{log.log_output.strip()}\n{'-'*40}\n")
            else:
                content.append("")

        device_name = getattr(job.device, 'name', f"device_{job.id}")
        filename = f"{device_name}_execution_logs_{tz.now().strftime('%d%m%y')}.txt"
        
        response = HttpResponse('\n'.join(content), content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class UpgradeJobDownloadChecksView(generic.ObjectView):
    """
    Serves the precheck/postcheck/diff ZIP archive for an UpgradeJob.
    Generates the archive on-the-fly if it doesn't exist yet.
    File name: <devicename>_checks_<ddmmyy>.zip
    """
    queryset = models.UpgradeJob.objects.all()

    def get(self, request, pk):
        import os
        import io
        import zipfile
        from django.http import HttpResponse, Http404
        from django.conf import settings
        from django.utils import timezone as tz

        job = self.get_object()

        # Check for existing archive in extra_config
        archive_meta = job.extra_config.get('checks_archive', {})
        base_media = getattr(settings, 'MEDIA_ROOT', '/opt/netbox/netbox/media')

        # If archive already exists on disk, serve it directly
        if archive_meta.get('filename'):
            archive_path = os.path.join(base_media, 'swim', 'checks', archive_meta['filename'])
            if os.path.exists(archive_path):
                with open(archive_path, 'rb') as f:
                    response = HttpResponse(f.read(), content_type='application/zip')
                    response['Content-Disposition'] = f'attachment; filename="{archive_meta["filename"]}"'
                    return response

        # Try to regenerate from filesystem
        from .engine import _generate_checks_archive
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

        # Fallback: build a ZIP from database log_output if no filesystem files
        device_name = job.device.name or f"device_{job.device.pk}"
        safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in device_name)
        date_str = (job.end_time or job.start_time or tz.now()).strftime('%d%m%y')
        filename = f"{safe_name}_checks_{date_str}.zip"

        logs = job.logs.all().order_by('timestamp')
        if not logs.exists():
            raise Http404("No check logs available for this job.")

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

            # Include the job_log JSON timeline
            if job.job_log:
                import json
                zf.writestr('engine_timeline.json', json.dumps(job.job_log, indent=2, default=str))

        buffer.seek(0)
        response = HttpResponse(buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


class UpgradeJobTestbedDownloadView(generic.ObjectView):
    """
    Generates and serves a pyATS testbed YAML for a specific UpgradeJob's device.
    The testbed contains only the single device associated with this job.
    """
    queryset = models.UpgradeJob.objects.all()

    def get(self, request, pk):
        from django.http import HttpResponse
        from .testbed import generate_testbed_yaml, testbed_dict_to_yaml

        job = self.get_object()
        device = job.device

        testbed_dict = generate_testbed_yaml([device])
        yaml_content = testbed_dict_to_yaml(testbed_dict)

        device_name = device.name or f"device_{device.pk}"
        safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in device_name)
        filename = f"{safe_name}_testbed.yaml"

        response = HttpResponse(yaml_content, content_type='text/yaml')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response

class UpgradeJobExecuteView(generic.ObjectView):
    queryset = models.UpgradeJob.objects.all()

    def post(self, request, pk):
        from django_rq import get_queue
        from .engine import execute_upgrade_job

        upgrade_job = get_object_or_404(self.queryset, pk=pk)
        
        if upgrade_job.status in ['running']:
            messages.warning(request, f"Upgrade Job {upgrade_job.pk} is already running.")
            return redirect(upgrade_job.get_absolute_url())

        queue = get_queue('default')
        queue.enqueue(execute_upgrade_job, upgrade_job.id)
        
        upgrade_job.status = 'scheduled'
        upgrade_job.save()

        messages.success(request, f"Workflow Template {upgrade_job.template.name if upgrade_job.template else 'Unknown'} queued for Upgrade Job {upgrade_job.pk}.")
        return redirect(upgrade_job.get_absolute_url())



# ============================================================
# PILLAR: Sync Record Consolidation
# ============================================================

class DeviceSyncRecordListView(generic.ObjectListView):
    queryset = models.DeviceSyncRecord.objects.all()
    table = tables.DeviceSyncRecordTable
    filterset = filtersets.DeviceSyncRecordFilterSet
    action_buttons = ('delete',)

class DeviceSyncRecordBulkDeleteView(generic.BulkDeleteView):
    queryset = models.DeviceSyncRecord.objects.all()
    filterset = filtersets.DeviceSyncRecordFilterSet
    table = tables.DeviceSyncRecordTable

class SyncJobDeleteView(generic.ObjectDeleteView):
    queryset = models.SyncJob.objects.all()

class SyncJobBulkDeleteView(generic.BulkDeleteView):
    queryset = models.SyncJob.objects.all()
    filterset = filtersets.SyncJobFilterSet
    table = tables.SyncJobTable

class SyncJobCancelView(generic.ObjectEditView):
    queryset = models.SyncJob.objects.all()
    
    def get(self, request, *args, **kwargs):
        obj = self.get_object(kwargs)
        if obj.status in ['pending', 'running']:
            obj.status = 'cancelled'
            from django.utils import timezone
            obj.end_time = timezone.now()
            obj.summary_logs.append("Job cancelled by user.")
            obj.save()
        from django.shortcuts import redirect
        return redirect('plugins:netbox_swim:syncjob', pk=obj.pk)

    def post(self, request, *args, **kwargs):
        return self.get(request, *args, **kwargs)

class DeviceSyncRecordView(generic.ObjectView):
    queryset = models.DeviceSyncRecord.objects.all()

class DeviceSyncRecordApproveView(generic.ObjectView):
    queryset = models.DeviceSyncRecord.objects.all()

    def post(self, request, pk):
        instance = get_object_or_404(self.queryset, pk=pk)
        if instance.approve():
            messages.success(request, f"Applied changes for {instance.device}")
        else:
            messages.error(request, "Failed to apply changes.")
        return redirect(instance.get_absolute_url())

class DeviceSyncRecordBulkApproveView(generic.ObjectView): # Changed from View to generic.ObjectView
    queryset = models.DeviceSyncRecord.objects.all() # Added queryset for generic.ObjectView
    def post(self, request):
        from django.shortcuts import redirect
        from django.contrib import messages
        pks = request.POST.getlist('pk')
        if not pks:
            messages.warning(request, "No records selected.")
            return redirect(request.META.get('HTTP_REFERER', 'plugins:netbox_swim:syncjob_list'))
        
        success, failed = 0, 0
        records = models.DeviceSyncRecord.objects.filter(pk__in=pks)
        for r in records:
            if r.approve():
                success += 1
            else:
                failed += 1
        
        if success:
            messages.success(request, f"Successfully approved {success} records.")
        if failed:
            messages.error(request, f"Failed to approve {failed} records.")
        return redirect(request.META.get('HTTP_REFERER', 'plugins:netbox_swim:syncjob_list'))

class SyncJobListView(generic.ObjectListView):
    queryset = models.SyncJob.objects.all()
    filterset = filtersets.SyncJobFilterSet
    table = tables.SyncJobTable
    action_buttons = ('delete',)

class SyncJobView(generic.ObjectView):
    queryset = models.SyncJob.objects.all()
    template_name = 'netbox_swim/syncjob.html'
    
    def get_extra_context(self, request, instance):
        return {
            'action_buttons': ('delete',)
        }

class DeviceSyncRecordDeleteView(generic.ObjectDeleteView):
    queryset = models.DeviceSyncRecord.objects.all()


# ============================================================
# Compliance Dashboard (computed on-the-fly)
# ============================================================

class ComplianceDashboardView(PermissionRequiredMixin, View):
    permission_required = 'netbox_swim.view_devicecompliance'
    """
    Iterates over all active devices, resolves each device's Hardware Group
    and Golden Image baseline, compares the synced software_version against
    the golden version, and renders a table with severity classifications.
    Supports checkbox selection and POST to dispatch bulk upgrades.
    """

    def _build_rows(self, device_queryset=None):
        """Build the flat dict rows used by both GET and POST."""
        from .compliance import compute_version_gap, classify_severity

        if device_queryset is None:
            device_queryset = Device.objects.filter(status='active')

        devices = device_queryset.select_related(
            'site', 'platform', 'device_type'
        ).order_by('name')

        # Pre-load hardware groups and build device → group map
        all_hw_groups = models.HardwareGroup.objects.prefetch_related(
            'platforms', 'device_types', 'manual_includes', 'manual_excludes',
            'golden_images__image'
        )
        device_hw_map = {}
        for hg in all_hw_groups:
            for dev in hg.get_matching_devices():
                if dev.pk not in device_hw_map:
                    device_hw_map[dev.pk] = hg

        # Pre-load Golden Images
        golden_by_dtype = {}
        golden_by_hwgroup = {}
        for gi in models.GoldenImage.objects.prefetch_related('device_types', 'hardware_groups').select_related('image'):
            for dt in gi.device_types.all():
                golden_by_dtype[(dt.pk, gi.deployment_mode)] = gi
            for hg in gi.hardware_groups.all():
                golden_by_hwgroup[(hg.pk, gi.deployment_mode)] = gi

        rows = []
        for device in devices:
            hw_group = device_hw_map.get(device.pk)
            current_version = (device.custom_field_data or {}).get('software_version', '')
            deployment_mode = (device.custom_field_data or {}).get('deployment_mode', 'universal')

            # Resolve golden image
            golden_image = None
            if device.device_type_id:
                golden_image = golden_by_dtype.get((device.device_type_id, deployment_mode))
            if not golden_image and hw_group:
                golden_image = golden_by_hwgroup.get((hw_group.pk, deployment_mode))
            if not golden_image and device.device_type_id:
                golden_image = golden_by_dtype.get((device.device_type_id, 'universal'))
            if not golden_image and hw_group:
                golden_image = golden_by_hwgroup.get((hw_group.pk, 'universal'))

            golden_version = golden_image.image.version if golden_image else ''

            gap = compute_version_gap(current_version, golden_version)
            severity, severity_css = classify_severity(gap)

            if gap is None:
                gap_display = '—'
            elif gap == 0:
                gap_display = 'Up to date'
            elif gap > 0:
                gap_display = f'{gap} behind'
            else:
                gap_display = f'{abs(gap)} ahead'

            # Flat dict for django-tables2 (no model instances as values)
            rows.append({
                'device_pk': device.pk,
                'device_name': device.name,
                'device_url': device.get_absolute_url(),
                'site_name': str(device.site) if device.site else '—',
                'site_pk': device.site.pk if device.site else None,
                'platform_name': str(device.platform) if device.platform else '—',
                'device_type_name': str(device.device_type),
                'hw_group_name': hw_group.name if hw_group else '',
                'hw_group_url': hw_group.get_absolute_url() if hw_group else '',
                'hw_group_pk': hw_group.pk if hw_group else None,
                'current_version': current_version,
                'golden_version': golden_version,
                'gap': gap if gap is not None else 999999,
                'gap_display': gap_display,
                'severity': severity,
                'severity_css': severity_css,
            })

        return rows, all_hw_groups

    def get(self, request):
        from .compliance import capture_compliance_snapshot
        import json

        # Apply the filterset to the Device queryset (site, region, platform, etc.)
        base_qs = Device.objects.filter(status='active')
        filterset = filtersets.ComplianceDashboardFilterSet(request.GET, queryset=base_qs)
        filtered_qs = filterset.qs

        rows, all_hw_groups = self._build_rows(filtered_qs)

        # Count devices in any hardware group (rows that have hw_group_pk)
        grouped_rows = [r for r in rows if r['hw_group_pk']]
        total_grouped = len(grouped_rows)

        # Apply virtual filters (severity, hardware_group) that operate on computed rows
        filter_severity = request.GET.get('severity', '')
        filter_hw_group = request.GET.get('hardware_group', '')

        if filter_severity:
            rows = [r for r in rows if r['severity'] == filter_severity]
        if filter_hw_group:
            rows = [r for r in rows if r['hw_group_pk'] and str(r['hw_group_pk']) == filter_hw_group]

        # Sort: Critical first, Compliant last
        severity_order = {'Critical': 0, 'High': 1, 'Medium': 2, 'Low': 3, 'Unknown': 4, 'Ahead': 5, 'Compliant': 6}
        rows.sort(key=lambda r: severity_order.get(r['severity'], 99))

        # Summary (post-filter)
        summary = {
            'compliant': sum(1 for r in rows if r['severity'] == 'Compliant'),
            'ahead': sum(1 for r in rows if r['severity'] == 'Ahead'),
            'low': sum(1 for r in rows if r['severity'] == 'Low'),
            'medium': sum(1 for r in rows if r['severity'] == 'Medium'),
            'high': sum(1 for r in rows if r['severity'] == 'High'),
            'critical': sum(1 for r in rows if r['severity'] == 'Critical'),
        }

        # Compliance percentage (across all grouped devices, pre-virtual-filter)
        compliant_total = sum(1 for r in grouped_rows if r['severity'] in ('Compliant', 'Ahead'))
        non_compliant_total = total_grouped - compliant_total
        compliance_pct = round((compliant_total / total_grouped * 100), 1) if total_grouped > 0 else 0

        # Capture today's snapshot (idempotent)
        try:
            capture_compliance_snapshot()
        except Exception:
            pass

        # Load ALL snapshot data (up to 1 year) — JS will handle range switching
        from datetime import date, timedelta
        cutoff = date.today() - timedelta(days=365)
        snapshots = list(
            models.ComplianceSnapshot.objects.filter(date__gte=cutoff).order_by('date')
        )
        # Pass ISO dates so JS can parse and filter by range
        chart_dates = json.dumps([s.date.isoformat() for s in snapshots])
        chart_labels = json.dumps([s.date.strftime('%b %d') for s in snapshots])
        chart_compliant = json.dumps([s.compliant + s.ahead for s in snapshots])
        chart_non_compliant = json.dumps([s.non_compliant for s in snapshots])
        chart_total = json.dumps([s.total_devices for s in snapshots])

        # Build the django-tables2 table with pagination
        from django_tables2 import RequestConfig
        table = tables.ComplianceDashboardTable(rows)
        RequestConfig(request, paginate={'per_page': 50}).configure(table)

        return render(request, 'netbox_swim/compliance_dashboard.html', {
            'table': table,
            'filter_form': filterset.form,
            'summary': summary,
            'total_grouped': total_grouped,
            'compliant_total': compliant_total,
            'non_compliant_total': non_compliant_total,
            'compliance_pct': compliance_pct,
            'chart_dates': chart_dates,
            'chart_labels': chart_labels,
            'chart_compliant': chart_compliant,
            'chart_non_compliant': chart_non_compliant,
            'chart_total': chart_total,
        })



    def post(self, request):
        """Handle bulk upgrade action from selected checkboxes."""
        selected_pks = request.POST.getlist('pk')
        if not selected_pks:
            messages.warning(request, 'No devices were selected.')
            return redirect('plugins:netbox_swim:compliance_dashboard')

        action = request.POST.get('action', 'upgrade')
        connection_library = request.POST.get('connection_library', 'scrapli')
        execution_mode = request.POST.get('execution_mode', 'execute')

        device_ids = [int(pk) for pk in selected_pks]

        if action == 'upgrade':
            from .engine import execute_bulk_remediation
            dry_run = execution_mode == 'dry_run'
            mock_run = execution_mode == 'mock_run'
            django_rq.enqueue(
                execute_bulk_remediation,
                device_ids,
                connection_library=connection_library,
                dry_run=dry_run,
                mock_run=mock_run,
            )
            messages.success(request, f'Queued {len(device_ids)} device(s) for bulk upgrade ({execution_mode}).')
            return redirect('plugins:netbox_swim:upgradejob_list')

        elif action == 'sync':
            from .engine import execute_bulk_sync_batch
            django_rq.enqueue(
                execute_bulk_sync_batch,
                device_ids,
                auto_update=False,
                max_concurrency=5,
                connection_library=connection_library,
            )
            messages.success(request, f'Queued {len(device_ids)} device(s) for sync.')
            return redirect('plugins:netbox_swim:syncjob_list')

        messages.warning(request, 'Unknown action.')
        return redirect('plugins:netbox_swim:compliance_dashboard')


# ============================================================
# pyATS Testbed Generator
# ============================================================

class TestbedGeneratorView(PermissionRequiredMixin, View):
    permission_required = 'netbox_swim.view_upgradejob'
    """
    UI view for generating pyATS testbed YAML from NetBox devices.
    Supports filtering by site, platform, role, and individual devices.
    Provides both preview and download capabilities.
    """
    def get(self, request):
        from dcim.models import Site, Platform, DeviceRole
        
        # Get filter options for the form
        sites = Site.objects.all().order_by('name')
        platforms = Platform.objects.all().order_by('name')
        roles = DeviceRole.objects.all().order_by('name')
        
        context = {
            'sites': sites,
            'platforms': platforms,
            'roles': roles,
            'testbed_yaml': None,
            'device_count': 0,
            'skipped_count': 0,
        }
        return render(request, 'netbox_swim/testbed_generator.html', context)

    def post(self, request):
        from dcim.models import Site, Platform, DeviceRole
        from .testbed import generate_testbed_yaml, testbed_dict_to_yaml
        from django.http import HttpResponse
        
        # Get filter options for re-rendering form
        sites = Site.objects.all().order_by('name')
        platforms = Platform.objects.all().order_by('name')
        roles = DeviceRole.objects.all().order_by('name')
        
        # Build the device queryset from filters
        devices = Device.objects.filter(status='active')
        
        site_ids = request.POST.getlist('site_id')
        platform_ids = request.POST.getlist('platform_id')
        role_ids = request.POST.getlist('role_id')
        device_ids = request.POST.getlist('device_id')
        credential_profile = request.POST.get('credential_profile', '').strip()
        
        if site_ids:
            devices = devices.filter(site_id__in=site_ids)
        if platform_ids:
            devices = devices.filter(platform_id__in=platform_ids)
        if role_ids:
            devices = devices.filter(role_id__in=role_ids)
        if device_ids:
            devices = devices.filter(pk__in=device_ids)
        
        devices = devices.select_related('primary_ip', 'platform', 'device_type__manufacturer', 'site', 'role')
        
        # Generate testbed
        total_count = devices.count()
        testbed_dict = generate_testbed_yaml(
            devices,
            credential_profile=credential_profile if credential_profile else None,
        )
        device_count = len(testbed_dict.get('devices', {}))
        skipped_count = total_count - device_count
        
        yaml_content = testbed_dict_to_yaml(testbed_dict)
        
        # If download was requested, serve as file
        action = request.POST.get('action', 'preview')
        if action == 'download':
            response = HttpResponse(yaml_content, content_type='text/yaml')
            response['Content-Disposition'] = 'attachment; filename="testbed.yaml"'
            return response
        
        # Otherwise, render preview
        context = {
            'sites': sites,
            'platforms': platforms,
            'roles': roles,
            'testbed_yaml': yaml_content,
            'device_count': device_count,
            'skipped_count': skipped_count,
            'selected_sites': [int(s) for s in site_ids] if site_ids else [],
            'selected_platforms': [int(p) for p in platform_ids] if platform_ids else [],
            'selected_roles': [int(r) for r in role_ids] if role_ids else [],
            'credential_profile': credential_profile,
        }
        return render(request, 'netbox_swim/testbed_generator.html', context)


class TestbedDownloadView(View):
    """
    Direct download endpoint — generates testbed for ALL active devices.
    Supports query params: ?site_id=1&platform_id=2&role_id=3&profile=TACACS
    """
    def get(self, request):
        from .testbed import generate_testbed_yaml, testbed_dict_to_yaml
        from django.http import HttpResponse
        
        devices = Device.objects.filter(status='active')
        
        site_id = request.GET.get('site_id')
        platform_id = request.GET.get('platform_id')
        role_id = request.GET.get('role_id')
        device_ids = request.GET.getlist('device_id')
        credential_profile = request.GET.get('profile', '').strip()
        
        if site_id:
            devices = devices.filter(site_id=site_id)
        if platform_id:
            devices = devices.filter(platform_id=platform_id)
        if role_id:
            devices = devices.filter(role_id=role_id)
        if device_ids:
            devices = devices.filter(pk__in=device_ids)
        
        devices = devices.select_related('primary_ip', 'platform', 'device_type__manufacturer', 'site', 'role')
        
        testbed_dict = generate_testbed_yaml(
            devices,
            credential_profile=credential_profile if credential_profile else None,
        )
        yaml_content = testbed_dict_to_yaml(testbed_dict)
        
        response = HttpResponse(yaml_content, content_type='text/yaml')
        response['Content-Disposition'] = 'attachment; filename="testbed.yaml"'
        return response


# ============================================================
# Golden Image Assignment Matrix
# ============================================================

class GoldenImageAssignmentView(PermissionRequiredMixin, View):
    permission_required = 'netbox_swim.view_goldenimage'
    """
    Lists all DeviceTypes with their current golden image assignment.
    Supports bulk assignment: select device types → pick a golden image → assign.
    """

    def get(self, request):
        from dcim.models import DeviceType
        from django_tables2 import RequestConfig

        # Build golden image lookups: device_type_pk → display string / url / version
        golden_map = {}       # pk → image name
        golden_map_urls = {}  # pk → golden image url
        golden_versions = {}  # pk → version string
        for gi in models.GoldenImage.objects.prefetch_related('device_types').select_related('image'):
            for dt in gi.device_types.all():
                golden_map[dt.pk] = str(gi.image)
                golden_map_urls[dt.pk] = gi.get_absolute_url()
                golden_versions[dt.pk] = gi.image.version

        # Build hardware group lookup: device_type_pk → [(name, url), ...]
        hw_group_map = {}  # dt_pk → list of (name, url)
        for hg in models.HardwareGroup.objects.prefetch_related('device_types'):
            for dt in hg.device_types.all():
                hw_group_map.setdefault(dt.pk, []).append((hg.name, hg.get_absolute_url()))

        # Use DeviceType queryset directly
        device_types = DeviceType.objects.select_related('manufacturer').order_by('manufacturer__name', 'model')

        table = tables.GoldenImageAssignmentTable(
            device_types,
            golden_map=golden_map,
            golden_map_urls=golden_map_urls,
            golden_versions=golden_versions,
            hw_group_map=hw_group_map,
        )
        RequestConfig(request, paginate={'per_page': 50}).configure(table)

        # Dropdowns for the bulk-assign bar
        golden_images = models.GoldenImage.objects.select_related('image').all()
        hardware_groups = models.HardwareGroup.objects.order_by('name')

        total = device_types.count()
        assigned = len(golden_map)

        return render(request, 'netbox_swim/golden_image_assignment.html', {
            'table': table,
            'golden_images': golden_images,
            'hardware_groups': hardware_groups,
            'total_device_types': total,
            'assigned_count': assigned,
            'unassigned_count': total - assigned,
        })

    def post(self, request):
        from dcim.models import DeviceType

        selected_pks = request.POST.getlist('pk')
        action = request.POST.get('action', 'assign_gi')

        if not selected_pks:
            messages.warning(request, "No device types selected.")
            return redirect('plugins:netbox_swim:goldenimage_assignment')

        device_types = DeviceType.objects.filter(pk__in=selected_pks)
        count = len(selected_pks)

        # --- Golden Image actions ---
        if action == 'assign_gi':
            golden_image_pk = request.POST.get('golden_image')
            if not golden_image_pk:
                messages.warning(request, "Please select a golden image to assign.")
                return redirect('plugins:netbox_swim:goldenimage_assignment')
            try:
                gi = models.GoldenImage.objects.get(pk=golden_image_pk)
            except models.GoldenImage.DoesNotExist:
                messages.error(request, "Selected golden image not found.")
                return redirect('plugins:netbox_swim:goldenimage_assignment')
            # Remove from other golden images first
            for other_gi in models.GoldenImage.objects.exclude(pk=gi.pk).prefetch_related('device_types'):
                other_gi.device_types.remove(*device_types)
            gi.device_types.add(*device_types)
            messages.success(request, f"Assigned {count} device type(s) to golden image: {gi}")

        elif action == 'unassign_gi':
            for gi in models.GoldenImage.objects.prefetch_related('device_types'):
                gi.device_types.remove(*device_types)
            messages.success(request, f"Removed golden image from {count} device type(s).")

        # --- Hardware Group actions ---
        elif action == 'assign_hwgroup':
            hw_group_pk = request.POST.get('hardware_group')
            if not hw_group_pk:
                messages.warning(request, "Please select a hardware group to assign.")
                return redirect('plugins:netbox_swim:goldenimage_assignment')
            try:
                hg = models.HardwareGroup.objects.get(pk=hw_group_pk)
            except models.HardwareGroup.DoesNotExist:
                messages.error(request, "Selected hardware group not found.")
                return redirect('plugins:netbox_swim:goldenimage_assignment')
            hg.device_types.add(*device_types)
            messages.success(request, f"Added {count} device type(s) to hardware group: {hg.name}")

        elif action == 'unassign_hwgroup':
            for hg in models.HardwareGroup.objects.prefetch_related('device_types'):
                hg.device_types.remove(*device_types)
            messages.success(request, f"Removed {count} device type(s) from all hardware groups.")

        return redirect('plugins:netbox_swim:goldenimage_assignment')
