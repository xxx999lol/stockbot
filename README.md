# 🛒 Telegram Shop Bot — Bán stock tài nguyên MXH, acc CapCut Pro...

Bot bán hàng tự động trên Telegram: khách xem danh mục → chọn sản phẩm → mua bằng số dư
trong bot → nhận nội dung (tài khoản/key/link...) ngay lập tức. Admin quản lý toàn bộ qua
bảng điều khiển ngay trong Telegram, **không cần code thêm mỗi khi thêm mặt hàng mới**.

## ✨ Tính năng

**Khách hàng:**
- 🛍 Xem danh mục (nhiều danh mục tùy ý: Acc CapCut Pro, Stock MXH, Acc Canva, Key phần mềm...)
- ✅ Mua hàng tự động, trừ số dư, nhận nội dung ngay
- 💳 Nạp tiền: hiển thị thông tin ngân hàng, gửi yêu cầu để admin duyệt
- 👛 Xem số dư, 🧾 xem lịch sử mua hàng

**Admin (gõ `/admin`):**
- ➕ Thêm danh mục mới không giới hạn
- ➕ Thêm sản phẩm vào danh mục (tên, giá, mô tả)
- 📥 Nhập kho: dán danh sách acc/key, mỗi dòng một item — hệ thống tự bán lần lượt
- 📋 Xem danh sách toàn bộ sản phẩm + tồn kho
- 📊 Thống kê: số user, số đơn, doanh thu
- ✅❌ Duyệt/từ chối yêu cầu nạp tiền ngay từ tin nhắn
- `/setbalance <user_id> <so_tien>` — chỉnh số dư thủ công cho khách

## 📁 Cấu trúc

```
telegram_shop_bot/
├── main.py          # Toàn bộ logic bot (user flow + admin panel)
├── database.py       # Lớp thao tác SQLite (users, categories, products, stock, orders, deposits)
├── config.py         # Đọc cấu hình từ .env
├── requirements.txt
├── .env.example
└── shop.db           # File database (tự tạo khi chạy lần đầu)
```

## 🚀 Cài đặt

1. Cài Python 3.10+ rồi cài thư viện:
   ```bash
   pip install -r requirements.txt
   ```

2. Tạo bot với [@BotFather](https://t.me/BotFather) trên Telegram để lấy **BOT_TOKEN**.

3. Lấy **ID Telegram** của bạn (để làm admin) bằng cách nhắn [@userinfobot](https://t.me/userinfobot).

4. Copy `.env.example` thành `.env` rồi điền token + admin ID + thông tin ngân hàng:
   ```bash
   cp .env.example .env
   ```

5. Chạy bot:
   ```bash
   python main.py
   ```

## 🧑‍💼 Hướng dẫn thêm mặt hàng mới (dành cho admin)

1. Nhắn `/admin` trong Telegram → bấm **➕ Thêm danh mục** (ví dụ: "Acc CapCut Pro").
2. Bấm **➕ Thêm sản phẩm** → chọn ID danh mục vừa tạo → nhập tên, giá, mô tả.
3. Bấm **📥 Nhập kho** → chọn ID sản phẩm → dán danh sách acc, **mỗi dòng 1 item**, ví dụ:
   ```
   user1@gmail.com:matkhau1
   user2@gmail.com:matkhau2
   ```
4. Xong! Khách vào 🛍 Cửa hàng sẽ thấy sản phẩm mới ngay, mua là nhận acc tự động.

Muốn thêm loại hàng khác (Canva Pro, Key Windows, Proxy, Gmail...) chỉ cần lặp lại 3 bước
trên — **không cần sửa code**.

## 💰 Luồng nạp tiền

Khách bấm **💳 Nạp tiền** → bot hiện STK ngân hàng → khách chuyển khoản thật ngoài đời →
nhập lại số tiền đã chuyển vào bot → admin nhận thông báo kèm nút ✅ Duyệt / ❌ Từ chối →
duyệt xong số dư khách được cộng tự động.

> Đây là xác nhận thủ công (an toàn, dễ triển khai). Nếu muốn tự động 100% bạn có thể tích
> hợp thêm cổng thanh toán (SePay, PayOS, Casso...) để đọc lịch sử biến động số dư ngân hàng
> và tự cộng tiền — có thể bổ sung sau nếu cần.

## ⚠️ Lưu ý

- Bot dùng SQLite, phù hợp shop nhỏ/vừa. Nếu lượng đơn hàng rất lớn, có thể chuyển sang
  PostgreSQL/MySQL (chỉ cần sửa `database.py`).
- Hãy **backup file `shop.db` định kỳ** vì đây là nơi lưu toàn bộ dữ liệu acc/kho hàng.
- Đừng chia sẻ file `.env` (chứa BOT_TOKEN) cho người khác.
