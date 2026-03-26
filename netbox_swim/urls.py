from django.urls import path
from netbox.views.generic import ObjectChangeLogView
from . import models, views

urlpatterns = (
    # ---------------------------------------------------------
    # Dashboard
    # ---------------------------------------------------------
    path('', views.DashboardView.as_view(), name='dashboard'),

    # ---------------------------------------------------------
    # Actions & Bulk Sync
    # ---------------------------------------------------------
    path('device/<int:pk>/sync/', views.DeviceSyncExecuteView.as_view(), name='device_sync'),
    path('bulk-sync/', views.BulkSyncFormView.as_view(), name='device_bulk_sync'),
    path('bulk-upgrade/', views.BulkUpgradeFormView.as_view(), name='device_bulk_upgrade'),

    # ---------------------------------------------------------
    # Pillar 0: Hardware Groups
    # ---------------------------------------------------------
    path('hardware-groups/', views.HardwareGroupListView.as_view(), name='hardwaregroup_list'),
    path('hardware-groups/add/', views.HardwareGroupEditView.as_view(), name='hardwaregroup_add'),
    path('hardware-groups/import/', views.HardwareGroupBulkImportView.as_view(), name='hardwaregroup_import'),
    path('hardware-groups/<int:pk>/', views.HardwareGroupView.as_view(), name='hardwaregroup'),
    path('hardware-groups/<int:pk>/edit/', views.HardwareGroupEditView.as_view(), name='hardwaregroup_edit'),
    path('hardware-groups/<int:pk>/delete/', views.HardwareGroupDeleteView.as_view(), name='hardwaregroup_delete'),
    path('hardware-groups/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='hardwaregroup_changelog', kwargs={'model': models.HardwareGroup}),

    # ---------------------------------------------------------
    # Pillar 1: Software Images
    # ---------------------------------------------------------
    path('software-images/', views.SoftwareImageListView.as_view(), name='softwareimage_list'),
    path('software-images/add/', views.SoftwareImageEditView.as_view(), name='softwareimage_add'),
    path('software-images/import/', views.SoftwareImageBulkImportView.as_view(), name='softwareimage_import'),
    path('software-images/<int:pk>/', views.SoftwareImageView.as_view(), name='softwareimage'),
    path('software-images/<int:pk>/edit/', views.SoftwareImageEditView.as_view(), name='softwareimage_edit'),
    path('software-images/<int:pk>/delete/', views.SoftwareImageDeleteView.as_view(), name='softwareimage_delete'),
    path('software-images/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='softwareimage_changelog', kwargs={'model': models.SoftwareImage}),

    # ---------------------------------------------------------
    # Pillar 1b: File Servers
    # ---------------------------------------------------------
    path('file-servers/', views.FileServerListView.as_view(), name='fileserver_list'),
    path('file-servers/add/', views.FileServerEditView.as_view(), name='fileserver_add'),
    path('file-servers/import/', views.FileServerBulkImportView.as_view(), name='fileserver_import'),
    path('file-servers/<int:pk>/', views.FileServerView.as_view(), name='fileserver'),
    path('file-servers/<int:pk>/edit/', views.FileServerEditView.as_view(), name='fileserver_edit'),
    path('file-servers/<int:pk>/delete/', views.FileServerDeleteView.as_view(), name='fileserver_delete'),
    path('file-servers/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='fileserver_changelog', kwargs={'model': models.FileServer}),

    # ---------------------------------------------------------
    # Pillar 2: Golden Images
    # ---------------------------------------------------------
    path('golden-images/', views.GoldenImageListView.as_view(), name='goldenimage_list'),
    path('golden-images/add/', views.GoldenImageEditView.as_view(), name='goldenimage_add'),
    path('golden-images/import/', views.GoldenImageBulkImportView.as_view(), name='goldenimage_import'),
    path('golden-images/<int:pk>/', views.GoldenImageView.as_view(), name='goldenimage'),
    path('golden-images/<int:pk>/edit/', views.GoldenImageEditView.as_view(), name='goldenimage_edit'),
    path('golden-images/<int:pk>/delete/', views.GoldenImageDeleteView.as_view(), name='goldenimage_delete'),
    path('golden-images/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='goldenimage_changelog', kwargs={'model': models.GoldenImage}),
    path('golden-images/assignment/', views.GoldenImageAssignmentView.as_view(), name='goldenimage_assignment'),

    # ---------------------------------------------------------
    # Pillar 2b: Compliance Report
    # ---------------------------------------------------------
    path('compliance/dashboard/', views.ComplianceDashboardView.as_view(), name='compliance_dashboard'),
    path('compliance/', views.DeviceComplianceListView.as_view(), name='devicecompliance_list'),
    path('compliance/add/', views.DeviceComplianceEditView.as_view(), name='devicecompliance_add'),
    path('compliance/<int:pk>/', views.DeviceComplianceView.as_view(), name='devicecompliance'),
    path('compliance/<int:pk>/edit/', views.DeviceComplianceEditView.as_view(), name='devicecompliance_edit'),
    path('compliance/<int:pk>/delete/', views.DeviceComplianceDeleteView.as_view(), name='devicecompliance_delete'),
    path('compliance/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='devicecompliance_changelog', kwargs={'model': models.DeviceCompliance}),

    # ---------------------------------------------------------
    # Pillar    # --- Validation Check endpoints ---
    path('validation-checks/', views.ValidationCheckListView.as_view(), name='validationcheck_list'),
    path('validation-checks/add/', views.ValidationCheckEditView.as_view(), name='validationcheck_add'),
    path('validation-checks/<int:pk>/', views.ValidationCheckView.as_view(), name='validationcheck'),
    path('validation-checks/<int:pk>/edit/', views.ValidationCheckEditView.as_view(), name='validationcheck_edit'),
    path('validation-checks/<int:pk>/delete/', views.ValidationCheckDeleteView.as_view(), name='validationcheck_delete'),
    path('validation-checks/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='validationcheck_changelog', kwargs={'model': models.ValidationCheck}),
    path('validation-checks/import/', views.ValidationCheckBulkImportView.as_view(), name='validationcheck_import'),
    path('validation-checks/edit/', views.ValidationCheckBulkEditView.as_view(), name='validationcheck_bulk_edit'),
    path('validation-checks/delete/', views.ValidationCheckBulkDeleteView.as_view(), name='validationcheck_bulk_delete'),

    # --- Check Template endpoints ---
    path('check-templates/', views.CheckTemplateListView.as_view(), name='checktemplate_list'),
    path('check-templates/add/', views.CheckTemplateEditView.as_view(), name='checktemplate_add'),
    path('check-templates/<int:pk>/', views.CheckTemplateView.as_view(), name='checktemplate'),
    path('check-templates/<int:pk>/edit/', views.CheckTemplateEditView.as_view(), name='checktemplate_edit'),
    path('check-templates/<int:pk>/delete/', views.CheckTemplateDeleteView.as_view(), name='checktemplate_delete'),
    path('check-templates/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='checktemplate_changelog', kwargs={'model': models.CheckTemplate}),
    path('check-templates/import/', views.CheckTemplateBulkImportView.as_view(), name='checktemplate_import'),
    path('check-templates/edit/', views.CheckTemplateBulkEditView.as_view(), name='checktemplate_bulk_edit'),
    path('check-templates/delete/', views.CheckTemplateBulkDeleteView.as_view(), name='checktemplate_bulk_delete'),

    # --- Workflow endpoints ---es
    # ---------------------------------------------------------
    path('workflow-templates/', views.WorkflowTemplateListView.as_view(), name='workflowtemplate_list'),
    path('workflow-templates/add/', views.WorkflowTemplateEditView.as_view(), name='workflowtemplate_add'),
    path('workflow-templates/import/', views.WorkflowTemplateBulkImportView.as_view(), name='workflowtemplate_import'),
    path('workflow-templates/<int:pk>/', views.WorkflowTemplateView.as_view(), name='workflowtemplate'),
    path('workflow-templates/<int:pk>/edit/', views.WorkflowTemplateEditView.as_view(), name='workflowtemplate_edit'),
    path('workflow-templates/<int:pk>/delete/', views.WorkflowTemplateDeleteView.as_view(), name='workflowtemplate_delete'),
    path('workflow-templates/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='workflowtemplate_changelog', kwargs={'model': models.WorkflowTemplate}),
    
    path('workflow-steps/add/', views.WorkflowStepEditView.as_view(), name='workflowstep_add'),
    path('workflow-steps/<int:pk>/edit/', views.WorkflowStepEditView.as_view(), name='workflowstep_edit'),
    path('workflow-steps/<int:pk>/delete/', views.WorkflowStepDeleteView.as_view(), name='workflowstep_delete'),
    path('workflow-steps/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='workflowstep_changelog', kwargs={'model': models.WorkflowStep}),

    # ---------------------------------------------------------
    # Pillar 3 & 4: Upgrade Jobs
    # ---------------------------------------------------------
    path('upgrade-jobs/', views.UpgradeJobListView.as_view(), name='upgradejob_list'),
    path('upgrade-jobs/add/', views.UpgradeJobEditView.as_view(), name='upgradejob_add'),
    path('upgrade-jobs/<int:pk>/', views.UpgradeJobView.as_view(), name='upgradejob'),
    path('upgrade-jobs/<int:pk>/edit/', views.UpgradeJobEditView.as_view(), name='upgradejob_edit'),
    path('upgrade-jobs/<int:pk>/delete/', views.UpgradeJobDeleteView.as_view(), name='upgradejob_delete'),
    path('upgrade-jobs/<int:pk>/execute/', views.UpgradeJobExecuteView.as_view(), name='upgradejob_execute'),
    path('upgrade-jobs/<int:pk>/download-checks/', views.UpgradeJobDownloadChecksView.as_view(), name='upgradejob_download_checks'),
    path('upgrade-jobs/<int:pk>/download-logs/', views.UpgradeJobDownloadLogsView.as_view(), name='upgradejob_download_logs'),
    path('upgrade-jobs/<int:pk>/download-fragment/<str:fragment>/', views.UpgradeJobDownloadFragmentView.as_view(), name='upgradejob_download_fragment'),
    path('upgrade-jobs/<int:pk>/testbed/', views.UpgradeJobTestbedDownloadView.as_view(), name='upgradejob_testbed'),
    path('upgrade-jobs/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='upgradejob_changelog', kwargs={'model': models.UpgradeJob}),

    # ---------------------------------------------------------
    # Bulk Sync Jobs
    # ---------------------------------------------------------
    path('sync-jobs/', views.SyncJobListView.as_view(), name='syncjob_list'),
    path('sync-jobs/<int:pk>/', views.SyncJobView.as_view(), name='syncjob'),
    path('sync-jobs/delete/', views.SyncJobBulkDeleteView.as_view(), name='syncjob_bulk_delete'),
    path('sync-jobs/<int:pk>/delete/', views.SyncJobDeleteView.as_view(), name='syncjob_delete'),
    path('sync-jobs/<int:pk>/cancel/', views.SyncJobCancelView.as_view(), name='syncjob_cancel'),
    path('sync-jobs/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='syncjob_changelog', kwargs={'model': models.SyncJob}),

    # ---------------------------------------------------------
    # Pillar 5: Sync Validation Results
    # ---------------------------------------------------------
    path('sync-records/', views.DeviceSyncRecordListView.as_view(), name='devicesyncrecord_list'),
    path('sync-records/<int:pk>/', views.DeviceSyncRecordView.as_view(), name='devicesyncrecord'),
    path('sync-records/<int:pk>/approve/', views.DeviceSyncRecordApproveView.as_view(), name='devicesyncrecord_approve'),
    path('sync-records/approve/', views.DeviceSyncRecordBulkApproveView.as_view(), name='devicesyncrecord_bulk_approve'),
    path('sync-records/delete/', views.DeviceSyncRecordBulkDeleteView.as_view(), name='devicesyncrecord_bulk_delete'),
    path('sync-records/<int:pk>/delete/', views.DeviceSyncRecordDeleteView.as_view(), name='devicesyncrecord_delete'),
    path('sync-records/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='devicesyncrecord_changelog', kwargs={'model': models.DeviceSyncRecord}),

    # ---------------------------------------------------------
    # Job Logs (per-step execution logs for Upgrade Jobs)
    # ---------------------------------------------------------
    path('job-logs/', views.JobLogListView.as_view(), name='joblog_list'),
    path('job-logs/<int:pk>/', views.JobLogView.as_view(), name='joblog'),
    path('job-logs/<int:pk>/changelog/', ObjectChangeLogView.as_view(), name='joblog_changelog', kwargs={'model': models.JobLog}),

    # ---------------------------------------------------------
    # pyATS Testbed Generator
    # ---------------------------------------------------------
    path('testbed/', views.TestbedGeneratorView.as_view(), name='testbed_generator'),
    path('testbed/download/', views.TestbedDownloadView.as_view(), name='testbed_download'),
)
