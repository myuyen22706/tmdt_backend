class VietQRHelper:
    """Helper để sinh mã VietQR chuẩn NAPAS 247."""

    @staticmethod
    def generate_qr_url(bank_bin: str, account_no: str, amount: int, memo: str) -> str:
        # Sử dụng API VietQR chuẩn (compact2 template)
        return f"https://img.vietqr.io/image/{bank_bin}-{account_no}-compact2.png?amount={amount}&addInfo={memo}"
