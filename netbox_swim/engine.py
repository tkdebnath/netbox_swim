import logging
import os
from django_rq import job
from django.utils import timezone
from .models import UpgradeJob, JobLog, WorkflowStep

logger = logging.getLogger('netbox_swim')
logger.setLevel(logging.DEBUG)
if not logger.handlers:
    log_path = '/opt/netbox/netbox/media/swim_sync.log'
    # Fallback for dev environments
    if not os.path.exists('/opt/netbox/netbox/media/'):
        log_path = '/tmp/swim_sync.log'
    fh = logging.FileHandler(log_path)
    fh.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(process)d - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    
logger.info("SWIM Engine initialized.")

# ============================================================
# Background Worker Task
# ============================================================

def _log(job_obj, action_type, is_success=True, log_output='', step=None):
    """Helper to create a JobLog entry."""
    JobLog.objects.create(
        job=job_obj,
        action_type=action_type,
        is_success=is_success,
        log_output=log_output,
        step=step,
    )
    level = logging.INFO if is_success else logging.ERROR
    logger.log(level, f"Job {job_obj.id} | {action_type} | {'✓' if is_success else '✗'} {log_output[:200]}")


# ============================================================
# Device Sync Background Task
# ============================================================

def _sync_device_logic(device_id, auto_update=False, connection_library='scrapli', sync_job_id=None):
    """
    Core synchronous logic for syncing a single device.
    """
    from dcim.models import Device
    logger.info(f"Initiating Sync Logic for Device ID {device_id} (AutoUpdate={auto_update}, Library={connection_library})")
    try:
        device = Device.objects.get(pk=device_id)
    except Device.DoesNotExist:
        logger.error(f"Device ID {device_id} not found.")
        return f"Device {device_id} not found."
    
    # 1. Determine which Sync Task to run based on Platform and Library preference
    from .tasks.sync.cisco import (
        SyncCiscoIosDeviceScrapli, 
        SyncCiscoIosDeviceNetmiko, 
        SyncCiscoIosDeviceUnicon
    )
    
    platform_slug = getattr(device.platform, 'slug', '')
    logger.info(f"Target platform extracted as: {platform_slug}")
    
    # User Request: Must have an explicit IPv4/IPv6 assigned.
    if not device.primary_ip:
        logger.error(f"Device {device.name} lacks a Primary IP address. Sync aborted.")
        return f"Device lacks a Primary IP address. Sync aborted."

    task = None
    
    # Standardize the connection library format
    if 'cisco' in platform_slug.lower() or platform_slug == 'cisco-ios-xe':
        # Priority Logic: Use requested library if available, otherwise fallback in order: Scrapli > Netmiko > Unicon
        if connection_library == 'scrapli':
            task = SyncCiscoIosDeviceScrapli()
        elif connection_library == 'netmiko':
            task = SyncCiscoIosDeviceNetmiko()
        elif connection_library == 'unicon':
            task = SyncCiscoIosDeviceUnicon()
        
        # Absolute Fallback if choice was invalid
        if not task:
            task = SyncCiscoIosDeviceScrapli()
    
    if task is None:
        # Fallback or unsupported
        logger.error(f"No sync strategy found for platform {platform_slug}")
        return f"No sync strategy found for platform {platform_slug}"
        
    # 2. Execute the Sync Task
    try:
        from .models import DeviceSyncRecord
        import uuid
        
        # Get the job ID from the current RQ task context if available
        current_job_id = None
        try:
            from django_rq import get_current_job
            job = get_current_job()
            if job:
                current_job_id = job.id
        except Exception:
            pass

        # Create a sync record in 'syncing' state before connecting
        if sync_job_id:
            from .models import SyncJob
            sync_job = SyncJob.objects.filter(id=sync_job_id).first()
            if sync_job and sync_job.status == 'cancelled':
                logger.info(f"SyncJob {sync_job_id} cancelled. Aborting for {device.name}.")
                return [("info", "Job was cancelled.")]
        else:
            sync_job = None
            
        sync_record = DeviceSyncRecord.objects.create(
            device=device,
            sync_job=sync_job,
            status='syncing',
            is_active=True,
            job_id=current_job_id,
            log_messages=[f"[{timezone.now().strftime('%H:%M:%S')}] Setup connection to {device.primary_ip.address.ip} (via {device.name})..."]
        )

        logger.info(f"Starting sync execution for {device.name}")
        result = task.execute(device, auto_update=auto_update)
        
        has_error = any(msg_tuple[0] in ['error', 'failed'] for msg_tuple in result) if isinstance(result, list) else True
        if not has_error:
            device.custom_field_data['swim_last_sync_status'] = 'success'
            device.custom_field_data['swim_last_successful_sync'] = timezone.now().isoformat()
            device.save()
        else:
            device.custom_field_data['swim_last_sync_status'] = 'error'
            device.save()
        
        # Logic in execute() should ideally update this sync_record or create a new one.
        # For now, we clean up the tracker if it wasn't replaced (some tasks might create a new one instead of using the syncing one).
        if not DeviceSyncRecord.objects.filter(id=sync_record.id).exclude(status='syncing').exists():
            # If it's still specifically 'syncing' and hasn't changed, clean it up
            pass

        return result
    except Exception as e:
        from .models import DeviceSyncRecord
        logger.error(f"FATAL Engine error: {str(e)}", exc_info=True)
        DeviceSyncRecord.objects.filter(device=device, status='syncing').delete()
        DeviceSyncRecord.objects.create(
            device=device,
            sync_job=sync_job if 'sync_job' in locals() else None,
            status='failed',
            detected_diff={},
            log_messages=[f"SSH Transport Exception: {str(e)}"]
        )
        
        # Update device custom field to track sync failure
        device.custom_field_data['swim_last_sync_status'] = 'error'
        device.save()
        if 'sync_job' in locals() and sync_job:
            sync_job.failed_device_count += 1
            sync_job.save()
        return [("error", str(e))]


@job('default')
def execute_sync_job(device_id, auto_update=False):
    """
    Background worker job that connects to a SINGLE device.
    (Used by the individual "Sync SWIM Facts" button on the Device view)
    """
    return _sync_device_logic(device_id, auto_update)


@job('default')
def execute_bulk_sync_batch(device_ids, auto_update=False, max_concurrency=5, connection_library='scrapli'):
    """
    A single background task that manages a controlled swarm of Sync actions.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from .models import SyncJob
    from django.utils import timezone
    
    # Create the SyncJob tracker
    sync_job = SyncJob.objects.create(
        connection_library=connection_library,
        max_concurrency=max_concurrency,
        selected_device_count=len(device_ids),
        summary_logs=[f"Starting Bulk Sync for {len(device_ids)} devices."]
    )

    results = {}
    with ThreadPoolExecutor(max_workers=max_concurrency) as executor:
        future_to_device = {
            executor.submit(_sync_device_logic, dev_id, auto_update, connection_library, sync_job.id): dev_id 
            for dev_id in device_ids
        }
        
        for future in as_completed(future_to_device):
            dev_id = future_to_device[future]
            try:
                results[dev_id] = future.result()
            except Exception as e:
                logger.error(f"Bulk sync execution exception for device {dev_id}: {str(e)}")
                results[dev_id] = [("error", str(e))]
                sync_job.failed_device_count += 1
                
    sync_job.end_time = timezone.now()
    sync_job.status = 'completed' if sync_job.failed_device_count == 0 else 'failed'
    sync_job.summary_logs.append(f"Completed with {sync_job.failed_device_count} failures.")
    sync_job.save()
    return results


@job('default')
def execute_bulk_remediation(device_ids, connection_library='auto', dry_run=False, mock_run=False, scheduled_time=None):
    """
    Spawns background jobs to process all devices in the provided list.
    Evaluates Hardware Groups to find the correct Workflow Template.
    
    If scheduled_time is provided (a datetime), UpgradeJobs are created with
    status='scheduled' and execution is deferred to that time using django-rq's
    scheduler.enqueue_at().
    """
    # Iterates through device IDs, matches them against HardwareGroups,
    # finds the correct GoldenImage + WorkflowTemplate, and spawns an UpgradeJob for each.
    from dcim.models import Device
    from .models import UpgradeJob, HardwareGroup
    from django.utils import timezone
    import django_rq
    
    queued = 0
    skipped = 0
    successful_spawns = 0
    is_scheduled = scheduled_time is not None
    
    devices = Device.objects.filter(id__in=device_ids)
    
    for device in devices:
        # 1. Find matching Hardware Group
        matched_hg = None
        for hg in HardwareGroup.objects.all():
            if device in hg.get_matching_devices():
                matched_hg = hg
                break
                
        if not matched_hg:
            skipped += 1
            logger.warning(f"[Bulk Remediation] Skipping {device.name} - Not bound to any valid Hardware Group.")
            _create_aborted_job(device, "Hardware Group Missing", "Device does not match any defined Hardware Groups.")
            continue
            
        # 2. Get the assigned Workflow Template
        template = matched_hg.workflow_template
        if not template:
            skipped += 1
            logger.warning(f"[Bulk Remediation] Skipping {device.name} - Hardware Group '{matched_hg.name}' lacks a Workflow Template.")
            _create_aborted_job(device, "Workflow Template Missing", f"Hardware Group '{matched_hg.name}' does not have a mapped Workflow Template.")
            continue
            
        # 3. Get the target Golden Image
        golden = matched_hg.golden_images.first()
        if not golden or not golden.image:
            skipped += 1
            logger.warning(f"[Bulk Remediation] Skipping {device.name} - Hardware Group '{matched_hg.name}' lacks a Golden Image.")
            _create_aborted_job(device, "Golden Image Missing", f"Hardware Group '{matched_hg.name}' does not have a Golden Image mapped to it.")
            continue
            
        target_image = golden.image
        
        # 4. Create the UpgradeJob record
        priority_str = connection_library if connection_library != 'auto' else matched_hg.connection_priority
        
        initial_status = 'scheduled' if is_scheduled else 'pending'
        
        upgrade = UpgradeJob.objects.create(
            device=device,
            target_image=golden.image,
            template=matched_hg.workflow_template,
            status=initial_status,
            scheduled_time=scheduled_time,
            extra_config={'connection_priority': priority_str, 'dry_run': dry_run, 'mock_run': mock_run}
        )
        
        # 5. Enqueue or Schedule the execution
        if is_scheduled:
            # Use django-rq scheduler for deferred execution
            scheduler = django_rq.get_scheduler('default')
            scheduler.enqueue_at(
                scheduled_time,
                execute_upgrade_job,
                upgrade.id,
                dry_run=dry_run,
                mock_run=mock_run,
            )
            upgrade.job_log.append({
                "time": timezone.now().isoformat(),
                "level": "info",
                "message": f"Job scheduled for maintenance window: {scheduled_time.strftime('%Y-%m-%d %H:%M %Z')}. Execution will begin automatically at the scheduled time."
            })
            logger.info(f"[Bulk Remediation] Scheduled UpgradeJob #{upgrade.id} for {device.name} at {scheduled_time}")
        else:
            # Immediate execution
            django_rq.enqueue(execute_upgrade_job, upgrade.id, dry_run=dry_run, mock_run=mock_run)
            upgrade.job_log.append({
                "time": timezone.now().isoformat(),
                "level": "info",
                "message": f"Successfully validated Hardware Group compliance. Auto-Remediation Workflow started."
            })
            logger.info(f"[Bulk Remediation] Spawning background worker UpgradeJob #{upgrade.id} for {device.name}")
        
        if dry_run or mock_run:
            upgrade.job_log.append({"time": timezone.now().isoformat(), "level": "info", "message": f"Execution mode active. Dry Run: {dry_run}, Mock: {mock_run}."})
        
        upgrade.save()
        successful_spawns += 1
        queued += 1
        
    action_word = "scheduled" if is_scheduled else "spun up"
    return f"Successfully {action_word} {queued} upgrade queues. Skipped {skipped} devices."

def _create_aborted_job(device, reason, detailed_message):
    from .models import UpgradeJob, JobLog
    from django.utils import timezone
    job = UpgradeJob.objects.create(
        device=device,
        status='failed',
        start_time=timezone.now(),
        end_time=timezone.now()
    )
    JobLog.objects.create(
        job=job,
        step=None,
        action_type='Validation Error',
        is_success=False,
        log_output=f"[{reason}]\n{detailed_message}"
    )
    
def generate_pipeline_plan(job_id):
    """Returns a linear plan of what the upgrade workflow will do step-by-step."""
    from .models import UpgradeJob
    try:
        upgrade = UpgradeJob.objects.get(id=job_id)
    except UpgradeJob.DoesNotExist:
        return ["Error: Job not found"]

    device = upgrade.device
    target_image = upgrade.target_image
    template = upgrade.template
    
    if not template or not target_image:
        return ["Error: WorkflowTemplate or Target SoftwareImage missing."]
        
    platform_slug = getattr(device.platform, 'slug', 'cisco-ios-xe')
    model = getattr(getattr(device, 'device_type', None), 'model', 'Generic')

    # Match Hardware Group by checking which group this device belongs to
    hw_group_name = "None (Using Native Fallbacks)"
    from .models import HardwareGroup
    for hg in HardwareGroup.objects.all():
        if device in hg.get_matching_devices():
            hw_group_name = hg.name
            break
    
    # Pull Config Context overrides if present
    ctx = device.get_config_context()
    swim_config = ctx.get('swim', {})
    tacacs_source = swim_config.get('tacacs_source_interface', 'Not Specified in Config Context')
    mgmt_vrf = swim_config.get('mgmt_vrf', 'Not Specified in Config Context')
    
    # File Server Logic
    fs_info = "None Assigned"
    dl_link = "N/A"
    if target_image.file_server:
        fs = target_image.file_server
        fs_info = fs.name
        dl_link = f"{fs.protocol}://{fs.username}:***@{fs.ip_address}/{fs.base_path}/{target_image.image_file_name}"

    plan = []
    plan.append(f"====== PIPELINE DRY RUN ======")
    plan.append(f"Target Device: {device.name} ({model})")
    plan.append(f"Architecture: {platform_slug}")
    plan.append(f"Matching Hardware Group: {hw_group_name}")
    plan.append(f"Target Image: {target_image.image_name}")
    plan.append(f"File Server: {fs_info}")
    plan.append(f"Download Link: {dl_link}")
    plan.append(f"Mgmt VRF: {mgmt_vrf}")
    plan.append(f"TACACS Source Int: {tacacs_source}\n")
    plan.append("--- WORKFLOW SEQUENCE ---")

    for step in template.steps.all().order_by('order'):
        base_priority = "scrapli,netmiko,unicon"
        # Extract from hardware group assigned to this image
        hw_group = getattr(target_image, 'hardware_groups', None)
        if hw_group and hw_group.exists():
            base_priority = hw_group.first().connection_priority
            
        # Overrides 
        job_override = upgrade.extra_config.get('connection_priority_override') or upgrade.extra_config.get('connection_priority')
        if job_override: base_priority = job_override
        
        step_override = step.extra_config.get('connection_priority_override')
        if step_override: base_priority = step_override
            
        priority_list = [t.strip().lower() for t in base_priority.split(',')]
        
        # Action Map
        action = step.action_type
        
        # Map action type to readable name for dry-run output
        module_mapper = {
            'readiness': 'Readiness Logic',
            'distribution': 'Distribution Logic',
            'activation': 'Activation Logic',
            'precheck': 'Pre-Check Operations',
            'postcheck': 'Post-Check Operations',
        }
        
        if action in module_mapper:
            selected_lib = priority_list[0] if priority_list else 'UNKNOWN'
            class_predicted = f"Cisco{action.capitalize()}{selected_lib.capitalize()}"
            plan.append(f"[STEP {step.order} | {step.get_action_type_display()}] -> Will execute {class_predicted} using connection driver: {selected_lib.upper()}")
        else:
            plan.append(f"[STEP {step.order} | {step.get_action_type_display()}] -> Native platform sleep/ping/report routine.")

    return plan


@job('default')
def execute_upgrade_job(job_id, dry_run=False, mock_run=False):
    """Runs the full upgrade lifecycle: precheck -> distribute -> activate -> postcheck."""
    from .models import UpgradeJob, JobLog
    from django.utils import timezone
    import difflib

    try:
        upgrade = UpgradeJob.objects.get(id=job_id)
    except UpgradeJob.DoesNotExist:
        return f"UpgradeJob {job_id} not found"

    device = upgrade.device

    # --- Safety Check: Prevent Concurrent Jobs on Same Device ---
    active_jobs = UpgradeJob.objects.filter(
        device=device,
        status__in=['pending', 'running', 'distributing', 'activating']
    ).exclude(id=job_id)

    if active_jobs.exists():
        reason = f"Device already has an active firmware job (ID: {active_jobs.first().id}) running. Aborting to prevent collision."
        JobLog.objects.create(
            job=upgrade,
            action_type='precheck',
            result='error',
            log_output=reason,
            is_success=False
        )
        upgrade.status = 'failed'
        upgrade.end_time = timezone.now()
        upgrade.save()
        return reason

    upgrade.status = 'running'
    upgrade.start_time = timezone.now()
    upgrade.save()

    device = upgrade.device
    target_image = upgrade.target_image
    template = upgrade.template
    
    # ---------------------------------------------------------
    # Validation Check: Ensure device has recently synced
    # ---------------------------------------------------------
    from datetime import timedelta
    import dateutil.parser
    
    last_sync_str = device.custom_field_data.get('swim_last_successful_sync')
    needs_sync = True
    
    if last_sync_str:
        try:
            last_sync_dt = dateutil.parser.isoparse(last_sync_str)
            if timezone.now() - last_sync_dt < timedelta(minutes=30):
                needs_sync = False
        except Exception:
            pass
            
    if needs_sync:
        upgrade.job_log.append({"time": timezone.now().isoformat(), "level": "warning", "message": "Last sync is older than 30 minutes or missing. Forcing pre-flight Sync."})
        upgrade.save()
        
        sync_result = _sync_device_logic(device.id, auto_update=True)
        has_sync_error = any(msg_tuple[0] in ['error', 'failed'] for msg_tuple in sync_result) if isinstance(sync_result, list) else True
        
        if has_sync_error:
            upgrade.job_log.append({"time": timezone.now().isoformat(), "level": "error", "message": "Pre-flight Sync encountered a fatal error. Upgrade aborted manually to ensure safety."})
            upgrade.status = 'failed'
            upgrade.end_time = timezone.now()
            upgrade.save()
            return "Pre-flight Sync Failed"
            
        upgrade.job_log.append({"time": timezone.now().isoformat(), "level": "success", "message": "Pre-flight Sync completed. Proceeding to Workflow Execution."})
        upgrade.save()
        
        # Refresh device object to pull latest DB state just in case
        device.refresh_from_db()
    if not template or not target_image:
        JobLog.objects.create(job=upgrade, action_type='precheck', result='error', log_output="Missing template or target image.", is_success=False)
        upgrade.status = 'failed'
        upgrade.end_time = timezone.now()
        upgrade.save()
        return "Failed: Missing assets"

    # Platform task mapping 
    # Currently supports Cisco IOS-XE; add platform branches here as needed
    platform_slug = getattr(device.platform, 'slug', 'cisco-ios-xe')
    
    # ---------------------------------------------------------
    # Import Modular Tasks
    # ---------------------------------------------------------
    from .tasks.readiness.cisco import ReadinessCiscoScrapli, ReadinessCiscoNetmiko, ReadinessCiscoUnicon
    from .tasks.distribution.cisco import CiscoDistributeScrapli, CiscoDistributeNetmiko, CiscoDistributeUnicon
    from .tasks.activation.cisco import CiscoActivateScrapli, CiscoActivateNetmiko, CiscoActivateUnicon
    from .tasks.checks.cisco import CiscoChecksScrapli, CiscoChecksNetmiko, CiscoChecksUnicon
    from .tasks.verification.cisco import CiscoVerifyScrapli, CiscoVerifyNetmiko, CiscoVerifyUnicon
    
    TASK_REGISTRY = {
        'readiness': {'scrapli': ReadinessCiscoScrapli, 'netmiko': ReadinessCiscoNetmiko, 'unicon': ReadinessCiscoUnicon},
        'distribution': {'scrapli': CiscoDistributeScrapli, 'netmiko': CiscoDistributeNetmiko, 'unicon': CiscoDistributeUnicon},
        'activation': {'scrapli': CiscoActivateScrapli, 'netmiko': CiscoActivateNetmiko, 'unicon': CiscoActivateUnicon},
        'precheck': {'scrapli': CiscoChecksScrapli, 'netmiko': CiscoChecksNetmiko, 'unicon': CiscoChecksUnicon},
        'postcheck': {'scrapli': CiscoChecksScrapli, 'netmiko': CiscoChecksNetmiko, 'unicon': CiscoChecksUnicon},
        'verification': {'scrapli': CiscoVerifyScrapli, 'netmiko': CiscoVerifyNetmiko, 'unicon': CiscoVerifyUnicon},
    }

    overall_success = True
    precheck_output = ""
    postcheck_output = ""

    for step in template.steps.all().order_by('order'):
        log_entry = JobLog.objects.create(
            job=upgrade,
            action_type=step.action_type,
            is_success=True,
            log_output=f"Starting Step: {step.get_action_type_display()}...\n"
        )
        
        # --- 1. Compute Connection Priority ---
        base_priority = "scrapli,netmiko,unicon"
        # Extract from hardware group assigned to this image
        hw_group = getattr(target_image, 'hardware_groups', None)
        if hw_group and hw_group.exists():
            base_priority = hw_group.first().connection_priority
            
        # Overrides 
        job_override = upgrade.extra_config.get('connection_priority_override') or upgrade.extra_config.get('connection_priority')
        if job_override: base_priority = job_override
        
        step_override = step.extra_config.get('connection_priority_override')
        if step_override: base_priority = step_override
            
        priority_list = [t.strip().lower() for t in base_priority.split(',')]
        
        # ---------------------------------------------------------
        # Execute Step Action Types
        # ---------------------------------------------------------
        action = step.action_type
        
        try:
            # --- Inline handlers for steps that don't need SSH connections ---
            if action == 'ping':
                import subprocess
                import time as _time
                
                # Check for explicit IP override from the 'Ping Target IP' UI field
                target_override = step.extra_config.get('target_ip') if step.extra_config else None
                host = target_override if target_override else (str(device.primary_ip.address.ip) if device.primary_ip else None)
                
                if not host:
                    log_entry.log_output += "PING FAILED: No Target IP specified and Device has no Primary IP assigned.\n"
                    log_entry.is_success = False
                    overall_success = False
                else:
                    retries = step.extra_config.get('retries', 3) if step.extra_config else 3
                    interval = step.extra_config.get('interval', 10) if step.extra_config else 10
                    log_entry.log_output += f"Checking reachability for {device.name} ({host})...\n"
                    
                    reachable = False
                    for attempt in range(1, retries + 1):
                        try:
                            result = subprocess.call(
                                ['ping', '-c', '1', host],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2
                            )
                            if result == 0:
                                log_entry.log_output += f"Device {device.name} is reachable! (attempt {attempt})\n"
                                reachable = True
                                break
                        except subprocess.TimeoutExpired:
                            pass
                        
                        log_entry.log_output += f"Ping attempt {attempt}/{retries} failed. Retrying in {interval}s...\n"
                        if attempt < retries:
                            _time.sleep(interval)
                    
                    if reachable:
                        log_entry.log_output += f"\nPING SUCCESS: {host} is reachable.\n"
                        log_entry.log_output += "Waiting 30s for device to fully initialize...\n"
                        _time.sleep(30)
                        log_entry.is_success = True
                    else:
                        log_entry.log_output += f"\nPING FAILED: {host} unreachable after {retries} attempts.\n"
                        log_entry.is_success = False
                        overall_success = False

                log_entry.save()
                if not overall_success:
                    break
                continue

            if action == 'wait':
                import time as _time
                # Read 'duration' key populated by the 'Wait Duration' UI field
                wait_seconds = step.extra_config.get('duration', 30) if step.extra_config else 30
                log_entry.log_output += f"Waiting {wait_seconds} seconds before proceeding...\n"
                log_entry.save()
                _time.sleep(wait_seconds)
                log_entry.log_output += f"Wait complete ({wait_seconds}s elapsed).\n"
                log_entry.is_success = True
                log_entry.save()
                continue

            # --- Task Registry steps (require SSH connection) ---
            if action not in TASK_REGISTRY:
                log_entry.log_output += f"No mapped Engine Task for {action}. Simulating success.\n"
                log_entry.is_success = True
                log_entry.save()
                continue
                
            # --- 2. Iterate libraries by sequence until success ---
            executor_class = None
            for lib in priority_list:
                executor_class = TASK_REGISTRY[action].get(lib)
                if executor_class:
                    log_entry.log_output += f"Attempting execution using connection library: [{lib.upper()}]\n"
                    break
                    
            if not executor_class:
                raise Exception(f"No suitable connection libraries found in priority string: {base_priority}")

            executor = executor_class()
            
            # Action Mapping
            if mock_run:
                log_entry.log_output += f"\n[MOCK RUN] Mocking {action} step. No real connections established.\n"
                log_entry.is_success = True
            elif dry_run and action in ['distribution', 'activation']:
                log_entry.log_output += f"\n[DRY RUN] Bypassing actual image {action} logic.\n"
                log_entry.is_success = True
            else:
                if action in ['precheck', 'postcheck']:
                    output_dirs, report_blob = executor.execute(device, target_image, step=step, job=upgrade, phase=action)
                    log_entry.log_output += f"\n{action.upper()} OUTPUT:\n" + str(report_blob)
                    
                    if action == 'precheck':
                        precheck_output = report_blob
                    else:
                        postcheck_output = report_blob
                        
                        # Auto-Diff Fallback directly here since it works
                        log_entry.log_output += "\n--- PRE/POST DIFF REPORT ---\n"
                        diff = list(difflib.unified_diff(
                            precheck_output.splitlines(keepends=True),
                            postcheck_output.splitlines(keepends=True),
                            fromfile='Pre-Upgrade',
                            tofile='Post-Upgrade',
                            n=0
                        ))
                        if not diff:
                            log_entry.log_output += "No operational differences detected."
                        else:
                            log_entry.log_output += "".join(diff)
                            
                    log_entry.is_success = True
                else:
                    # Execute Distribution, Activation, Readiness
                    report_blob = executor.execute(device, target_image)
                    
                    # Format output based on return type
                    if isinstance(report_blob, list):
                        # Readiness returns list of (status, message) tuples
                        formatted = "\n".join(f"[{s.upper()}] {m}" for s, m in report_blob)
                        log_entry.log_output += f"\n{action.upper()} OUTPUT:\n" + formatted
                        
                        # Check for failures in readiness results
                        failure_indicators = {'failed', 'fail', 'error'}
                        has_failure = any(
                            s.lower() in failure_indicators 
                            for s, m in report_blob 
                            if isinstance(s, str)
                        )
                        if has_failure:
                            log_entry.is_success = False
                            overall_success = False
                        else:
                            log_entry.is_success = True
                    else:
                        log_entry.log_output += f"\n{action.upper()} OUTPUT:\n" + str(report_blob)
                        log_entry.is_success = True

        except Exception as e:
            overall_success = False
            log_entry.is_success = False
            log_entry.log_output += f"\nERROR: {str(e)}"
        
        log_entry.save()
        if not overall_success:
            # We generally halt the pipeline if a step fails (e.g., Readiness/Distribution).
            # However, we want to ensure Post-Checks and Reports ALWAYS run even if 
            # Verification fails, so we can gather crucial state diffs for debugging.
            if action in ['verification', 'postcheck', 'report']:
                logger.warning(f"[Engine] Step '{action}' failed, but continuing pipeline to gather artifacts.")
            else:
                break

    # Finalize Job and Generate Zip Payload
    try:
        archive_meta = _generate_checks_archive(upgrade)
        if archive_meta:
            upgrade.extra_config['checks_archive'] = archive_meta
            upgrade.job_log.append({
                "time": timezone.now().isoformat(),
                "level": "info",
                "message": f"Checks archive generated: {archive_meta['filename']}"
            })
    except Exception as e:
        logger.error(f"Failed to compile Checks Archive for {upgrade.id}: {str(e)}")
            
    upgrade.status = 'completed' if overall_success else 'failed'
    upgrade.end_time = timezone.now()
    upgrade.save()
    
    return upgrade.status


def _generate_checks_archive(job):
    """
    Generates a ZIP archive containing precheck/, postcheck/, and diffs/ folders.
    Archive name: <devicename>_checks_<ddmmyy>.zip
    """
    import os
    import shutil
    import subprocess
    from django.conf import settings
    
    base_media = getattr(settings, 'MEDIA_ROOT', '/opt/netbox/netbox/media')
    job_dir = os.path.join(base_media, 'swim', 'checks', str(job.id))
    
    pre_dir = os.path.join(job_dir, 'precheck')
    post_dir = os.path.join(job_dir, 'postcheck')
    diff_dir = os.path.join(job_dir, 'diffs')
    
    # At least one of pre/post must exist
    has_pre = os.path.exists(pre_dir)
    has_post = os.path.exists(post_dir)
    
    if not has_pre and not has_post:
        return None
    
    # Run Genie diff if both pre and post exist
    if has_pre and has_post:
        os.makedirs(diff_dir, exist_ok=True)
        cmd = ["genie", "diff", pre_dir, post_dir, "--output", diff_dir]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.stdout:
                with open(os.path.join(diff_dir, 'summary.log'), 'w') as f:
                    f.write(result.stdout)
            if result.stderr:
                with open(os.path.join(diff_dir, 'errors.log'), 'w') as f:
                    f.write(result.stderr)
        except Exception as e:
            logger.warning(f"Genie diff CLI failed: {str(e)}")
            # Write a fallback diff using Python's difflib
            _generate_fallback_diff(pre_dir, post_dir, diff_dir)
    
    # Build archive name: devicename_checks_ddmmyy.zip
    device_name = job.device.name or f"device_{job.device.pk}"
    # Sanitize device name for filesystem
    safe_name = "".join(c if c.isalnum() or c in ('-', '_') else '_' for c in device_name)
    date_str = (job.end_time or job.start_time or timezone.now()).strftime('%d%m%y')
    archive_filename = f"{safe_name}_checks_{date_str}"
    
    archive_base = os.path.join(base_media, 'swim', 'checks', archive_filename)
    shutil.make_archive(archive_base, 'zip', job_dir)
    
    media_url = getattr(settings, 'MEDIA_URL', '/media/')
    return {
        'filename': f"{archive_filename}.zip",
        'url': f"{media_url}swim/checks/{archive_filename}.zip",
        'job_dir': job_dir,
        'has_precheck': has_pre,
        'has_postcheck': has_post,
        'has_diffs': os.path.exists(diff_dir) and len(os.listdir(diff_dir)) > 0,
    }


def _generate_fallback_diff(pre_dir, post_dir, diff_dir):
    """Fallback diffing using Python's difflib when Genie CLI is not available."""
    import os
    import difflib
    
    pre_files = set(os.listdir(pre_dir)) if os.path.exists(pre_dir) else set()
    post_files = set(os.listdir(post_dir)) if os.path.exists(post_dir) else set()
    common = pre_files & post_files
    
    summary_lines = []
    for fname in sorted(common):
        pre_path = os.path.join(pre_dir, fname)
        post_path = os.path.join(post_dir, fname)
        
        with open(pre_path, 'r', errors='replace') as f:
            pre_lines = f.readlines()
        with open(post_path, 'r', errors='replace') as f:
            post_lines = f.readlines()
        
        diff = list(difflib.unified_diff(
            pre_lines, post_lines,
            fromfile=f'precheck/{fname}',
            tofile=f'postcheck/{fname}',
            n=3
        ))
        
        if diff:
            diff_path = os.path.join(diff_dir, f"diff_{fname}")
            with open(diff_path, 'w') as f:
                f.writelines(diff)
            summary_lines.append(f"CHANGED: {fname} ({len(diff)} diff lines)")
        else:
            summary_lines.append(f"IDENTICAL: {fname}")
    
    for fname in sorted(pre_files - post_files):
        summary_lines.append(f"REMOVED (post-upgrade): {fname}")
    for fname in sorted(post_files - pre_files):
        summary_lines.append(f"NEW (post-upgrade): {fname}")
    
    with open(os.path.join(diff_dir, 'summary.log'), 'w') as f:
        f.write("=== Python difflib Fallback Comparison ===\n\n")
        f.write("\n".join(summary_lines))           

def _fail_job(upgrade_job, reason):
    """Mark a job as failed and log the reason."""
    upgrade_job.status = UpgradeJob.StatusChoices.FAILED
    upgrade_job.end_time = timezone.now()
    upgrade_job.save()
    _log(upgrade_job, 'workflow', is_success=False, log_output=reason)
    logger.error(f"Upgrade job {upgrade_job.id} failed: {reason}")
