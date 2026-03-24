from .base import UpgradeStrategy, register_strategy
from ..tasks.validation.cisco import VerifyCiscoFlash
from ..tasks.deployment.cisco import DistributeCiscoImage, RebootCiscoDevice

@register_strategy
class CiscoCampusStrategy(UpgradeStrategy):
    name = "Cisco IOS-XE Campus Upgrade"

    @classmethod
    def matches(cls, device):
        platform_slug = getattr(device.platform, 'slug', '')
        deployment_mode = device.custom_field_data.get('deployment_mode', '')
        return platform_slug == 'cisco-ios-xe' and deployment_mode == 'campus'

    def get_pipeline(self):
        # We can assemble any tasks we want here.
        return [
            VerifyCiscoFlash(),
            DistributeCiscoImage(),
            RebootCiscoDevice(),
        ]

@register_strategy
class GenericCiscoStrategy(UpgradeStrategy):
    """Fallback for Cisco devices if they don't match Campus/SDWAN specifically."""
    name = "Generic Cisco IOS-XE Upgrade"

    @classmethod
    def matches(cls, device):
        platform_slug = getattr(device.platform, 'slug', '')
        return platform_slug == 'cisco-ios-xe'

    def get_pipeline(self):
        return [
            VerifyCiscoFlash(),
            DistributeCiscoImage(),
            RebootCiscoDevice(), # Maybe different reboot flags for generic?
        ]
