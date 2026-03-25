import os
import json
import logging
from ..base import ScrapliTask, NetmikoTask, UniconTask
from ...models import CheckTemplate
from django.conf import settings

logger = logging.getLogger('netbox_swim')


class CiscoChecksScrapli(ScrapliTask):
    def execute(self, device, target_image=None, **kwargs):
        return None, "Scrapli checks not yet implemented. Set connection_priority to 'unicon'."


class CiscoChecksNetmiko(NetmikoTask):
    def execute(self, device, target_image=None, **kwargs):
        return None, "Netmiko checks not yet implemented. Set connection_priority to 'unicon'."


class CiscoChecksUnicon(UniconTask):
    """
    Pre/Post Check execution engine.
    
    Runs ValidationChecks from a CheckTemplate against a device:
      - category='genie': pyATS learn (bgp, ospf, etc.) → JSON output
      - category='command': CLI execute (show ip int brief, etc.) → raw text
      - category='genie' + command='config': show running-config
    
    Outputs saved to: /media/swim/checks/{job_id}/{phase}/{filename}.txt
    Report blob returned to engine for diff comparison.
    """

    def execute(self, device, target_image=None, step=None, job=None, phase='precheck', **kwargs):
        if not step or not job:
            return None, "Error: Missing WorkflowStep or UpgradeJob context."

        # Resolve CheckTemplate from step config
        check_template_id = step.extra_config.get('check_template_id')
        if not check_template_id:
            return None, "Skipped: No Check Template assigned to this step."

        try:
            template = CheckTemplate.objects.get(id=check_template_id)
        except CheckTemplate.DoesNotExist:
            return None, f"Error: CheckTemplate ID {check_template_id} not found."

        # Output directory: /media/swim/checks/{job_id}/{phase}/
        base_media = getattr(settings, 'MEDIA_ROOT', '/opt/netbox/netbox/media')
        output_dir = os.path.join(base_media, 'swim', 'checks', str(job.id))
        target_dir = os.path.join(output_dir, phase)
        os.makedirs(target_dir, exist_ok=True)

        # Filter checks by phase: 'precheck' → filter for 'pre' or 'both'
        phase_key = phase.replace('check', '')  # 'precheck' → 'pre', 'postcheck' → 'post'
        checks = template.checks.filter(phase__in=[phase_key, 'both'])
        if not checks.exists():
            return None, f"No applicable checks for '{phase}' in template: {template.name}"

        report_blob = f"====== EXECUTING TEMPLATE: {template.name} ======\n"
        failures = 0

        try:
            with self.connect(device, connection_timeout=60) as pyats_device:
                for check in checks:
                    success, output = self._run_check(pyats_device, check, target_dir, phase)

                    if success:
                        report_blob += f"\n[SUCCESS] {check.name} ({check.category}: {check.command})\n"
                    else:
                        report_blob += f"\n[FAILED] {check.name}: {output}\n"
                        failures += 1

                    # Include snippet in report blob for diff comparison
                    report_blob += f"--- {check.name} snippet ---\n"
                    lines = output.splitlines()
                    snipped = lines[:50]
                    report_blob += "\n".join(snipped)
                    report_blob += "\n...<truncated>\n" if len(lines) > 50 else "\n"

            # Summary
            if failures > 0:
                report_blob += f"\n====== {failures} CHECK(S) FAILED ======\n"
                logger.warning(f"[Checks] {failures} checks failed for {device.name} ({phase})")
            else:
                report_blob += f"\n====== ALL CHECKS PASSED ======\n"

        except Exception as e:
            logger.error(f"[Checks] Connection/execution error for {device.name}: {e}")
            report_blob += f"\n[ERROR] Check execution failed: {str(e)}\n"

        return target_dir, report_blob

    def _run_check(self, pyats_device, check, target_dir, phase):
        """
        Execute a single ValidationCheck and save output to file.
        Returns (success: bool, output: str)
        """
        safe_name = "".join(c if c.isalnum() else "_" for c in check.name)
        output = ""

        try:
            if check.category == 'genie':
                if check.command == 'config':
                    output = pyats_device.execute('show running-config', timeout=300)
                else:
                    # Genie learn (bgp, ospf, routing, etc.)
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

                # Genie filename: {command}_{check_name}_ops.txt
                filename = f"{check.command}_{safe_name}_ops.txt"
            else:
                # CLI command execution
                output = pyats_device.execute(check.command, timeout=300)
                filename = f"{safe_name}.txt"

            # Save output to file
            filepath = os.path.join(target_dir, filename)
            with open(filepath, 'w') as f:
                f.write(output)

            return True, output

        except Exception as e:
            error_msg = f"Error executing {check.name}: {str(e)}"
            logger.error(f"[Checks] {error_msg}")

            # Save error to file
            filename = f"{safe_name}.txt"
            filepath = os.path.join(target_dir, filename)
            with open(filepath, 'w') as f:
                f.write(error_msg)

            return False, error_msg
