class StrategyRegistry:
    _strategies = []

    @classmethod
    def register(cls, strategy_class):
        cls._strategies.append(strategy_class)
        return strategy_class

    @classmethod
    def get_matching_strategy(cls, device):
        # Return the first matching strategy based on `matches`
        # Complex implementation could score or order them
        for strategy in cls._strategies:
            if strategy.matches(device):
                return strategy()
        return None

def register_strategy(cls):
    return StrategyRegistry.register(cls)

class UpgradeStrategy:
    name = "Base Strategy"

    @classmethod
    def matches(cls, device):
        """Return True if this strategy applies to the device."""
        raise NotImplementedError

    def get_pipeline(self):
        """Return an ordered list of atomic Task instances."""
        raise NotImplementedError
