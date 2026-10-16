from abc import ABC, abstractmethod
import uuid
from typing import Dict, Any


class ShippingProvider(ABC):
    """Giao diện chuẩn cho các đơn vị vận chuyển (Mục 7).
    Cho phép cắm thêm GHNShippingProvider hoặc ViettelPost mà không sửa đổi luồng đặt hàng.
    """

    @abstractmethod
    def quote(self, address: Dict[str, Any], weight: float = 0.5, subtotal: int = 0) -> int:
        """Tính phí vận chuyển dựa trên địa chỉ, trọng lượng và giá trị đơn hàng."""
        pass

    @abstractmethod
    def create_shipment(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Tạo vận đơn và sinh mã vận đơn."""
        pass

    @abstractmethod
    def get_status(self, tracking_code: str) -> Dict[str, Any]:
        """Tra cứu trạng thái hành trình của mã vận đơn."""
        pass


class MockShippingProvider(ShippingProvider):
    """Mô-đun vận chuyển giả lập theo đặc tả Mục 7:
    - Phí nội thành TP.HCM: 25.000 VND
    - Tỉnh thành khác: 40.000 VND
    - Miễn phí vận chuyển khi giá trị đơn hàng >= 500.000 VND
    """

    def __init__(self, freeship_threshold: int = 500000):
        self.freeship_threshold = freeship_threshold
        self.hcm_fee = 25000
        self.other_province_fee = 40000

    def quote(self, address: Dict[str, Any], weight: float = 0.5, subtotal: int = 0) -> int:
        if subtotal >= self.freeship_threshold and subtotal > 0:
            return 0

        city = str(address.get("city_province", "")).lower()
        if any(hcm in city for hcm in ["hồ chí minh", "tp.hcm", "hcm", "tp hcm", "saigon", "sài gòn"]):
            return self.hcm_fee
        return self.other_province_fee

    def create_shipment(self, order: Dict[str, Any]) -> Dict[str, Any]:
        code = f"DT-SHIP-{uuid.uuid4().hex[:8].upper()}"
        return {
            "tracking_code": code,
            "carrier": "MockShipping",
            "fee": order.get("shipping_fee", self.other_province_fee),
            "status": "ready_to_ship",
            "estimated_delivery_days": 2 if order.get("shipping_fee") == self.hcm_fee else 4,
        }

    def get_status(self, tracking_code: str) -> Dict[str, Any]:
        return {
            "tracking_code": tracking_code,
            "carrier": "MockShipping",
            "status": "in_transit",
            "description": "Đơn hàng đang được vận chuyển bởi đối tác giao hàng.",
        }


# Default provider instance
shipping_service = MockShippingProvider()
