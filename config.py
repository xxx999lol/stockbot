import os
from dotenv import load_dotenv

load_dotenv()

# Token bot lấy từ @BotFather
BOT_TOKEN = os.getenv("BOT_TOKEN", "8920810875:AAGtwsy5pGC-wEkIQhtHIkgR7d0GB02MMv0")

# Danh sách ID Telegram của admin (cách nhau bởi dấu phẩy trong .env)
# Ví dụ trong .env: ADMIN_IDS=123456789,987654321
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "7752271438").split(",") if x.strip()]

# Đường dẫn file database SQLite
DB_PATH = os.getenv("DB_PATH", "shop.db")

# Thông tin ngân hàng hiển thị khi khách nạp tiền (chỉnh lại theo tài khoản của bạn)
BANK_INFO = os.getenv(
    "BANK_INFO",
    "🏦 Ngân hàng: MB Bank\n"
    "💳 Số TK: 0000 1234 5678\n"
    "👤 Chủ TK: NGUYEN VAN A\n"
    "📝 Nội dung CK: NAP <ID_TELEGRAM_CUA_BAN>",
)

# Số lượng sản phẩm hiển thị trên mỗi trang danh sách
PAGE_SIZE = 8
