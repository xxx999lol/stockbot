"""
Lớp thao tác database SQLite cho bot bán hàng.
Dùng sqlite3 đồng bộ (đủ nhanh cho quy mô shop nhỏ/vừa trên Telegram).
"""
import sqlite3
import datetime
from contextlib import contextmanager

from config import DB_PATH


def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


@contextmanager
def get_conn():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                balance     INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS categories (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                emoji       TEXT DEFAULT '📦'
            );

            CREATE TABLE IF NOT EXISTS products (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                name        TEXT NOT NULL,
                price       INTEGER NOT NULL,
                description TEXT DEFAULT '',
                active      INTEGER NOT NULL DEFAULT 1,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS stock (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER NOT NULL,
                content     TEXT NOT NULL,
                is_sold     INTEGER NOT NULL DEFAULT 0,
                sold_to     INTEGER,
                sold_at     TEXT,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS orders (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                product_id  INTEGER NOT NULL,
                product_name TEXT NOT NULL,
                price       INTEGER NOT NULL,
                stock_id    INTEGER,
                created_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS deposits (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                amount      INTEGER NOT NULL,
                status      TEXT NOT NULL DEFAULT 'pending',
                created_at  TEXT NOT NULL,
                resolved_at TEXT
            );
            """
        )


def now():
    return datetime.datetime.now().isoformat(timespec="seconds")


# ---------- USERS ----------
def get_or_create_user(user_id: int, username: str):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO users (user_id, username, balance, created_at) VALUES (?,?,0,?)",
                (user_id, username or "", now()),
            )
            row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
        else:
            conn.execute("UPDATE users SET username=? WHERE user_id=?", (username or "", user_id))
        return dict(row)


def get_balance(user_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute("SELECT balance FROM users WHERE user_id=?", (user_id,)).fetchone()
        return row["balance"] if row else 0


def change_balance(user_id: int, delta: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (delta, user_id))


def set_balance(user_id: int, amount: int):
    with get_conn() as conn:
        conn.execute("UPDATE users SET balance = ? WHERE user_id=?", (amount, user_id))


def count_users():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]


def all_user_ids():
    with get_conn() as conn:
        return [r["user_id"] for r in conn.execute("SELECT user_id FROM users").fetchall()]


# ---------- CATEGORIES ----------
def add_category(name: str, emoji: str = "📦"):
    with get_conn() as conn:
        conn.execute("INSERT INTO categories (name, emoji) VALUES (?,?)", (name, emoji))


def list_categories():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM categories ORDER BY id").fetchall()]


def get_category(cat_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM categories WHERE id=?", (cat_id,)).fetchone()
        return dict(row) if row else None


def delete_category(cat_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))


# ---------- PRODUCTS ----------
def add_product(category_id: int, name: str, price: int, description: str = ""):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO products (category_id, name, price, description) VALUES (?,?,?,?)",
            (category_id, name, price, description),
        )
        return cur.lastrowid


def list_products(category_id: int = None, active_only: bool = True):
    with get_conn() as conn:
        q = "SELECT * FROM products"
        params = []
        conds = []
        if category_id is not None:
            conds.append("category_id=?")
            params.append(category_id)
        if active_only:
            conds.append("active=1")
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY id"
        return [dict(r) for r in conn.execute(q, params).fetchall()]


def get_product(product_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        return dict(row) if row else None


def set_product_active(product_id: int, active: bool):
    with get_conn() as conn:
        conn.execute("UPDATE products SET active=? WHERE id=?", (1 if active else 0, product_id))


def delete_product(product_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM products WHERE id=?", (product_id,))


# ---------- STOCK ----------
def add_stock_bulk(product_id: int, lines: list):
    with get_conn() as conn:
        conn.executemany(
            "INSERT INTO stock (product_id, content, is_sold) VALUES (?,?,0)",
            [(product_id, line) for line in lines if line.strip()],
        )
        return len([line for line in lines if line.strip()])


def count_available_stock(product_id: int) -> int:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) c FROM stock WHERE product_id=? AND is_sold=0", (product_id,)
        ).fetchone()
        return row["c"]


def take_one_stock(product_id: int, buyer_id: int):
    """Lấy 1 item còn hàng, đánh dấu đã bán, trả về nội dung (hoặc None nếu hết hàng)."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM stock WHERE product_id=? AND is_sold=0 ORDER BY id LIMIT 1",
            (product_id,),
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE stock SET is_sold=1, sold_to=?, sold_at=? WHERE id=?",
            (buyer_id, now(), row["id"]),
        )
        return dict(row)


# ---------- ORDERS ----------
def create_order(user_id: int, product_id: int, product_name: str, price: int, stock_id: int):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO orders (user_id, product_id, product_name, price, stock_id, created_at) "
            "VALUES (?,?,?,?,?,?)",
            (user_id, product_id, product_name, price, stock_id, now()),
        )


def list_orders(user_id: int, limit: int = 20):
    with get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM orders WHERE user_id=? ORDER BY id DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        ]


def total_revenue():
    with get_conn() as conn:
        row = conn.execute("SELECT COALESCE(SUM(price),0) s FROM orders").fetchone()
        return row["s"]


def count_orders():
    with get_conn() as conn:
        return conn.execute("SELECT COUNT(*) c FROM orders").fetchone()["c"]


# ---------- DEPOSITS ----------
def create_deposit(user_id: int, amount: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO deposits (user_id, amount, status, created_at) VALUES (?,?,?,?)",
            (user_id, amount, "pending", now()),
        )
        return cur.lastrowid


def get_deposit(deposit_id: int):
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM deposits WHERE id=?", (deposit_id,)).fetchone()
        return dict(row) if row else None


def resolve_deposit(deposit_id: int, status: str):
    with get_conn() as conn:
        conn.execute(
            "UPDATE deposits SET status=?, resolved_at=? WHERE id=?",
            (status, now(), deposit_id),
        )
