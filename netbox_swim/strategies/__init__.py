from .base import StrategyRegistry, UpgradeStrategy, register_strategy

# Import strategies to ensure they are registered
from . import cisco
from . import palo_alto

__all__ = [
    'StrategyRegistry',
    'UpgradeStrategy',
    'register_strategy',
]
