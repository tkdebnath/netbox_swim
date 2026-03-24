from .base import UpgradeStrategy, register_strategy
from ..tasks.deployment.palo_alto import UploadPanosImage, InstallPanosImage

@register_strategy
class PaloAltoStrategy(UpgradeStrategy):
    name = "Palo Alto Networks Upgrade"

    @classmethod
    def matches(cls, device):
        platform_slug = getattr(device.platform, 'slug', '')
        # Could also filter on device manufacturer if needed
        return 'pan-os' in platform_slug or 'paloalto' in platform_slug

    def get_pipeline(self):
        return [
            UploadPanosImage(),
            InstallPanosImage(),
        ]
