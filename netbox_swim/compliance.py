"""
Version comparison and compliance severity utilities for the SWIM plugin.
"""
import re


def parse_version_tuple(version_string):
    """
    Converts a version string like '17.09.04', '17.6.5a', '10.2(3)F'
    into a tuple of integers for comparison purposes.
    Non-numeric characters are stripped. Returns None if unparsable.
    """
    if not version_string:
        return None
    # Strip leading/trailing whitespace
    version_string = version_string.strip()
    # Replace common separators with dots: '10.2(3)F' -> '10.2.3'
    cleaned = re.sub(r'[^0-9.]+', '.', version_string)
    # Remove trailing dots
    cleaned = cleaned.strip('.')
    # Split and convert to integers
    parts = []
    for segment in cleaned.split('.'):
        if segment:
            try:
                parts.append(int(segment))
            except ValueError:
                continue
    return tuple(parts) if parts else None


def compute_version_gap(current_str, golden_str):
    """
    Compares two version strings and returns an integer representing progress.
    Positive = behind golden (needs upgrade), Negative = ahead of golden.
    Returns None if either version is unparsable.
    """
    cur = parse_version_tuple(current_str)
    gold = parse_version_tuple(golden_str)
    if cur is None or gold is None:
        return None

    # Pad to equal length for fair comparison
    max_len = max(len(cur), len(gold))
    cur_padded = cur + (0,) * (max_len - len(cur))
    gold_padded = gold + (0,) * (max_len - len(gold))

    # Calculate a weighted distance: major.minor.patch
    # Weight: [1000, 100, 10, 1] to reflect severity of each level
    weights = []
    for i in range(max_len):
        weights.append(10 ** (max_len - 1 - i))

    gap = 0
    for i in range(max_len):
        gap += (gold_padded[i] - cur_padded[i]) * weights[i]

    return gap


def classify_severity(gap):
    """
    Maps a numeric version gap to a severity classification.
    Returns a tuple of (severity_label, css_class).
    """
    if gap is None:
        return 'Unknown', 'secondary'
    if gap < 0:
        return 'Ahead', 'info'
    if gap == 0:
        return 'Compliant', 'success'
    if gap <= 10:
        return 'Low', 'warning'
    if gap <= 100:
        return 'Medium', 'orange'
    if gap <= 1000:
        return 'High', 'danger'
    return 'Critical', 'dark'


def capture_compliance_snapshot():
    """
    Evaluates all active devices, computes their compliance state,
    and saves (or updates) today's ComplianceSnapshot record.
    Call this after sync jobs complete or on a daily schedule.
    """
    from datetime import date
    from dcim.models import Device
    from . import models as swim_models

    devices = Device.objects.filter(status='active').select_related(
        'site', 'platform', 'device_type'
    )

    # Build hw group mapping
    all_hw_groups = swim_models.HardwareGroup.objects.prefetch_related(
        'platforms', 'device_types', 'manual_includes', 'manual_excludes',
        'golden_images__image'
    )
    device_hw_map = {}
    for hg in all_hw_groups:
        for dev in hg.get_matching_devices():
            if dev.pk not in device_hw_map:
                device_hw_map[dev.pk] = hg

    golden_by_dtype = {}
    golden_by_hwgroup = {}
    for gi in swim_models.GoldenImage.objects.prefetch_related('device_types', 'hardware_groups').select_related('image'):
        for dt in gi.device_types.all():
            golden_by_dtype[(dt.pk, gi.deployment_mode)] = gi
        for hg in gi.hardware_groups.all():
            golden_by_hwgroup[(hg.pk, gi.deployment_mode)] = gi

    counts = {'total': 0, 'compliant': 0, 'non_compliant': 0, 'ahead': 0, 'unknown': 0}

    for device in devices:
        hw_group = device_hw_map.get(device.pk)
        if not hw_group:
            continue  # Only count devices in a hardware group

        counts['total'] += 1
        current_version = (device.custom_field_data or {}).get('software_version', '')
        deployment_mode = (device.custom_field_data or {}).get('deployment_mode', 'universal')

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
        severity, _ = classify_severity(gap)

        if severity == 'Compliant':
            counts['compliant'] += 1
        elif severity == 'Ahead':
            counts['ahead'] += 1
        elif severity == 'Unknown':
            counts['unknown'] += 1
        else:
            counts['non_compliant'] += 1

    today = date.today()
    swim_models.ComplianceSnapshot.objects.update_or_create(
        date=today,
        defaults={
            'total_devices': counts['total'],
            'compliant': counts['compliant'],
            'non_compliant': counts['non_compliant'],
            'ahead': counts['ahead'],
            'unknown': counts['unknown'],
        }
    )
    return counts

