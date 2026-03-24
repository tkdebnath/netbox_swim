from netbox.api.routers import NetBoxRouter
from . import views

router = NetBoxRouter()
router.register('hardware-groups', views.HardwareGroupViewSet)
router.register('images', views.SoftwareImageViewSet)
router.register('file-servers', views.FileServerViewSet)
router.register('golden-images', views.GoldenImageViewSet)
router.register('compliance', views.DeviceComplianceViewSet)
router.register('workflow-templates', views.WorkflowTemplateViewSet)
router.register('workflow-steps', views.WorkflowStepViewSet)
router.register('upgrade-jobs', views.UpgradeJobViewSet)
router.register('job-logs', views.JobLogViewSet)
router.register('sync-jobs', views.SyncJobViewSet)
router.register('sync-records', views.DeviceSyncRecordViewSet)
router.register('validation-checks', views.ValidationCheckViewSet)
router.register('check-templates', views.CheckTemplateViewSet)

urlpatterns = router.urls
