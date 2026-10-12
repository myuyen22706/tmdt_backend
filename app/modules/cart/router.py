from fastapi import APIRouter
from app.core.responses import APIResponse
from app.modules.cart.schemas import CartItem, CartItemAdd, CartResponse
from app.modules.products.service import ProductService

router = APIRouter(prefix="/cart", tags=["Cart & Mini-Cart"])

# In-memory mock session cart for demo purposes
_demo_cart: list[CartItem] = [
    CartItem(
        product_id="prod-vovinam-standard",
        product_name="Võ Phục Vovinam Tiêu Chuẩn Việt Võ Đạo",
        price=240000,
        size="Size 4 (M)",
        quantity=1,
        thumbnail="https://placehold.co/400x400?text=Vovinam",
        is_embroidered=True,
        embroidered_text="Nguyễn Văn A",
        embroidery_fee=20000,
    )
]


def _calculate_totals(items: list[CartItem]) -> CartResponse:
    subtotal = sum((item.price + item.embroidery_fee) * item.quantity for item in items)
    shipping_fee = 0 if subtotal >= 500000 or subtotal == 0 else 30000
    grand_total = subtotal + shipping_fee
    total_items = sum(item.quantity for item in items)
    return CartResponse(
        items=items,
        total_items=total_items,
        subtotal=subtotal,
        shipping_fee=shipping_fee,
        discount_amount=0,
        grand_total=grand_total,
    )


@router.get("", response_model=APIResponse[CartResponse])
async def get_cart():
    """Lấy danh sách sản phẩm trong giỏ hàng và tổng tiền."""
    return APIResponse(
        success=True,
        message="Lấy giỏ hàng thành công",
        data=_calculate_totals(_demo_cart),
    )


@router.post("/items", response_model=APIResponse[CartResponse])
async def add_to_cart(item: CartItemAdd):
    """Thêm sản phẩm vào giỏ hàng (kèm size và tùy chọn thêu tên)."""
    prod = ProductService.get_by_id_or_slug(item.product_id)
    product_name = prod["name"] if prod else "Võ phục"
    price = prod["price"] if prod else 250000
    thumbnail = prod["thumbnail"] if prod else ""

    new_cart_item = CartItem(
        product_id=item.product_id,
        product_name=product_name,
        price=price,
        size=item.size,
        quantity=item.quantity,
        thumbnail=thumbnail,
        is_embroidered=item.is_embroidered,
        embroidered_text=item.embroidered_text,
        embroidery_fee=20000 if item.is_embroidered else 0,
    )
    _demo_cart.append(new_cart_item)
    return APIResponse(
        success=True,
        message="Thêm vào giỏ hàng thành công",
        data=_calculate_totals(_demo_cart),
    )


@router.delete("/items/{index}", response_model=APIResponse[CartResponse])
async def remove_from_cart(index: int):
    """Xóa sản phẩm khỏi giỏ hàng theo vị trí."""
    if 0 <= index < len(_demo_cart):
        _demo_cart.pop(index)
    return APIResponse(
        success=True,
        message="Cập nhật giỏ hàng thành công",
        data=_calculate_totals(_demo_cart),
    )
