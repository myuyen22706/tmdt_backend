from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user_token
from app.core.responses import APIResponse
from app.modules.cart.schemas import (
    CartItem,
    CartItemAdd,
    CartItemUpdate,
    CartMergeRequest,
    CartResponse,
)

router = APIRouter(prefix="/cart", tags=["Cart & Embroidery (F06, F07)"])

EMBROIDERY_FEE_DEFAULT = settings.EMBROIDERY_FEE  # 30.000 VND / sản phẩm thêu (Mục 2 & docs/gia-dinh.md)


def _get_cart_filter(token_payload: Optional[dict], session_id: Optional[str]) -> dict:
    if token_payload and token_payload.get("sub"):
        return {"user_id": token_payload.get("sub")}
    if session_id:
        return {"session_id": session_id}
    return {"session_id": "guest_default"}


def _match_line(item: dict, sku: str, embroidery_name: Optional[str]) -> bool:
    """Xác định dòng hàng theo SKU; nếu truyền tên thêu thì khớp chính xác dòng thêu đó."""
    if item.get("sku") != sku:
        return False
    if embroidery_name is None:
        return True
    return (item.get("embroidery_name") or "") == embroidery_name


def _calculate_cart_totals(items: list[dict]) -> CartResponse:
    cart_items = []
    total_items = 0
    subtotal = 0
    embroidery_total = 0
    has_embroidery = False

    for it in items:
        qty = it.get("quantity", 1)
        price = int(it.get("price", 0))
        is_emb = it.get("is_embroidered", False)
        emb_fee = int(it.get("embroidery_fee", 0)) if is_emb else 0

        if is_emb:
            has_embroidery = True
            embroidery_total += emb_fee * qty

        subtotal += price * qty
        total_items += qty

        cart_items.append(
            CartItem(
                product_id=it.get("product_id"),
                sku=it.get("sku"),
                product_name=it.get("product_name"),
                size=it.get("size"),
                color=it.get("color", "Trắng"),
                price=price,
                quantity=qty,
                thumbnail=it.get("thumbnail"),
                is_embroidered=is_emb,
                embroidery_name=it.get("embroidery_name"),
                embroidery_fee=emb_fee,
            )
        )

    # Phí ship tham khảo trong giỏ: Miễn phí nếu subtotal >= 500.000 VND, ngược lại 30.000 VND
    shipping_fee = 0 if subtotal >= 500000 or subtotal == 0 else 30000
    grand_total = subtotal + embroidery_total + shipping_fee

    return CartResponse(
        items=cart_items,
        total_items=total_items,
        subtotal=subtotal,
        embroidery_total=embroidery_total,
        has_embroidery=has_embroidery,
        shipping_fee=shipping_fee,
        grand_total=grand_total,
    )


@router.get("", response_model=APIResponse[CartResponse])
async def get_cart(
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F06: Lấy danh sách sản phẩm trong giỏ hàng (theo user_id hoặc session_id)."""
    carts_col = db["carts"]
    filter_query = _get_cart_filter(token_payload, x_session_id)
    cart = await carts_col.find_one(filter_query)

    items = cart.get("items", []) if cart else []
    return APIResponse(
        success=True,
        message="Lấy giỏ hàng thành công",
        data=_calculate_cart_totals(items),
    )


@router.post("/items", response_model=APIResponse[CartResponse])
async def add_to_cart(
    item_in: CartItemAdd,
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F06 & F07: Thêm sản phẩm vào giỏ hàng.
    - Kiểm tra tồn kho tại thời điểm thêm.
    - Tùy chọn thêu tên võ sinh (tối đa 20 ký tự, cộng phí thêu 30.000 VND).
    """
    products_col = db["products"]
    carts_col = db["carts"]

    # 1. Tìm sản phẩm và biến thể SKU
    product = await products_col.find_one({"id": item_in.product_id})
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy sản phẩm",
        )

    matched_variant = None
    for v in product.get("variants", []):
        if v.get("sku") == item_in.sku:
            matched_variant = v
            break

    if not matched_variant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Biến thể SKU '{item_in.sku}' không tồn tại",
        )

    # 2. Kiểm tra tồn kho (F06)
    stock = matched_variant.get("stock", 0)
    if stock < item_in.quantity:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Số lượng tồn kho không đủ (chỉ còn {stock} sản phẩm)",
        )

    # 3. Kiểm tra điều kiện thêu tên (F07)
    embroidery_fee = 0
    embroidery_name = None
    if item_in.is_embroidered:
        if not product.get("is_customizable", False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Sản phẩm này không hỗ trợ dịch vụ thêu tên riêng",
            )
        if not item_in.embroidery_name or len(item_in.embroidery_name.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Vui lòng nhập tên võ sinh cần thêu",
            )
        if len(item_in.embroidery_name.strip()) > 20:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tên thêu tối đa 20 ký tự (F07)",
            )
        embroidery_name = item_in.embroidery_name.strip()
        embroidery_fee = EMBROIDERY_FEE_DEFAULT

    # 4. Thêm hoặc cập nhật trong giỏ hàng
    filter_query = _get_cart_filter(token_payload, x_session_id)
    cart = await carts_col.find_one(filter_query)

    items = cart.get("items", []) if cart else []

    # Kiểm tra xem sản phẩm + SKU + tên thêu đã có trong giỏ chưa
    existing_item = None
    for it in items:
        if it.get("sku") == item_in.sku and it.get("embroidery_name") == embroidery_name:
            existing_item = it
            break

    same_sku_qty = sum(it.get("quantity", 0) for it in items if it.get("sku") == item_in.sku)
    if same_sku_qty + item_in.quantity > stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Tổng số lượng trong giỏ ({same_sku_qty + item_in.quantity}) vượt quá tồn kho hiện có ({stock})",
        )

    if existing_item:
        existing_item["quantity"] = existing_item.get("quantity", 1) + item_in.quantity
    else:
        items.append({
            "product_id": product.get("id"),
            "sku": item_in.sku,
            "product_name": product.get("name"),
            "size": matched_variant.get("size"),
            "color": matched_variant.get("color", "Trắng"),
            "price": int(matched_variant.get("price", product.get("price", 0))),
            "quantity": item_in.quantity,
            "thumbnail": product.get("thumbnail"),
            "is_embroidered": item_in.is_embroidered,
            "embroidery_name": embroidery_name,
            "embroidery_fee": embroidery_fee,
        })

    now = datetime.now(timezone.utc)
    await carts_col.update_one(
        filter_query,
        {"$set": {"items": items, "updated_at": now}},
        upsert=True,
    )

    return APIResponse(
        success=True,
        message="Thêm vào giỏ hàng thành công",
        data=_calculate_cart_totals(items),
    )


@router.put("/items/{sku}", response_model=APIResponse[CartResponse])
async def update_cart_item_quantity(
    sku: str,
    payload: CartItemUpdate,
    embroidery_name: Optional[str] = Query(None, description="Tên thêu của dòng hàng cần sửa (nếu có)"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F06: Cập nhật số lượng của dòng hàng trong giỏ."""
    products_col = db["products"]
    carts_col = db["carts"]

    # Kiểm tra tồn kho của SKU
    product = await products_col.find_one({"variants.sku": sku})
    if not product:
        raise HTTPException(status_code=404, detail="Sản phẩm không tồn tại")

    stock = 0
    for v in product.get("variants", []):
        if v.get("sku") == sku:
            stock = v.get("stock", 0)
            break

    if payload.quantity > stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Số lượng yêu cầu ({payload.quantity}) vượt quá tồn kho hiện có ({stock})",
        )

    filter_query = _get_cart_filter(token_payload, x_session_id)
    cart = await carts_col.find_one(filter_query)
    if not cart:
        raise HTTPException(status_code=404, detail="Giỏ hàng trống")

    items = cart.get("items", [])
    other_lines_qty = sum(
        it.get("quantity", 0) for it in items
        if it.get("sku") == sku and not _match_line(it, sku, embroidery_name)
    )
    if payload.quantity + other_lines_qty > stock:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Số lượng yêu cầu ({payload.quantity + other_lines_qty}) vượt quá tồn kho hiện có ({stock})",
        )

    updated = False
    for it in items:
        if _match_line(it, sku, embroidery_name):
            it["quantity"] = payload.quantity
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail="Không tìm thấy mặt hàng trong giỏ")

    await carts_col.update_one(
        filter_query,
        {"$set": {"items": items, "updated_at": datetime.now(timezone.utc)}},
    )

    return APIResponse(
        success=True,
        message="Cập nhật số lượng thành công",
        data=_calculate_cart_totals(items),
    )


@router.delete("/items/{sku}", response_model=APIResponse[CartResponse])
async def remove_cart_item(
    sku: str,
    embroidery_name: Optional[str] = Query(None, description="Tên thêu của dòng hàng cần xóa (nếu có)"),
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F06: Xóa dòng hàng khỏi giỏ hàng."""
    carts_col = db["carts"]
    filter_query = _get_cart_filter(token_payload, x_session_id)
    cart = await carts_col.find_one(filter_query)
    if not cart:
        return APIResponse(success=True, message="Giỏ hàng trống", data=_calculate_cart_totals([]))

    items = [it for it in cart.get("items", []) if not _match_line(it, sku, embroidery_name)]
    await carts_col.update_one(
        filter_query,
        {"$set": {"items": items, "updated_at": datetime.now(timezone.utc)}},
    )

    return APIResponse(
        success=True,
        message="Đã xóa sản phẩm khỏi giỏ hàng",
        data=_calculate_cart_totals(items),
    )


@router.delete("", response_model=APIResponse[dict])
async def clear_cart(
    x_session_id: Optional[str] = Header(None, alias="X-Session-ID"),
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """Xóa trắng toàn bộ giỏ hàng."""
    carts_col = db["carts"]
    filter_query = _get_cart_filter(token_payload, x_session_id)
    await carts_col.delete_one(filter_query)
    return APIResponse(success=True, message="Đã làm sạch giỏ hàng", data={"cleared": True})


@router.post("/merge", response_model=APIResponse[CartResponse])
async def merge_cart(
    payload: CartMergeRequest,
    token_payload: Optional[dict] = Depends(get_current_user_token),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """F06: Gộp giỏ hàng của khách vãng lai (session_id) vào tài khoản sau khi đăng nhập."""
    if not token_payload or not token_payload.get("sub"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Cần đăng nhập để gộp giỏ hàng vào tài khoản",
        )

    user_id = token_payload.get("sub")
    carts_col = db["carts"]

    guest_cart = await carts_col.find_one({"session_id": payload.session_id})
    user_cart = await carts_col.find_one({"user_id": user_id})

    user_items = user_cart.get("items", []) if user_cart else []
    guest_items = guest_cart.get("items", []) if guest_cart else []

    # Gộp items
    for g_it in guest_items:
        found = False
        for u_it in user_items:
            if u_it.get("sku") == g_it.get("sku") and u_it.get("embroidery_name") == g_it.get("embroidery_name"):
                u_it["quantity"] += g_it.get("quantity", 1)
                found = True
                break
        if not found:
            user_items.append(g_it)

    now = datetime.now(timezone.utc)
    await carts_col.update_one(
        {"user_id": user_id},
        {"$set": {"items": user_items, "updated_at": now}},
        upsert=True,
    )

    # Xóa giỏ khách vãng lai sau khi đã gộp
    if guest_cart:
        await carts_col.delete_one({"session_id": payload.session_id})

    return APIResponse(
        success=True,
        message="Gộp giỏ hàng thành công",
        data=_calculate_cart_totals(user_items),
    )
