"""Gửi email giao dịch qua Resend (https://resend.com/docs/api-reference/emails/send-email).

Mọi hàm ở đây không bao giờ ném lỗi ra ngoài: email chỉ là thông báo phụ, không được làm hỏng
việc đặt hàng hay đặt lại mật khẩu. Gọi qua BackgroundTasks để không làm chậm phản hồi API.
"""
import logging
from html import escape
from typing import Any, Dict

import httpx

from app.core.config import settings

logger = logging.getLogger("vo_ecommerce.mail")

RESEND_ENDPOINT = "https://api.resend.com/emails"


# Domain dành riêng (RFC 2606/6761) của tài khoản mẫu: không bao giờ nhận được thư,
# gửi tới đó chỉ tạo bounce làm giảm uy tín domain gửi trên Resend.
RESERVED_DOMAINS = ("example.com", "example.org", "example.net")
RESERVED_TLDS = (".test", ".example", ".invalid", ".localhost")


def mail_enabled() -> bool:
    return bool(settings.RESEND_API_KEY)


def is_deliverable(address: str) -> bool:
    domain = address.rsplit("@", 1)[-1].strip().lower()
    return "@" in address and domain not in RESERVED_DOMAINS and not domain.endswith(RESERVED_TLDS)


async def send_email(to: str, subject: str, html: str) -> bool:
    """Gửi một email HTML. Trả về True nếu Resend nhận yêu cầu."""
    if not mail_enabled():
        logger.info("Chưa cấu hình RESEND_API_KEY, bỏ qua email '%s'", subject)
        return False
    if not is_deliverable(to):
        logger.info("Bỏ qua email '%s' tới địa chỉ mẫu không nhận thư: %s", subject, to)
        return False
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.post(
                RESEND_ENDPOINT,
                headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
                json={"from": settings.MAIL_FROM, "to": [to], "subject": subject, "html": html},
            )
        if res.status_code >= 400:
            logger.warning("Resend từ chối email '%s' (HTTP %s): %s", subject, res.status_code, res.text[:300])
            return False
        return True
    except Exception as e:  # mạng lỗi, timeout...
        logger.warning("Không gửi được email '%s': %s", subject, e)
        return False


def _vnd(amount: Any) -> str:
    return f"{int(amount or 0):,}₫".replace(",", ".")


def _layout(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="vi"><body style="margin:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;color:#17171a">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="padding:24px 12px">
<tr><td align="center">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:12px;overflow:hidden">
<tr><td style="background:#15213d;color:#ffffff;padding:20px 28px;font-size:22px;font-weight:bold;letter-spacing:2px">VÕ</td></tr>
<tr><td style="padding:28px">
<h1 style="margin:0 0 16px;font-size:20px">{title}</h1>
{body}
</td></tr>
<tr><td style="padding:16px 28px;background:#fafafa;color:#71717a;font-size:12px">
Email tự động từ cửa hàng VÕ, vui lòng không trả lời email này.
</td></tr>
</table></td></tr></table></body></html>"""


def _button(href: str, label: str) -> str:
    return (
        f'<a href="{escape(href)}" style="display:inline-block;background:#c8322b;color:#ffffff;'
        f'text-decoration:none;padding:12px 22px;border-radius:8px;font-weight:bold">{escape(label)}</a>'
    )


def render_order_confirmation(order: Dict[str, Any]) -> str:
    """Email xác nhận đơn hàng. Mọi giá trị do khách nhập đều được escape."""
    rows = []
    for it in order.get("items", []):
        extra = f"<br><span style='color:#71717a;font-size:12px'>Thêu tên: {escape(it.get('embroidery_name') or '')}</span>" if it.get("is_embroidered") else ""
        rows.append(
            "<tr>"
            f"<td style='padding:8px 0;border-bottom:1px solid #eee'>{escape(it.get('product_name', ''))}"
            f"<br><span style='color:#71717a;font-size:12px'>{escape(it.get('size', ''))} · SL {int(it.get('quantity', 1))}</span>{extra}</td>"
            f"<td align='right' style='padding:8px 0;border-bottom:1px solid #eee;white-space:nowrap'>{_vnd(int(it.get('price', 0)) * int(it.get('quantity', 1)))}</td>"
            "</tr>"
        )

    def line(label: str, value: Any, bold: bool = False) -> str:
        w = "bold" if bold else "normal"
        return f"<tr><td style='padding:4px 0;font-weight:{w}'>{label}</td><td align='right' style='padding:4px 0;font-weight:{w}'>{value}</td></tr>"

    totals = line("Tạm tính", _vnd(order.get("subtotal")))
    if order.get("embroidery_total"):
        totals += line("Phí thêu tên", _vnd(order.get("embroidery_total")))
    totals += line("Phí giao hàng", _vnd(order.get("shipping_fee")))
    if order.get("discount_amount"):
        totals += line(f"Giảm giá ({escape(order.get('voucher_code') or '')})", "-" + _vnd(order.get("discount_amount")))
    totals += line("Tổng cộng", _vnd(order.get("total_amount")), bold=True)

    addr = order.get("shipping_address") or {}
    addr_str = ", ".join(str(addr.get(k)).strip() for k in ("street_address", "ward", "district", "city_province") if addr.get(k))
    method = "Thanh toán khi nhận hàng (COD)" if order.get("payment_method") == "COD" else "Ví MoMo"
    code = order.get("order_code", "")
    order_url = f"{settings.FRONTEND_URL.rstrip('/')}/orders/{code}"

    body = f"""
<p style="margin:0 0 16px;line-height:1.6">Chào {escape(order.get('customer_name') or 'bạn')}, cảm ơn bạn đã đặt hàng tại VÕ.
Mã đơn của bạn là <b>{escape(code)}</b>.</p>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px">{''.join(rows)}</table>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;margin-top:12px">{totals}</table>
<p style="margin:20px 0 4px;font-size:14px"><b>Giao đến:</b> {escape(addr.get('recipient_name', ''))} · {escape(addr.get('phone', ''))}<br>{escape(addr_str)}</p>
<p style="margin:0 0 24px;font-size:14px"><b>Thanh toán:</b> {method}</p>
{_button(order_url, "Xem đơn hàng")}
<p style="margin:16px 0 0;color:#71717a;font-size:12px">Khi xem đơn, nhập số điện thoại đặt hàng nếu bạn chưa đăng nhập.</p>
"""
    return _layout("Đặt hàng thành công", body)


def render_password_reset(full_name: str, reset_link: str, expire_minutes: int) -> str:
    body = f"""
<p style="margin:0 0 16px;line-height:1.6">Chào {escape(full_name or 'bạn')}, chúng tôi nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn.</p>
<p style="margin:0 0 24px">{_button(reset_link, "Đặt lại mật khẩu")}</p>
<p style="margin:0;color:#71717a;font-size:13px;line-height:1.6">Liên kết có hiệu lực trong {int(expire_minutes)} phút và chỉ dùng được một lần.
Nếu bạn không yêu cầu, hãy bỏ qua email này, mật khẩu của bạn vẫn giữ nguyên.</p>
"""
    return _layout("Đặt lại mật khẩu", body)
