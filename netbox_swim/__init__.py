from netbox.plugins import PluginConfig

class NetBoxSwimConfig(PluginConfig):
    name = 'netbox_swim'
    verbose_name = 'Firmware & OS Upgrades'
    description = 'Manage firmware images, compliance, validation, and upgrade workflows.'
    version = '0.1.0'
    base_url = 'swim'
    template_extensions = 'template_content.template_extensions'

    def ready(self):
        super().ready()
        # Provision required custom fields on dcim.Device at startup
        try:
            from django.contrib.contenttypes.models import ContentType
            from extras.models import CustomField, CustomFieldChoiceSet
            from extras.choices import CustomFieldTypeChoices
            from dcim.models import Device

            device_ct = ContentType.objects.get_for_model(Device)

            from .constants import SWIM_CUSTOM_FIELDS
            group_label = 'SWIM Derived Data'

            for field_def in SWIM_CUSTOM_FIELDS:
                if field_def['type'] == 'select':
                    # Create the Choice Set first
                    choice_set, _ = CustomFieldChoiceSet.objects.get_or_create(
                        name=f"{field_def['name']}_choices",
                        defaults={'extra_choices': field_def.get('choices', [])}
                    )
                    cf, _ = CustomField.objects.get_or_create(
                        name=field_def['name'],
                        type=CustomFieldTypeChoices.TYPE_SELECT,
                        defaults={
                            'label': field_def['label'],
                            'group_name': group_label,
                            'description': field_def.get('description', ''),
                            'choice_set': choice_set,
                            'required': False,
                            'weight': field_def.get('weight', 100),
                        }
                    )
                elif field_def['type'] == 'datetime':
                    cf, _ = CustomField.objects.get_or_create(
                        name=field_def['name'],
                        type=CustomFieldTypeChoices.TYPE_DATETIME,
                        defaults={
                            'label': field_def['label'],
                            'group_name': group_label,
                            'description': field_def.get('description', ''),
                            'required': False,
                            'weight': field_def.get('weight', 100),
                        }
                    )
                else:
                    cf, _ = CustomField.objects.get_or_create(
                        name=field_def['name'],
                        type=CustomFieldTypeChoices.TYPE_TEXT,
                        defaults={
                            'label': field_def['label'],
                            'group_name': group_label,
                            'description': field_def.get('description', ''),
                            'required': False,
                            'weight': field_def.get('weight', 100),
                        }
                    )
                
                # Assign custom field to device content type
                cf.object_types.add(device_ct)
                cf.group_name = group_label
                cf.save()

        except Exception as e:
            # Handle cases where DB might not be ready (e.g. during migrations)
            pass

        # Clean up orphaned jobs from unclean shutdowns
        # Jobs stuck in active states after a restart get marked as failed
        try:
            from .models import DeviceSyncRecord, SyncJob
            from django.utils import timezone
            
            # Mark stale sync records as failed
            orphaned_records = DeviceSyncRecord.objects.filter(status='syncing')
            for rec in orphaned_records:
                rec.status = 'failed'
                rec.log_messages.append(f"[{timezone.now().strftime('%H:%M:%S')}] FATAL: Job abruptly aborted due to NetBox Server Container Restart.")
                rec.save()

            # Mark stale bulk sync jobs as errored
            orphaned_jobs = SyncJob.objects.filter(status__in=['pending', 'running'])
            for job in orphaned_jobs:
                job.status = 'error'
                job.end_time = timezone.now()
                job.summary_logs.append(f"[{timezone.now().strftime('%H:%M:%S')}] FATAL: Container restarted. Job aborted.")
                job.save()

            # Mark stale upgrade jobs as failed
            from .models import UpgradeJob, JobLog
            orphaned_upgrades = UpgradeJob.objects.filter(status__in=['pending', 'scheduled', 'running'])
            for up in orphaned_upgrades:
                up.status = 'failed'
                up.end_time = timezone.now()
                up.save()
                
                # Log the failure reason
                JobLog.objects.create(
                    job=up,
                    step=None,
                    action_type="Container Interruption",
                    result="Terminated",
                    is_success=False,
                    log_output=f"[{timezone.now().strftime('%H:%M:%S')}] FATAL: Job abruptly aborted due to NetBox Server Container Restart/Reboot."
                )
        except Exception as e:
            # Handle cases where Models might not be initialized yet
            pass

        # Create default workflow template if not present
        try:
            from .models import WorkflowTemplate, WorkflowStep
            if not WorkflowTemplate.objects.filter(name="Default SWIM Upgrade Lifecycle").exists():
                wt = WorkflowTemplate.objects.create(
                    name="Default SWIM Upgrade Lifecycle", 
                    description="Standard 9-step upgrade lifecycle template.",
                    is_active=True
                )
                
                # Standard upgrade sequence
                actions = [
                    (1, WorkflowStep.ActionTypes.READINESS),
                    (2, WorkflowStep.ActionTypes.DISTRIBUTE),
                    (3, WorkflowStep.ActionTypes.PRECHECK),
                    (4, WorkflowStep.ActionTypes.ACTIVATE),
                    (5, WorkflowStep.ActionTypes.WAIT),
                    (6, WorkflowStep.ActionTypes.PING),
                    (7, WorkflowStep.ActionTypes.POSTCHECK),
                    (8, WorkflowStep.ActionTypes.VERIFICATION),
                    (9, WorkflowStep.ActionTypes.REPORT)
                ]
                for order, action in actions:
                    config = {}
                    if action in [WorkflowStep.ActionTypes.DISTRIBUTE, WorkflowStep.ActionTypes.ACTIVATE]:
                        config = {"connection_priority_override": "unicon,netmiko,scrapli"}
                        
                    WorkflowStep.objects.create(template=wt, order=order, action_type=action, extra_config=config)
        except Exception:
            pass

config = NetBoxSwimConfig
