from netbox.views import generic
from django.views.generic import View
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from dcim.models import Device
import django_rq
from . import forms, models, tables, filtersets

# ============================================================
# Dashboard
# ============================================================

class DashboardView(View):
    def get(self, request):
        return render(request, 'netbox_swim/dashboard.html', {
            'hardware_group_count': models.HardwareGroup.objects.count(),
            'software_images_count': models.SoftwareImage.objects.count(),
            'file_server_count': models.FileServer.objects.count(),
            'golden_image_count': models.GoldenImage.objects.count(),
            'compliant_count': models.DeviceCompliance.objects.filter(status='compliant').count(),
            'non_compliant_count': models.DeviceCompliance.objects.filter(status='non_compliant').count(),
            'upgrade_jobs_count': models.UpgradeJob.objects.count(),
            'sync_jobs_count': models.SyncJob.objects.count(),
        })

# ============================================================
# Device Sync Action
# ============================================================

class DeviceSyncExecuteView(View):
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

class BulkSyncFormView(View):
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

class BulkUpgradeFormView(View):
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
            
            dry_run = execution_mode == 'dry_run'
            mock_run = execution_mode == 'mock_run'
            
            if device_ids:
                django_rq.enqueue(
                    execute_bulk_remediation, 
                    device_ids, 
                    connection_library=connection_library,
                    dry_run=dry_run,
                    mock_run=mock_run
                )
            
            count = len(device_ids)
            messages.success(request, f"Successfully queued {count} devices for auto-remediation.")
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
    form = forms.SoftwareImageForm

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
