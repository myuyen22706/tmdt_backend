class ShippingHelper:
    """Helper tính phí vận chuyển và sinh mã tracking (GHTK / GHN / Viettel Post mô phỏng)."""

    @staticmethod
    def calculate_fee(city_province: str, subtotal: float) -> float:
        if subtotal >= 500000:
            return 0  # Freeship cho đơn từ 500k
        if any(h in city_province.lower() for h in ["hồ chí minh", "hcm", "sài gòn"]):
            return 22000
        return 35000
