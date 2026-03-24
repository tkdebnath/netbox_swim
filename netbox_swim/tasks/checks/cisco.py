import os
import json
import logging
from ..base import ScrapliTask, NetmikoTask, UniconTask
from ...models import CheckTemplate
from django.conf import settings

logger = logging.getLogger('netbox_swim')

class CiscoChecksLogicMixin:
    """Pre/Post Check executions. Wraps Unicon logic."""
    pass
        
class CiscoChecksScrapli(ScrapliTask, CiscoChecksLogicMixin):
    def execute(self, device, target_image=None, **kwargs):
        raise NotImplementedError("Scrapli checker not implemented")

class CiscoChecksNetmiko(NetmikoTask, CiscoChecksLogicMixin):
    def execute(self, device, target_image=None, **kwargs):
        raise NotImplementedError("Netmiko checker not implemented")

class CiscoChecksUnicon(UniconTask, CiscoChecksLogicMixin):
    def execute(self, device, target_image=None, step=None, job=None, phase='precheck', **kwargs):
        if not step or not job:
            return None, "Error: Missing WorkflowStep or UpgradeJob context."
            
        check_template_id = step.extra_config.get('check_template_id')
        if not check_template_id:
            return None, "Skipped: No Check Template assigned to this step."
            
        try:
            template = CheckTemplate.objects.get(id=check_template_id)
        except CheckTemplate.DoesNotExist:
            return None, f"Error: CheckTemplate ID {check_template_id} not found."
            
        # Try finding /media/ path
        base_media = getattr(settings, 'MEDIA_ROOT', '/opt/netbox/netbox/media')
        output_dir = os.path.join(base_media, 'swim', 'checks', str(job.id))
        target_dir = os.path.join(output_dir, phase)
        os.makedirs(target_dir, exist_ok=True)
        
        checks = template.checks.filter(phase__in=[phase.replace('check', ''), 'both'])
        if not checks.exists():
            return None, f"No applicable checks assigned for {phase} inside Template: {template.name}"
            
        report_blob = f"====== EXECUTING TEMPLATE: {template.name} ======\n"
        
        with self.connect(device, connection_timeout=60) as pyats_device:
            for check in checks:
                safe_name = "".join(c if c.isalnum() else "_" for c in check.name)
                filename = f"{check.category}_{safe_name}.txt"
                filepath = os.path.join(target_dir, filename)
                
                output = ""
                try:
                    if check.category == 'genie':
                        if check.command == 'config':
                            output = pyats_device.execute('show running-config', timeout=300)
                        else:
                            try:
                                learned = pyats_device.learn(check.command, timeout=300)
                            except TypeError:
                                learned = pyats_device.learn(check.command)
                                
                            if hasattr(learned, 'to_dict'):
                                output = json.dumps(learned.to_dict(), indent=2, default=str)
                            elif hasattr(learned, 'info'):
                                output = json.dumps(learned.info, indent=2, default=str)
                            else:
                                import pprint
                                output = pprint.pformat(dict(learned), width=120)
                    else:
                        # Standard CLI command
                        output = pyats_device.execute(check.command, timeout=300)
                        
                    with open(filepath, 'w') as f:
                        f.write(output)
                        
                    report_blob += f"\n[SUCCESS] {check.name} ({check.category}: {check.command})\n"
                    # We inject a snippet into the blob for the DB to do rudimentary diffs.
                    report_blob += f"--- {check.name} snippet ---\n"
                    lines = output.splitlines()
                    snipped = lines[:50]
                    report_blob += "\n".join(snipped) + ("\n...<truncated>\n" if len(lines) > 50 else "\n")
                    
                except Exception as e:
                    logger.error(f"Failed check {check.name}: {str(e)}")
                    report_blob += f"\n[FAILED] {check.name}: {str(e)}\n"
                    with open(filepath, 'w') as f:
                        f.write(f"Error executing {check.name}: {str(e)}")
                        
        return target_dir, report_blob
