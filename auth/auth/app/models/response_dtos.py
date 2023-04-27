class PlanResponse:
    def __init__(
        self, price_id: str, price: float, currency: str, recurring_interval: str
    ):
        self.price_id: str = price_id
        self.price: float = price
        self.currency: str = currency
        self.recurring_interval: str = recurring_interval
