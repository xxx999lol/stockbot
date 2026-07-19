import logging

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

import config
import database as db

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---------------- Conversation states ----------------
(
    ADD_CAT_NAME,
    ADD_PROD_CAT,
    ADD_PROD_NAME,
    ADD_PROD_PRICE,
    ADD_PROD_DESC,
    ADD_STOCK_PROD,
    ADD_STOCK_CONTENT,
    DEPOSIT_AMOUNT,
) = range(8)

MAIN_MENU_KB = ReplyKeyboardMarkup(
    [
        ["🛍 Cửa hàng", "👛 Số dư"],
        ["💳 Nạp tiền", "🧾 Lịch sử mua hàng"],
        ["☎️ Hỗ trợ"],
    ],
    resize_keyboard=True,
)


def is_admin(user_id: int) -> bool:
    return user_id in config.ADMIN_IDS


def fmt_money(amount: int) -> str:
    return f"{amount:,}đ".replace(",", ".")


# =========================================================
#                       USER FLOW
# =========================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db.get_or_create_user(user.id, user.username)
    text = (
        f"👋 Xin chào {user.first_name}!\n\n"
        "Chào mừng đến <b>Shop Bot</b> 🛒\n"
        "Nơi cung cấp tài nguyên MXH, acc CapCut Pro và nhiều mặt hàng số khác.\n\n"
        "Chọn một mục bên dưới để bắt đầu 👇"
    )
    await update.message.reply_text(text, reply_markup=MAIN_MENU_KB, parse_mode=ParseMode.HTML)


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bal = db.get_balance(update.effective_user.id)
    await update.message.reply_text(f"👛 Số dư hiện tại của bạn: <b>{fmt_money(bal)}</b>", parse_mode=ParseMode.HTML)


async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    orders = db.list_orders(update.effective_user.id)
    if not orders:
        await update.message.reply_text("📭 Bạn chưa mua đơn hàng nào.")
        return
    lines = ["🧾 <b>Lịch sử mua hàng gần đây:</b>\n"]
    for o in orders:
        lines.append(f"#{o['id']} • {o['product_name']} • {fmt_money(o['price'])} • {o['created_at']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)


async def show_support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("☎️ Mọi thắc mắc vui lòng liên hệ admin: @your_admin_username")


def categories_keyboard():
    cats = db.list_categories()
    if not cats:
        return None
    rows = [
        [InlineKeyboardButton(f"{c['emoji']} {c['name']}", callback_data=f"cat:{c['id']}")]
        for c in cats
    ]
    return InlineKeyboardMarkup(rows)


async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = categories_keyboard()
    if kb is None:
        await update.message.reply_text("🚧 Hiện chưa có danh mục sản phẩm nào. Vui lòng quay lại sau.")
        return
    await update.message.reply_text("🛍 <b>Danh mục sản phẩm:</b>", reply_markup=kb, parse_mode=ParseMode.HTML)


async def cb_show_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cat_id = int(query.data.split(":")[1])
    cat = db.get_category(cat_id)
    products = db.list_products(category_id=cat_id)
    if not products:
        await query.edit_message_text(
            f"{cat['emoji']} <b>{cat['name']}</b>\n\n🚧 Danh mục này hiện chưa có sản phẩm.",
            parse_mode=ParseMode.HTML,
        )
        return
    rows = []
    for p in products:
        stock_count = db.count_available_stock(p["id"])
        label = f"{p['name']} — {fmt_money(p['price'])} (còn {stock_count})"
        rows.append([InlineKeyboardButton(label, callback_data=f"prod:{p['id']}")])
    rows.append([InlineKeyboardButton("⬅️ Quay lại danh mục", callback_data="menu:shop")])
    await query.edit_message_text(
        f"{cat['emoji']} <b>{cat['name']}</b>\nChọn sản phẩm bên dưới:",
        reply_markup=InlineKeyboardMarkup(rows),
        parse_mode=ParseMode.HTML,
    )


async def cb_show_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    prod_id = int(query.data.split(":")[1])
    p = db.get_product(prod_id)
    if not p:
        await query.edit_message_text("❌ Sản phẩm không tồn tại.")
        return
    stock_count = db.count_available_stock(prod_id)
    text = (
        f"📦 <b>{p['name']}</b>\n"
        f"💰 Giá: {fmt_money(p['price'])}\n"
        f"📊 Tồn kho: {stock_count}\n\n"
        f"{p['description'] or ''}"
    )
    rows = [
        [InlineKeyboardButton("✅ Mua ngay", callback_data=f"buy:{p['id']}")],
        [InlineKeyboardButton("⬅️ Quay lại", callback_data=f"cat:{p['category_id']}")],
    ]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(rows), parse_mode=ParseMode.HTML)


async def cb_buy_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    prod_id = int(query.data.split(":")[1])
    p = db.get_product(prod_id)
    if not p or not p["active"]:
        await query.answer("❌ Sản phẩm không khả dụng.", show_alert=True)
        return

    balance = db.get_balance(user_id)
    if balance < p["price"]:
        await query.answer(
            f"❌ Số dư không đủ. Cần {fmt_money(p['price'])}, bạn có {fmt_money(balance)}.",
            show_alert=True,
        )
        return

    item = db.take_one_stock(prod_id, user_id)
    if item is None:
        await query.answer("😥 Rất tiếc, sản phẩm vừa hết hàng.", show_alert=True)
        return

    db.change_balance(user_id, -p["price"])
    db.create_order(user_id, prod_id, p["name"], p["price"], item["id"])

    await query.answer("✅ Mua thành công! Kiểm tra tin nhắn riêng.", show_alert=True)
    await context.bot.send_message(
        chat_id=user_id,
        text=(
            f"✅ <b>Mua hàng thành công!</b>\n"
            f"📦 Sản phẩm: {p['name']}\n"
            f"💰 Giá: {fmt_money(p['price'])}\n\n"
            f"🔑 <b>Nội dung:</b>\n<code>{item['content']}</code>\n\n"
            f"👛 Số dư còn lại: {fmt_money(db.get_balance(user_id))}"
        ),
        parse_mode=ParseMode.HTML,
    )


async def cb_back_to_shop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    kb = categories_keyboard()
    await query.edit_message_text("🛍 <b>Danh mục sản phẩm:</b>", reply_markup=kb, parse_mode=ParseMode.HTML)


# ---------------- Deposit (nạp tiền) flow ----------------
async def deposit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"💳 <b>Thông tin nạp tiền:</b>\n\n{config.BANK_INFO}\n\n"
        "Sau khi chuyển khoản, hãy nhập <b>số tiền bạn đã chuyển</b> (chỉ nhập số) để gửi yêu cầu duyệt cho admin.\n"
        "Gõ /cancel để huỷ.",
        parse_mode=ParseMode.HTML,
    )
    return DEPOSIT_AMOUNT


async def deposit_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(".", "").replace(",", "")
    if not text.isdigit() or int(text) <= 0:
        await update.message.reply_text("⚠️ Vui lòng nhập một số tiền hợp lệ (ví dụ: 50000).")
        return DEPOSIT_AMOUNT

    amount = int(text)
    user = update.effective_user
    deposit_id = db.create_deposit(user.id, amount)

    await update.message.reply_text(
        f"⏳ Yêu cầu nạp <b>{fmt_money(amount)}</b> đã được gửi. Vui lòng chờ admin duyệt.",
        parse_mode=ParseMode.HTML,
        reply_markup=MAIN_MENU_KB,
    )

    admin_kb = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Duyệt", callback_data=f"dep:approve:{deposit_id}"),
                InlineKeyboardButton("❌ Từ chối", callback_data=f"dep:reject:{deposit_id}"),
            ]
        ]
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=(
                    f"💳 <b>Yêu cầu nạp tiền mới #{deposit_id}</b>\n"
                    f"👤 User: {user.id} (@{user.username or 'no_username'})\n"
                    f"💰 Số tiền: {fmt_money(amount)}"
                ),
                reply_markup=admin_kb,
                parse_mode=ParseMode.HTML,
            )
        except Exception as e:
            logger.warning("Could not notify admin %s: %s", admin_id, e)

    return ConversationHandler.END


async def cb_deposit_decision(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not is_admin(query.from_user.id):
        await query.answer("⛔ Bạn không có quyền.", show_alert=True)
        return
    _, action, dep_id_str = query.data.split(":")
    dep_id = int(dep_id_str)
    dep = db.get_deposit(dep_id)
    if not dep or dep["status"] != "pending":
        await query.answer("Yêu cầu này đã được xử lý rồi.", show_alert=True)
        return

    if action == "approve":
        db.change_balance(dep["user_id"], dep["amount"])
        db.resolve_deposit(dep_id, "approved")
        await query.edit_message_text(query.message.text_html + "\n\n✅ <b>Đã duyệt</b>", parse_mode=ParseMode.HTML)
        await context.bot.send_message(
            chat_id=dep["user_id"],
            text=f"✅ Yêu cầu nạp {fmt_money(dep['amount'])} đã được duyệt. Số dư mới: {fmt_money(db.get_balance(dep['user_id']))}",
        )
    else:
        db.resolve_deposit(dep_id, "rejected")
        await query.edit_message_text(query.message.text_html + "\n\n❌ <b>Đã từ chối</b>", parse_mode=ParseMode.HTML)
        await context.bot.send_message(
            chat_id=dep["user_id"],
            text=f"❌ Yêu cầu nạp {fmt_money(dep['amount'])} đã bị từ chối. Liên hệ admin nếu có nhầm lẫn.",
        )
    await query.answer()


# =========================================================
#                       ADMIN PANEL
# =========================================================
def admin_kb():
    rows = [
        [InlineKeyboardButton("➕ Thêm danh mục", callback_data="adm:addcat")],
        [InlineKeyboardButton("➕ Thêm sản phẩm", callback_data="adm:addprod")],
        [InlineKeyboardButton("📥 Nhập kho (stock)", callback_data="adm:addstock")],
        [InlineKeyboardButton("📋 Danh sách sản phẩm", callback_data="adm:listprod")],
        [InlineKeyboardButton("📊 Thống kê", callback_data="adm:stats")],
    ]
    return InlineKeyboardMarkup(rows)


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Bạn không có quyền truy cập.")
        return
    await update.message.reply_text("🛠 <b>Bảng điều khiển Admin</b>", reply_markup=admin_kb(), parse_mode=ParseMode.HTML)


async def cb_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    text = (
        f"📊 <b>Thống kê shop</b>\n\n"
        f"👥 Người dùng: {db.count_users()}\n"
        f"🧾 Đơn hàng đã bán: {db.count_orders()}\n"
        f"💰 Doanh thu: {fmt_money(db.total_revenue())}\n"
        f"📦 Danh mục: {len(db.list_categories())}"
    )
    await query.edit_message_text(text, reply_markup=admin_kb(), parse_mode=ParseMode.HTML)


async def cb_admin_listprod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cats = db.list_categories()
    if not cats:
        await query.edit_message_text("Chưa có danh mục nào.", reply_markup=admin_kb())
        return
    lines = ["📋 <b>Danh sách sản phẩm:</b>\n"]
    for c in cats:
        lines.append(f"\n{c['emoji']} <b>{c['name']}</b> (id={c['id']})")
        for p in db.list_products(category_id=c["id"], active_only=False):
            stock_count = db.count_available_stock(p["id"])
            status = "🟢" if p["active"] else "🔴"
            lines.append(f"  {status} [{p['id']}] {p['name']} — {fmt_money(p['price'])} (còn {stock_count})")
    await query.edit_message_text("\n".join(lines), reply_markup=admin_kb(), parse_mode=ParseMode.HTML)


# ---------------- Admin: add category ----------------
async def admin_addcat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✏️ Nhập tên danh mục mới (ví dụ: <i>Acc CapCut Pro</i>):", parse_mode=ParseMode.HTML)
    return ADD_CAT_NAME


async def admin_addcat_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    try:
        db.add_category(name)
        await update.message.reply_text(f"✅ Đã thêm danh mục: {name}", reply_markup=admin_kb())
    except Exception as e:
        await update.message.reply_text(f"❌ Lỗi: {e}")
    return ConversationHandler.END


# ---------------- Admin: add product ----------------
async def admin_addprod_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cats = db.list_categories()
    if not cats:
        await query.edit_message_text("⚠️ Chưa có danh mục nào. Hãy thêm danh mục trước.", reply_markup=admin_kb())
        return ConversationHandler.END
    lines = ["✏️ Nhập <b>ID danh mục</b> cho sản phẩm mới:\n"]
    for c in cats:
        lines.append(f"[{c['id']}] {c['emoji']} {c['name']}")
    await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML)
    return ADD_PROD_CAT


async def admin_addprod_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or db.get_category(int(text)) is None:
        await update.message.reply_text("⚠️ ID danh mục không hợp lệ. Nhập lại:")
        return ADD_PROD_CAT
    context.user_data["new_prod_cat"] = int(text)
    await update.message.reply_text("✏️ Nhập tên sản phẩm (ví dụ: Acc CapCut Pro 1 năm):")
    return ADD_PROD_NAME


async def admin_addprod_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["new_prod_name"] = update.message.text.strip()
    await update.message.reply_text("💰 Nhập giá bán (VNĐ, chỉ nhập số, ví dụ: 25000):")
    return ADD_PROD_PRICE


async def admin_addprod_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip().replace(".", "").replace(",", "")
    if not text.isdigit():
        await update.message.reply_text("⚠️ Giá không hợp lệ. Nhập lại (chỉ số):")
        return ADD_PROD_PRICE
    context.user_data["new_prod_price"] = int(text)
    await update.message.reply_text("📝 Nhập mô tả sản phẩm (hoặc gõ - để bỏ qua):")
    return ADD_PROD_DESC


async def admin_addprod_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = update.message.text.strip()
    if desc == "-":
        desc = ""
    pid = db.add_product(
        context.user_data["new_prod_cat"],
        context.user_data["new_prod_name"],
        context.user_data["new_prod_price"],
        desc,
    )
    await update.message.reply_text(
        f"✅ Đã thêm sản phẩm #{pid}: {context.user_data['new_prod_name']} — "
        f"{fmt_money(context.user_data['new_prod_price'])}\n\n"
        f"Dùng menu 📥 Nhập kho để thêm nội dung/tài khoản cho sản phẩm này.",
        reply_markup=admin_kb(),
    )
    context.user_data.clear()
    return ConversationHandler.END


# ---------------- Admin: add stock ----------------
async def admin_addstock_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cats = db.list_categories()
    lines = ["✏️ Nhập <b>ID sản phẩm</b> cần nhập kho:\n"]
    for c in cats:
        for p in db.list_products(category_id=c["id"], active_only=False):
            lines.append(f"[{p['id']}] {c['name']} - {p['name']} ({fmt_money(p['price'])})")
    if len(lines) == 1:
        await query.edit_message_text("⚠️ Chưa có sản phẩm nào. Hãy thêm sản phẩm trước.", reply_markup=admin_kb())
        return ConversationHandler.END
    await query.edit_message_text("\n".join(lines), parse_mode=ParseMode.HTML)
    return ADD_STOCK_PROD


async def admin_addstock_prod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if not text.isdigit() or db.get_product(int(text)) is None:
        await update.message.reply_text("⚠️ ID sản phẩm không hợp lệ. Nhập lại:")
        return ADD_STOCK_PROD
    context.user_data["stock_prod_id"] = int(text)
    await update.message.reply_text(
        "📥 Dán danh sách tài khoản/nội dung, <b>mỗi dòng một item</b>.\n"
        "Ví dụ:\n<code>user1:pass1\nuser2:pass2</code>",
        parse_mode=ParseMode.HTML,
    )
    return ADD_STOCK_CONTENT


async def admin_addstock_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    lines = update.message.text.split("\n")
    pid = context.user_data["stock_prod_id"]
    added = db.add_stock_bulk(pid, lines)
    p = db.get_product(pid)
    await update.message.reply_text(
        f"✅ Đã nhập {added} item vào kho cho sản phẩm: {p['name']}\n"
        f"📊 Tổng tồn kho hiện tại: {db.count_available_stock(pid)}",
        reply_markup=admin_kb(),
    )
    context.user_data.clear()
    return ConversationHandler.END


# ---------------- Admin: misc commands ----------------
async def admin_setbalance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    try:
        target_id, amount = context.args[0], int(context.args[1])
        db.set_balance(int(target_id), amount)
        await update.message.reply_text(f"✅ Đã đặt số dư user {target_id} = {fmt_money(amount)}")
        await context.bot.send_message(chat_id=int(target_id), text=f"👛 Số dư của bạn đã được admin cập nhật: {fmt_money(amount)}")
    except (IndexError, ValueError):
        await update.message.reply_text("Cú pháp: /setbalance <user_id> <so_tien>")


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("❎ Đã huỷ thao tác.", reply_markup=MAIN_MENU_KB)
    return ConversationHandler.END


# =========================================================
#                       APP SETUP
# =========================================================
def main():
    if not config.BOT_TOKEN:
        raise SystemExit("⚠️  Chưa cấu hình BOT_TOKEN trong .env")

    db.init_db()

    app = Application.builder().token(config.BOT_TOKEN).build()

    # ---- User commands / menu ----
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Regex("^🛍 Cửa hàng$"), show_shop))
    app.add_handler(MessageHandler(filters.Regex("^👛 Số dư$"), show_balance))
    app.add_handler(MessageHandler(filters.Regex("^🧾 Lịch sử mua hàng$"), show_history))
    app.add_handler(MessageHandler(filters.Regex("^☎️ Hỗ trợ$"), show_support))

    # ---- Shop navigation callbacks ----
    app.add_handler(CallbackQueryHandler(cb_show_category, pattern=r"^cat:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_show_product, pattern=r"^prod:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_buy_product, pattern=r"^buy:\d+$"))
    app.add_handler(CallbackQueryHandler(cb_back_to_shop, pattern=r"^menu:shop$"))
    app.add_handler(CallbackQueryHandler(cb_deposit_decision, pattern=r"^dep:(approve|reject):\d+$"))

    # ---- Deposit conversation ----
    deposit_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^💳 Nạp tiền$"), deposit_start)],
        states={DEPOSIT_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, deposit_amount)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(deposit_conv)

    # ---- Admin panel ----
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("setbalance", admin_setbalance))
    app.add_handler(CallbackQueryHandler(cb_admin_stats, pattern=r"^adm:stats$"))
    app.add_handler(CallbackQueryHandler(cb_admin_listprod, pattern=r"^adm:listprod$"))

    addcat_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_addcat_start, pattern=r"^adm:addcat$")],
        states={ADD_CAT_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addcat_name)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    addprod_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_addprod_start, pattern=r"^adm:addprod$")],
        states={
            ADD_PROD_CAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addprod_cat)],
            ADD_PROD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addprod_name)],
            ADD_PROD_PRICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addprod_price)],
            ADD_PROD_DESC: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addprod_desc)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    addstock_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_addstock_start, pattern=r"^adm:addstock$")],
        states={
            ADD_STOCK_PROD: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addstock_prod)],
            ADD_STOCK_CONTENT: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_addstock_content)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(addcat_conv)
    app.add_handler(addprod_conv)
    app.add_handler(addstock_conv)

    logger.info("Bot đang chạy...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
