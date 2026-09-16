import sys
import sqlite3
import csv
import os
import re
import hashlib
from datetime import datetime, timedelta

import requests

from PySide6.QtCore import Qt, QDate, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QFrame,
    QStackedWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QComboBox,
    QDateEdit,
    QTabWidget,
    QMessageBox,
    QDialog,
    QDialogButtonBox,
    QTextEdit,
    QSpinBox,
    QCheckBox,
    QFileDialog,
    QGroupBox,
    QHeaderView,
    QAbstractItemView,
    QSplitter,
    QListWidget,
    QListWidgetItem,
)


DB_FILE = "library.db"


def get_app_base_dir():
    """
    Uygulama .exe olarak paketlendiğinde (PyInstaller vb.) veritabanı
    dosyalarının geçici çıkarma klasörüne değil, .exe'nin bulunduğu
    klasöre kaydedilmesini sağlar. Normal .py olarak çalıştırıldığında
    ise bu dosyanın bulunduğu klasör kullanılır.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller ile derlenmiş .exe olarak çalışıyor
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


APP_BASE_DIR = get_app_base_dir()

# Kitap / üye / ödünç verilerinin tutulduğu ana veritabanı
DB_FILE = os.path.join(APP_BASE_DIR, "kutuphane_veri.db")

# Tüm ekleme / silme / güncelleme işlemlerinin ayrıca kaydedildiği
# işlem geçmişi (audit log) veritabanı - ana veritabanından bağımsız
LOG_DB_FILE = os.path.join(APP_BASE_DIR, "kutuphane_islemler.db")


# =========================================================
# DİNAMİK TEMA (AYDINLIK / KARANLIK) QSS TANIMLARI
# =========================================================
# Not: Karanlık modda TÜM metinler (etiket, tablo, form, dialog,
# grup kutusu başlığı, mesaj kutusu vb.) okunabilirlik için
# beyaza (#FFFFFF) yakın renkte tutulur.

LIGHT_THEME_QSS = """
QMainWindow, QWidget {
    background-color: #F3F4F6;
    color: #1F2937;
    font-size: 13px;
}
QLabel { color: #1F2937; }
#AppTitle {
    color: #1F2937;
    font-size: 17px;
    font-weight: bold;
    padding: 4px 2px 12px 2px;
}
#SidebarSectionLabel {
    color: #6B7280;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    padding-top: 2px;
}
#SidebarFrame {
    background-color: #FFFFFF;
    border-right: 1px solid #E5E7EB;
}
#ContentStack {
    background-color: #F3F4F6;
}
QPushButton {
    background-color: #E5E7EB;
    color: #1F2937;
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    padding: 6px 12px;
}
QPushButton:hover { background-color: #D1D5DB; }
QPushButton[class="nav-btn"] {
    background-color: transparent;
    border: none;
    text-align: left;
    color: #374151;
    font-weight: 500;
    padding: 9px 10px;
    border-radius: 8px;
}
QPushButton[class="nav-btn"]:hover { background-color: #EEF2FF; color: #4338CA; }
QPushButton[class="nav-btn"]:checked { background-color: #4338CA; color: #FFFFFF; font-weight: bold; }
#ThemeToggleButton {
    background-color: #EEF2FF;
    color: #4338CA;
    border: 1px solid #C7D2FE;
    border-radius: 8px;
    padding: 8px;
    font-weight: 600;
}
#ThemeToggleButton:hover { background-color: #E0E7FF; }
#AccordionHeaderButton {
    background-color: transparent;
    border: none;
    text-align: left;
    color: #374151;
    font-weight: 600;
    padding: 9px 10px;
    border-radius: 8px;
}
#AccordionHeaderButton:hover { background-color: #EEF2FF; }
#AccordionHeaderButton:checked { color: #4338CA; }
#AccordionContainer { background-color: transparent; }
QLineEdit, QComboBox, QDateEdit, QSpinBox, QTextEdit {
    background-color: #FFFFFF;
    color: #1F2937;
    border: 1px solid #D1D5DB;
    border-radius: 6px;
    padding: 5px 8px;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QTextEdit:focus {
    border: 1px solid #4338CA;
}
QGroupBox {
    color: #1F2937;
    border: 1px solid #D1D5DB;
    border-radius: 8px;
    margin-top: 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #1F2937;
}
QTableWidget {
    background-color: #FFFFFF;
    color: #1F2937;
    gridline-color: #E5E7EB;
    border: 1px solid #E5E7EB;
    selection-background-color: #C7D2FE;
    selection-color: #1F2937;
}
QHeaderView::section {
    background-color: #F3F4F6;
    color: #1F2937;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #E5E7EB;
    font-weight: 600;
}
QCheckBox { color: #1F2937; }
QDialog { background-color: #F9FAFB; color: #1F2937; }
QMessageBox { background-color: #F9FAFB; color: #1F2937; }
"""

DARK_THEME_QSS = """
QMainWindow, QWidget {
    background-color: #121214;
    color: #FFFFFF;
    font-size: 13px;
}
QLabel { color: #FFFFFF; }
#AppTitle {
    color: #FFFFFF;
    font-size: 17px;
    font-weight: bold;
    padding: 4px 2px 12px 2px;
}
#SidebarSectionLabel {
    color: #A1A1AA;
    font-size: 11px;
    font-weight: 600;
    text-transform: uppercase;
    padding-top: 2px;
}
#SidebarFrame {
    background-color: #18181B;
    border-right: 1px solid #27272A;
}
#ContentStack {
    background-color: #121214;
}
QPushButton {
    background-color: #27272A;
    color: #FFFFFF;
    border: 1px solid #3F3F46;
    border-radius: 6px;
    padding: 6px 12px;
}
QPushButton:hover { background-color: #3F3F46; }
QPushButton[class="nav-btn"] {
    background-color: transparent;
    border: none;
    text-align: left;
    color: #FFFFFF;
    font-weight: 500;
    padding: 9px 10px;
    border-radius: 8px;
}
QPushButton[class="nav-btn"]:hover { background-color: #27272A; color: #FFFFFF; }
QPushButton[class="nav-btn"]:checked { background-color: #6366F1; color: #FFFFFF; font-weight: bold; }
#ThemeToggleButton {
    background-color: #312E81;
    color: #FFFFFF;
    border: 1px solid #4F46E5;
    border-radius: 8px;
    padding: 8px;
    font-weight: 600;
}
#ThemeToggleButton:hover { background-color: #3730A3; }
#AccordionHeaderButton {
    background-color: transparent;
    border: none;
    text-align: left;
    color: #FFFFFF;
    font-weight: 600;
    padding: 9px 10px;
    border-radius: 8px;
}
#AccordionHeaderButton:hover { background-color: #27272A; }
#AccordionHeaderButton:checked { color: #A5B4FC; }
#AccordionContainer { background-color: transparent; }
QLineEdit, QComboBox, QDateEdit, QSpinBox, QTextEdit {
    background-color: #18181B;
    color: #FFFFFF;
    border: 1px solid #3F3F46;
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: #4F46E5;
}
QLineEdit:focus, QComboBox:focus, QDateEdit:focus, QSpinBox:focus, QTextEdit:focus {
    border: 1px solid #6366F1;
}
QComboBox QAbstractItemView {
    background-color: #18181B;
    color: #FFFFFF;
    selection-background-color: #4F46E5;
    selection-color: #FFFFFF;
}
QGroupBox {
    color: #FFFFFF;
    border: 1px solid #3F3F46;
    border-radius: 8px;
    margin-top: 10px;
    font-weight: 600;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: #FFFFFF;
}
QTableWidget {
    background-color: #18181B;
    color: #FFFFFF;
    gridline-color: #27272A;
    border: 1px solid #27272A;
    selection-background-color: #4F46E5;
    selection-color: #FFFFFF;
}
QTableWidget::item { color: #FFFFFF; }
QHeaderView::section {
    background-color: #27272A;
    color: #FFFFFF;
    padding: 6px;
    border: none;
    border-bottom: 1px solid #3F3F46;
    font-weight: 600;
}
QCheckBox { color: #FFFFFF; }
QDialog { background-color: #121214; color: #FFFFFF; }
QMessageBox { background-color: #18181B; color: #FFFFFF; }
QMessageBox QLabel { color: #FFFFFF; }
QTabWidget::pane { border: 1px solid #27272A; }
QTabBar::tab { background: #18181B; color: #FFFFFF; padding: 8px; }
QTabBar::tab:selected { background: #6366F1; color: #FFFFFF; }
"""


# =========================================================
# GENEL YARDIMCI FONKSİYONLAR
# =========================================================

def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def display_date(value):
    if not value:
        return ""

    try:
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%y")
    except ValueError:
        try:
            return datetime.strptime(value, "%Y-%m-%d").strftime("%d/%m/%y")
        except ValueError:
            return str(value)


def display_datetime(value):
    if not value:
        return ""

    try:
        return datetime.strptime(
            value, "%Y-%m-%d %H:%M:%S"
        ).strftime("%d/%m/%y %H:%M")
    except ValueError:
        return str(value)


def normalize_isbn(value):
    if value is None:
        return ""

    return re.sub(r"[\s\-]", "", str(value).strip()).upper()


def is_valid_isbn(value):
    value = normalize_isbn(value)

    if len(value) == 10:
        return (
            all(c.isdigit() or (i == 9 and c == "X") for i, c in enumerate(value))
        )

    if len(value) == 13:
        return value.isdigit()

    return False


def qdate_to_db(qdate):
    return qdate.toString("yyyy-MM-dd")


def date_range_from_widgets(start_widget, end_widget):
    start = start_widget.date().toString("yyyy-MM-dd") + " 00:00:00"
    end = end_widget.date().toString("yyyy-MM-dd") + " 23:59:59"
    return start, end


# =========================================================
# VERİTABANI
# =========================================================

class Database:

    def __init__(self, filename=DB_FILE, log_filename=LOG_DB_FILE):
        # Ana veritabanı: kitaplar, nüshalar, üyeler, ödünç kayıtları
        self.conn = sqlite3.connect(filename)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

        # İşlem geçmişi (audit log) veritabanı: ayrı dosya
        self.log_conn = sqlite3.connect(log_filename)
        self.log_conn.row_factory = sqlite3.Row

        # Sidebar'daki "İşlemi Yapan Kullanıcı" seçiminden gelen,
        # log() çağrılarında otomatik kullanılacak aktif kullanıcı id'si
        self.current_user_id = None

        self.create_tables()
        self.create_log_tables()
        self.migrate_database()

    def execute(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        self.conn.commit()
        return cur

    def executemany(self, sql, data):
        cur = self.conn.cursor()
        cur.executemany(sql, data)
        self.conn.commit()
        return cur

    def fetchone(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchone()

    def fetchall(self, sql, params=()):
        cur = self.conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    # -----------------------------------------------------
    # İŞLEM GEÇMİŞİ (AYRI VERİTABANI) YARDIMCILARI
    # -----------------------------------------------------

    def log_execute(self, sql, params=()):
        cur = self.log_conn.cursor()
        cur.execute(sql, params)
        self.log_conn.commit()
        return cur

    def log_fetchall(self, sql, params=()):
        cur = self.log_conn.cursor()
        cur.execute(sql, params)
        return cur.fetchall()

    def create_log_tables(self):
        self.log_execute("""
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                action TEXT,
                target_type TEXT,
                target_id INTEGER,
                created_at TEXT
            )
        """)

    def create_tables(self):

        self.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                isbn TEXT,
                title TEXT NOT NULL,
                author TEXT,
                publisher TEXT,
                publication_year INTEGER,
                edition TEXT,
                language TEXT,
                category TEXT,
                description TEXT,
                status TEXT DEFAULT 'Aktif',
                created_at TEXT
            )
        """)

        self.execute("""
            CREATE TABLE IF NOT EXISTS book_copies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id INTEGER NOT NULL,
                book_number TEXT UNIQUE,
                shelf TEXT,
                status TEXT DEFAULT 'Mevcut',
                acquisition_date TEXT,
                notes TEXT,
                FOREIGN KEY(book_id)
                    REFERENCES books(id)
                    ON DELETE RESTRICT
            )
        """)

        self.execute("""
            CREATE TABLE IF NOT EXISTS members (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                member_number TEXT UNIQUE,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                phone TEXT,
                email TEXT,
                registration_date TEXT,
                status TEXT DEFAULT 'Aktif',
                notes TEXT
            )
        """)

        self.execute("""
            CREATE TABLE IF NOT EXISTS loans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_copy_id INTEGER NOT NULL,
                member_id INTEGER NOT NULL,
                borrowed_at TEXT NOT NULL,
                due_at TEXT NOT NULL,
                returned_at TEXT,
                notes TEXT,
                FOREIGN KEY(book_copy_id)
                    REFERENCES book_copies(id)
                    ON DELETE RESTRICT,
                FOREIGN KEY(member_id)
                    REFERENCES members(id)
                    ON DELETE RESTRICT
            )
        """)

        self.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        """)

        self.execute("""
            CREATE TABLE IF NOT EXISTS system_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password TEXT,
                role TEXT DEFAULT 'Viewer',
                status TEXT DEFAULT 'Aktif'
            )
        """)

        self.execute("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)

    def migrate_database(self):

        tables = {
            "books": [
                ("isbn", "TEXT"),
                ("title", "TEXT"),
                ("author", "TEXT"),
                ("publisher", "TEXT"),
                ("publication_year", "INTEGER"),
                ("edition", "TEXT"),
                ("language", "TEXT"),
                ("category", "TEXT"),
                ("description", "TEXT"),
                ("status", "TEXT DEFAULT 'Aktif'"),
                ("created_at", "TEXT"),
            ],
            "book_copies": [
                ("book_number", "TEXT"),
                ("shelf", "TEXT"),
                ("status", "TEXT DEFAULT 'Mevcut'"),
                ("acquisition_date", "TEXT"),
                ("notes", "TEXT"),
            ],
            "members": [
                ("member_number", "TEXT"),
                ("first_name", "TEXT"),
                ("last_name", "TEXT"),
                ("phone", "TEXT"),
                ("email", "TEXT"),
                ("registration_date", "TEXT"),
                ("status", "TEXT DEFAULT 'Aktif'"),
                ("notes", "TEXT"),
            ],
            "loans": [
                ("borrowed_at", "TEXT"),
                ("due_at", "TEXT"),
                ("returned_at", "TEXT"),
                ("notes", "TEXT"),
            ],
        }

        for table, columns in tables.items():
            existing = {
                row["name"]
                for row in self.fetchall(f"PRAGMA table_info({table})")
            }

            for column, definition in columns:
                if column not in existing:
                    try:
                        self.execute(
                            f"ALTER TABLE {table} ADD COLUMN {column} {definition}"
                        )
                    except sqlite3.OperationalError:
                        pass

        self.execute("""
            UPDATE books
            SET created_at = ?
            WHERE created_at IS NULL OR created_at = ''
        """, (now_string(),))

        self.execute("""
            UPDATE books
            SET status = 'Aktif'
            WHERE status IS NULL OR status = ''
        """)

        self.execute("""
            UPDATE members
            SET status = 'Aktif'
            WHERE status IS NULL OR status = ''
        """)

        self.execute("""
            UPDATE book_copies
            SET status = 'Mevcut'
            WHERE status IS NULL OR status = ''
        """)

    # -----------------------------------------------------
    # LOG
    # -----------------------------------------------------

    def log(self, action, target_type=None, target_id=None, user_id=None):
        if user_id is None:
            user_id = self.current_user_id

        self.log_execute("""
            INSERT INTO activity_logs
            (user_id, action, target_type, target_id, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            user_id,
            action,
            target_type,
            target_id,
            now_string()
        ))

    # -----------------------------------------------------
    # ADMİN ŞİFRESİ VE KULLANICI YÖNETİMİ
    # -----------------------------------------------------

    def is_admin_password_set(self):
        row = self.fetchone("""
            SELECT value FROM app_settings WHERE key = 'admin_password_hash'
        """)
        return row is not None and bool(row["value"])

    def set_admin_password(self, password):
        password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

        self.execute("""
            INSERT OR REPLACE INTO app_settings (key, value)
            VALUES ('admin_password_hash', ?)
        """, (password_hash,))

    def verify_admin_password(self, password):
        row = self.fetchone("""
            SELECT value FROM app_settings WHERE key = 'admin_password_hash'
        """)

        if not row or not row["value"]:
            return False

        password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()
        return row["value"] == password_hash

    def add_user(self, username, role="Kullanıcı"):
        username = username.strip()

        if not username:
            raise ValueError("Kullanıcı adı boş olamaz.")

        existing = self.fetchone("""
            SELECT id FROM system_users WHERE username = ?
        """, (username,))

        if existing:
            raise ValueError("Bu kullanıcı adı zaten kayıtlı.")

        cur = self.execute("""
            INSERT INTO system_users (username, role, status)
            VALUES (?, ?, 'Aktif')
        """, (username, role))

        user_id = cur.lastrowid
        self.log("Kullanıcı eklendi", "user", user_id)
        return user_id

    def get_active_users(self):
        return self.fetchall("""
            SELECT * FROM system_users
            WHERE status = 'Aktif'
            ORDER BY username COLLATE NOCASE
        """)

    def get_all_users(self):
        return self.fetchall("""
            SELECT * FROM system_users
            ORDER BY username COLLATE NOCASE
        """)

    def deactivate_user(self, user_id):
        self.execute("""
            UPDATE system_users SET status = 'Pasif' WHERE id = ?
        """, (user_id,))

        self.log("Kullanıcı pasifleştirildi", "user", user_id)

    # -----------------------------------------------------
    # KİTAPLAR
    # -----------------------------------------------------

    def find_book_by_isbn(self, isbn):
        isbn = normalize_isbn(isbn)

        return self.fetchone("""
            SELECT *
            FROM books
            WHERE isbn = ?
            LIMIT 1
        """, (isbn,))

    def add_book(
        self,
        isbn,
        title,
        author="",
        publisher="",
        publication_year=None,
        edition="",
        language="",
        category="",
        description="",
    ):
        isbn = normalize_isbn(isbn)

        cur = self.execute("""
            INSERT INTO books
            (
                isbn,
                title,
                author,
                publisher,
                publication_year,
                edition,
                language,
                category,
                description,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Aktif', ?)
        """, (
            isbn,
            title,
            author,
            publisher,
            publication_year,
            edition,
            language,
            category,
            description,
            now_string()
        ))

        book_id = cur.lastrowid
        self.log("Kitap eklendi", "book", book_id)
        return book_id

    def add_copy(
        self,
        book_id,
        book_number=None,
        shelf="",
        status="Mevcut",
        notes=""
    ):
        book_number = book_number.strip() if book_number else None

        if book_number:
            existing = self.fetchone("""
                SELECT id
                FROM book_copies
                WHERE book_number = ?
            """, (book_number,))

            if existing:
                raise ValueError("Bu Kitap Numarası zaten kullanılıyor.")

        cur = self.execute("""
            INSERT INTO book_copies
            (
                book_id,
                book_number,
                shelf,
                status,
                acquisition_date,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            book_id,
            book_number,
            shelf,
            status,
            now_string(),
            notes
        ))

        copy_id = cur.lastrowid
        self.log("Fiziksel kitap nüshası eklendi", "copy", copy_id)
        return copy_id

    def search_books(self, text=""):
        text = text.strip()

        if not text:
            return self.fetchall("""
                SELECT
                    b.*,
                    COUNT(c.id) AS copy_count,
                    SUM(
                        CASE
                            WHEN c.status = 'Mevcut'
                            THEN 1 ELSE 0
                        END
                    ) AS available_count
                FROM books b
                LEFT JOIN book_copies c
                    ON c.book_id = b.id
                GROUP BY b.id
                ORDER BY b.title COLLATE NOCASE
            """)

        like = f"%{text}%"

        return self.fetchall("""
            SELECT
                b.*,
                COUNT(c.id) AS copy_count,
                SUM(
                    CASE
                        WHEN c.status = 'Mevcut'
                        THEN 1 ELSE 0
                    END
                ) AS available_count
            FROM books b
            LEFT JOIN book_copies c
                ON c.book_id = b.id
            WHERE
                b.isbn LIKE ?
                OR b.title LIKE ?
                OR b.author LIKE ?
                OR b.publisher LIKE ?
                OR b.category LIKE ?
                OR EXISTS (
                    SELECT 1
                    FROM book_copies cc
                    WHERE cc.book_id = b.id
                    AND cc.book_number LIKE ?
                )
            GROUP BY b.id
            ORDER BY b.title COLLATE NOCASE
        """, (
            like,
            like,
            like,
            like,
            like,
            like
        ))

    def get_book(self, book_id):
        return self.fetchone("""
            SELECT *
            FROM books
            WHERE id = ?
        """, (book_id,))

    def get_book_copies(self, book_id):
        return self.fetchall("""
            SELECT *
            FROM book_copies
            WHERE book_id = ?
            ORDER BY
                CASE
                    WHEN book_number IS NULL THEN 1
                    ELSE 0
                END,
                book_number
        """, (book_id,))

    def get_copy(self, copy_id):
        return self.fetchone("""
            SELECT
                c.*,
                b.title,
                b.isbn,
                b.author
            FROM book_copies c
            JOIN books b ON b.id = c.book_id
            WHERE c.id = ?
        """, (copy_id,))

    def get_copy_by_number(self, book_number):
        return self.fetchone("""
            SELECT
                c.*,
                b.title,
                b.isbn,
                b.author
            FROM book_copies c
            JOIN books b ON b.id = c.book_id
            WHERE c.book_number = ?
        """, (book_number.strip(),))

    def get_available_copies_by_isbn(self, isbn):
        isbn = normalize_isbn(isbn)

        return self.fetchall("""
            SELECT
                c.*,
                b.title,
                b.isbn,
                b.author
            FROM book_copies c
            JOIN books b ON b.id = c.book_id
            WHERE b.isbn = ?
            AND c.status = 'Mevcut'
            ORDER BY c.book_number
        """, (isbn,))

    def get_copies_by_isbn(self, isbn):
        isbn = normalize_isbn(isbn)

        return self.fetchall("""
            SELECT
                c.*,
                b.title,
                b.isbn,
                b.author
            FROM book_copies c
            JOIN books b ON b.id = c.book_id
            WHERE b.isbn = ?
            ORDER BY c.book_number
        """, (isbn,))

    def get_book_history(self, book_id):
        return self.fetchall("""
            SELECT
                l.*,
                c.book_number,
                m.member_number,
                m.first_name,
                m.last_name
            FROM loans l
            JOIN book_copies c
                ON c.id = l.book_copy_id
            JOIN members m
                ON m.id = l.member_id
            WHERE c.book_id = ?
            ORDER BY l.borrowed_at DESC
        """, (book_id,))

    def archive_book(self, book_id):
        self.execute("""
            UPDATE books
            SET status = 'Arşivde'
            WHERE id = ?
        """, (book_id,))

        self.execute("""
            UPDATE book_copies
            SET status = 'Arşivde'
            WHERE book_id = ?
            AND status != 'Ödünçte'
        """, (book_id,))

        self.log("Kitap arşivlendi", "book", book_id)

    # -----------------------------------------------------
    # ÜYELER
    # -----------------------------------------------------

    def add_member(
        self,
        member_number,
        first_name,
        last_name,
        phone="",
        email="",
        notes=""
    ):
        member_number = member_number.strip() if member_number else None

        if member_number:
            existing = self.fetchone("""
                SELECT id
                FROM members
                WHERE member_number = ?
            """, (member_number,))

            if existing:
                raise ValueError("Bu Üye Numarası zaten kullanılıyor.")

        cur = self.execute("""
            INSERT INTO members
            (
                member_number,
                first_name,
                last_name,
                phone,
                email,
                registration_date,
                status,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, 'Aktif', ?)
        """, (
            member_number,
            first_name.strip(),
            last_name.strip(),
            phone.strip(),
            email.strip(),
            now_string(),
            notes.strip()
        ))

        member_id = cur.lastrowid
        self.log("Üye eklendi", "member", member_id)
        return member_id

    def search_members(self, text=""):
        text = text.strip()

        if not text:
            return self.fetchall("""
                SELECT *
                FROM members
                ORDER BY last_name COLLATE NOCASE,
                         first_name COLLATE NOCASE
            """)

        like = f"%{text}%"

        return self.fetchall("""
            SELECT *
            FROM members
            WHERE
                member_number LIKE ?
                OR first_name LIKE ?
                OR last_name LIKE ?
                OR (first_name || ' ' || last_name) LIKE ?
                OR phone LIKE ?
                OR email LIKE ?
            ORDER BY last_name COLLATE NOCASE,
                     first_name COLLATE NOCASE
        """, (
            like,
            like,
            like,
            like,
            like,
            like
        ))

    def get_member(self, member_id):
        return self.fetchone("""
            SELECT *
            FROM members
            WHERE id = ?
        """, (member_id,))

    def get_active_loans_for_member(self, member_id):
        return self.fetchall("""
            SELECT
                l.*,
                c.book_number,
                b.title,
                b.isbn,
                b.author
            FROM loans l
            JOIN book_copies c
                ON c.id = l.book_copy_id
            JOIN books b
                ON b.id = c.book_id
            WHERE l.member_id = ?
            AND l.returned_at IS NULL
            ORDER BY l.due_at
        """, (member_id,))

    def get_member_history(self, member_id):
        return self.fetchall("""
            SELECT
                l.*,
                c.book_number,
                b.title,
                b.isbn
            FROM loans l
            JOIN book_copies c
                ON c.id = l.book_copy_id
            JOIN books b
                ON b.id = c.book_id
            WHERE l.member_id = ?
            ORDER BY l.borrowed_at DESC
        """, (member_id,))

    def deactivate_member(self, member_id):
        self.execute("""
            UPDATE members
            SET status = 'Pasif'
            WHERE id = ?
        """, (member_id,))

        self.log("Üye pasifleştirildi", "member", member_id)

    # -----------------------------------------------------
    # ÖDÜNÇ / İADE
    # -----------------------------------------------------

    def get_copy_active_loan(self, copy_id):
        return self.fetchone("""
            SELECT
                l.*,
                m.member_number,
                m.first_name,
                m.last_name,
                c.book_number,
                b.title,
                b.isbn
            FROM loans l
            JOIN members m
                ON m.id = l.member_id
            JOIN book_copies c
                ON c.id = l.book_copy_id
            JOIN books b
                ON b.id = c.book_id
            WHERE l.book_copy_id = ?
            AND l.returned_at IS NULL
            ORDER BY l.borrowed_at DESC
            LIMIT 1
        """, (copy_id,))

    def borrow_book(self, copy_id, member_id, due_at, notes=""):

        copy = self.get_copy(copy_id)

        if not copy:
            raise ValueError("Kitap nüshası bulunamadı.")

        if copy["status"] != "Mevcut":
            raise ValueError(
                f"Kitap şu anda '{copy['status']}' durumunda."
            )

        member = self.get_member(member_id)

        if not member:
            raise ValueError("Üye bulunamadı.")

        if member["status"] != "Aktif":
            raise ValueError("Pasif üyeye kitap ödünç verilemez.")

        active = self.get_copy_active_loan(copy_id)

        if active:
            raise ValueError("Bu kitap zaten ödünçte.")

        cur = self.execute("""
            INSERT INTO loans
            (
                book_copy_id,
                member_id,
                borrowed_at,
                due_at,
                returned_at,
                notes
            )
            VALUES (?, ?, ?, ?, NULL, ?)
        """, (
            copy_id,
            member_id,
            now_string(),
            due_at,
            notes
        ))

        loan_id = cur.lastrowid

        self.execute("""
            UPDATE book_copies
            SET status = 'Ödünçte'
            WHERE id = ?
        """, (copy_id,))

        self.log("Kitap ödünç verildi", "loan", loan_id)

        return loan_id

    def return_book(self, loan_id):

        loan = self.fetchone("""
            SELECT *
            FROM loans
            WHERE id = ?
        """, (loan_id,))

        if not loan:
            raise ValueError("Ödünç kaydı bulunamadı.")

        if loan["returned_at"]:
            raise ValueError("Bu kitap zaten iade edilmiş.")

        returned_at = now_string()

        self.execute("""
            UPDATE loans
            SET returned_at = ?
            WHERE id = ?
        """, (
            returned_at,
            loan_id
        ))

        self.execute("""
            UPDATE book_copies
            SET status = 'Mevcut'
            WHERE id = ?
        """, (
            loan["book_copy_id"],
        ))

        self.log("Kitap iade alındı", "loan", loan_id)

    def get_overdue_loans(self):
        current = now_string()

        return self.fetchall("""
            SELECT
                l.*,
                c.book_number,
                b.title,
                b.isbn,
                m.member_number,
                m.first_name,
                m.last_name
            FROM loans l
            JOIN book_copies c
                ON c.id = l.book_copy_id
            JOIN books b
                ON b.id = c.book_id
            JOIN members m
                ON m.id = l.member_id
            WHERE l.returned_at IS NULL
            AND l.due_at < ?
            ORDER BY l.due_at
        """, (current,))

    def search_active_loans_by_isbn(self, isbn):
        isbn = normalize_isbn(isbn)

        return self.fetchall("""
            SELECT
                l.*,
                c.book_number,
                b.title,
                b.isbn,
                m.member_number,
                m.first_name,
                m.last_name
            FROM loans l
            JOIN book_copies c
                ON c.id = l.book_copy_id
            JOIN books b
                ON b.id = c.book_id
            JOIN members m
                ON m.id = l.member_id
            WHERE b.isbn = ?
            AND l.returned_at IS NULL
            ORDER BY l.due_at
        """, (isbn,))

    # -----------------------------------------------------
    # İSTATİSTİK
    # -----------------------------------------------------

    def scalar(self, sql, params=()):
        row = self.fetchone(sql, params)

        if not row:
            return 0

        return list(row)[0] or 0

    def dashboard_stats(self):

        return {
            "works": self.scalar("""
                SELECT COUNT(*)
                FROM books
                WHERE status != 'Arşivde'
            """),

            "copies": self.scalar("""
                SELECT COUNT(*)
                FROM book_copies
                WHERE status != 'Arşivde'
            """),

            "available": self.scalar("""
                SELECT COUNT(*)
                FROM book_copies
                WHERE status = 'Mevcut'
            """),

            "borrowed": self.scalar("""
                SELECT COUNT(*)
                FROM book_copies
                WHERE status = 'Ödünçte'
            """),

            "lost": self.scalar("""
                SELECT COUNT(*)
                FROM book_copies
                WHERE status = 'Kayıp'
            """),

            "damaged": self.scalar("""
                SELECT COUNT(*)
                FROM book_copies
                WHERE status = 'Hasarlı'
            """),

            "members": self.scalar("""
                SELECT COUNT(*)
                FROM members
            """),

            "active_members": self.scalar("""
                SELECT COUNT(*)
                FROM members
                WHERE status = 'Aktif'
            """),

            "overdue": self.scalar("""
                SELECT COUNT(*)
                FROM loans
                WHERE returned_at IS NULL
                AND due_at < ?
            """, (now_string(),))
        }

    # -----------------------------------------------------
    # RAPORLAR
    # -----------------------------------------------------

    def report_general(self, start, end):

        stats = self.dashboard_stats()

        loans_period = self.scalar("""
            SELECT COUNT(*)
            FROM loans
            WHERE borrowed_at >= ?
            AND borrowed_at <= ?
        """, (start, end))

        returns_period = self.scalar("""
            SELECT COUNT(*)
            FROM loans
            WHERE returned_at >= ?
            AND returned_at <= ?
        """, (start, end))

        rows = [
            ["Toplam eser", stats["works"]],
            ["Toplam fiziksel nüsha", stats["copies"]],
            ["Mevcut", stats["available"]],
            ["Ödünçte", stats["borrowed"]],
            ["Geciken", stats["overdue"]],
            ["Kayıp", stats["lost"]],
            ["Hasarlı", stats["damaged"]],
            ["Toplam üye", stats["members"]],
            ["Aktif üye", stats["active_members"]],
            ["Tarih aralığındaki ödünç işlemleri", loans_period],
            ["Tarih aralığındaki iade işlemleri", returns_period],
        ]

        return ["Gösterge", "Değer"], rows

    def report_loans(self, start, end, date_mode="borrowed_at"):

        allowed = {
            "borrowed_at",
            "returned_at",
            "due_at"
        }

        if date_mode not in allowed:
            date_mode = "borrowed_at"

        if date_mode == "returned_at":
            condition = "l.returned_at >= ? AND l.returned_at <= ?"
        else:
            condition = f"l.{date_mode} >= ? AND l.{date_mode} <= ?"

        rows = self.fetchall(f"""
            SELECT
                m.member_number,
                m.first_name || ' ' || m.last_name AS member_name,
                c.book_number,
                b.title,
                b.isbn,
                l.borrowed_at,
                l.due_at,
                l.returned_at,
                CASE
                    WHEN l.returned_at IS NOT NULL
                        THEN 'İade edildi'
                    WHEN l.due_at < ?
                        THEN 'Gecikmiş'
                    ELSE 'Ödünçte'
                END AS status
            FROM loans l
            JOIN members m
                ON m.id = l.member_id
            JOIN book_copies c
                ON c.id = l.book_copy_id
            JOIN books b
                ON b.id = c.book_id
            WHERE {condition}
            ORDER BY l.borrowed_at DESC
        """, (
            now_string(),
            start,
            end
        ))

        result = []

        for row in rows:
            result.append([
                row["member_number"] or "",
                row["member_name"],
                row["book_number"] or "",
                row["title"],
                row["isbn"] or "",
                display_datetime(row["borrowed_at"]),
                display_datetime(row["due_at"]),
                display_datetime(row["returned_at"]),
                row["status"]
            ])

        headers = [
            "Üye No",
            "Üye",
            "Kitap No",
            "Kitap",
            "ISBN",
            "Ödünç Tarihi",
            "Son İade Tarihi",
            "İade Tarihi",
            "Durum"
        ]

        return headers, result

    def report_members(self, start, end):

        rows = self.fetchall("""
            SELECT
                m.member_number,
                m.first_name || ' ' || m.last_name AS member_name,
                COUNT(l.id) AS loan_count,
                SUM(
                    CASE
                        WHEN l.returned_at IS NULL
                        THEN 1 ELSE 0
                    END
                ) AS active_count,
                SUM(
                    CASE
                        WHEN l.returned_at IS NOT NULL
                        THEN 1 ELSE 0
                    END
                ) AS returned_count
            FROM members m
            LEFT JOIN loans l
                ON l.member_id = m.id
                AND l.borrowed_at >= ?
                AND l.borrowed_at <= ?
            GROUP BY m.id
            ORDER BY loan_count DESC,
                     member_name
        """, (start, end))

        result = []

        for row in rows:
            result.append([
                row["member_number"] or "",
                row["member_name"],
                row["loan_count"] or 0,
                row["active_count"] or 0,
                row["returned_count"] or 0
            ])

        headers = [
            "Üye No",
            "Üye",
            "Ödünç Sayısı",
            "Aktif Ödünç",
            "İade Edilen"
        ]

        return headers, result

    def report_books(self, start, end):

        rows = self.fetchall("""
            SELECT
                b.isbn,
                b.title,
                b.author,
                COUNT(DISTINCT c.id) AS copy_count,
                COUNT(l.id) AS loan_count
            FROM books b
            LEFT JOIN book_copies c
                ON c.book_id = b.id
            LEFT JOIN loans l
                ON l.book_copy_id = c.id
                AND l.borrowed_at >= ?
                AND l.borrowed_at <= ?
            GROUP BY b.id
            ORDER BY loan_count DESC,
                     b.title
        """, (start, end))

        result = []

        for row in rows:
            result.append([
                row["isbn"] or "",
                row["title"],
                row["author"] or "",
                row["copy_count"] or 0,
                row["loan_count"] or 0
            ])

        headers = [
            "ISBN",
            "Kitap",
            "Yazar",
            "Nüsha Sayısı",
            "Ödünç Sayısı"
        ]

        return headers, result

    def report_overdue(self, start, end):

        current = now_string()

        rows = self.fetchall("""
            SELECT
                m.member_number,
                m.first_name || ' ' || m.last_name AS member_name,
                c.book_number,
                b.title,
                b.isbn,
                l.borrowed_at,
                l.due_at
            FROM loans l
            JOIN members m
                ON m.id = l.member_id
            JOIN book_copies c
                ON c.id = l.book_copy_id
            JOIN books b
                ON b.id = c.book_id
            WHERE l.returned_at IS NULL
            AND l.due_at < ?
            AND l.due_at >= ?
            AND l.due_at <= ?
            ORDER BY l.due_at
        """, (
            current,
            start,
            end
        ))

        result = []

        for row in rows:
            try:
                due = datetime.strptime(
                    row["due_at"],
                    "%Y-%m-%d %H:%M:%S"
                )

                days = (datetime.now() - due).days

            except ValueError:
                days = ""

            result.append([
                row["member_number"] or "",
                row["member_name"],
                row["book_number"] or "",
                row["title"],
                row["isbn"] or "",
                display_date(row["borrowed_at"]),
                display_date(row["due_at"]),
                days
            ])

        headers = [
            "Üye No",
            "Üye",
            "Kitap No",
            "Kitap",
            "ISBN",
            "Ödünç Tarihi",
            "Son İade Tarihi",
            "Gecikme Günü"
        ]

        return headers, result

    def report_copy_history(self, start, end, book_number=""):

        if book_number.strip():
            rows = self.fetchall("""
                SELECT
                    c.book_number,
                    b.title,
                    b.isbn,
                    m.member_number,
                    m.first_name || ' ' || m.last_name AS member_name,
                    l.borrowed_at,
                    l.due_at,
                    l.returned_at
                FROM loans l
                JOIN book_copies c
                    ON c.id = l.book_copy_id
                JOIN books b
                    ON b.id = c.book_id
                JOIN members m
                    ON m.id = l.member_id
                WHERE c.book_number = ?
                AND l.borrowed_at >= ?
                AND l.borrowed_at <= ?
                ORDER BY l.borrowed_at DESC
            """, (
                book_number.strip(),
                start,
                end
            ))
        else:
            rows = self.fetchall("""
                SELECT
                    c.book_number,
                    b.title,
                    b.isbn,
                    m.member_number,
                    m.first_name || ' ' || m.last_name AS member_name,
                    l.borrowed_at,
                    l.due_at,
                    l.returned_at
                FROM loans l
                JOIN book_copies c
                    ON c.id = l.book_copy_id
                JOIN books b
                    ON b.id = c.book_id
                JOIN members m
                    ON m.id = l.member_id
                WHERE l.borrowed_at >= ?
                AND l.borrowed_at <= ?
                ORDER BY l.borrowed_at DESC
            """, (
                start,
                end
            ))

        result = []

        for row in rows:
            result.append([
                row["book_number"] or "",
                row["title"],
                row["isbn"] or "",
                row["member_number"] or "",
                row["member_name"],
                display_datetime(row["borrowed_at"]),
                display_datetime(row["due_at"]),
                display_datetime(row["returned_at"])
            ])

        headers = [
            "Kitap No",
            "Kitap",
            "ISBN",
            "Üye No",
            "Üye",
            "Ödünç Tarihi",
            "Son İade Tarihi",
            "İade Tarihi"
        ]

        return headers, result

    def generate_report(
        self,
        report_type,
        start,
        end,
        date_mode="borrowed_at",
        book_number=""
    ):

        if report_type == "Genel Durum":
            return self.report_general(start, end)

        if report_type == "Ödünç / İade":
            return self.report_loans(
                start,
                end,
                date_mode
            )

        if report_type == "Üye Raporu":
            return self.report_members(start, end)

        if report_type == "Kitap Kullanım":
            return self.report_books(start, end)

        if report_type == "Geciken Kitaplar":
            return self.report_overdue(start, end)

        if report_type == "Kitap Numarası Geçmişi":
            return self.report_copy_history(
                start,
                end,
                book_number
            )

        return [], []


# =========================================================
# ISBN / BARKOD BİLGİ ARAMA
# =========================================================

class ISBNLookupDialog(QDialog):

    information_found = None

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("ISBN / Barkod ile Kitap Bilgisi Ara")
        self.resize(700, 500)

        layout = QVBoxLayout(self)

        top = QHBoxLayout()

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(
            "ISBN veya ISBN barkodunu okutun/girin..."
        )

        self.search_button = QPushButton("Ara")

        top.addWidget(self.search_edit)
        top.addWidget(self.search_button)

        layout.addLayout(top)

        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)

        layout.addWidget(self.result_text)

        buttons = QHBoxLayout()

        self.transfer_button = QPushButton(
            "Bilgileri Kitap Ekle Ekranına Aktar"
        )

        self.close_button = QPushButton("Kapat")

        buttons.addWidget(self.transfer_button)
        buttons.addStretch()
        buttons.addWidget(self.close_button)

        layout.addLayout(buttons)

        self.search_button.clicked.connect(self.search)
        self.search_edit.returnPressed.connect(self.search)
        self.transfer_button.clicked.connect(self.transfer)
        self.close_button.clicked.connect(self.reject)

        self.transfer_button.setEnabled(False)

    def search(self):

        isbn = normalize_isbn(self.search_edit.text())

        if not isbn:
            QMessageBox.warning(
                self,
                "Uyarı",
                "ISBN veya barkod girin."
            )
            return

        if not is_valid_isbn(isbn):
            QMessageBox.warning(
                self,
                "Geçersiz ISBN",
                "Girilen değer geçerli bir ISBN-10 veya ISBN-13 görünmüyor.\n\n"
                "ISBN içindeki '-' karakterleri zorunlu değildir."
            )
            return

        try:
            url = f"https://openlibrary.org/isbn/{isbn}.json"

            response = requests.get(
                url,
                timeout=10,
                headers={
                    "User-Agent": "LibraryTrackingApp/1.0"
                }
            )

            if response.status_code != 200:
                raise ValueError(
                    "ISBN bilgisi Open Library'de bulunamadı."
                )

            data = response.json()

            authors = data.get("authors", [])

            author_names = []

            for author in authors:
                if isinstance(author, dict):
                    name = author.get("name")

                    if name:
                        author_names.append(name)

            author_text = ", ".join(author_names)

            publishers = data.get("publishers", [])

            publisher_text = ""

            if publishers:
                if isinstance(publishers[0], dict):
                    publisher_text = publishers[0].get(
                        "name",
                        ""
                    )
                else:
                    publisher_text = str(
                        publishers[0]
                    )

            publish_date = data.get(
                "publish_date",
                ""
            )

            description = data.get(
                "description",
                ""
            )

            if isinstance(description, dict):
                description = description.get(
                    "value",
                    ""
                )

            languages = data.get(
                "languages",
                []
            )

            language_text = ""

            if languages:
                language_names = []

                for lang in languages:
                    if isinstance(lang, dict):
                        key = lang.get("key", "")

                        if "/" in key:
                            key = key.split("/")[-1]

                        language_names.append(key)

                language_text = ", ".join(
                    language_names
                )

            title = data.get(
                "title",
                ""
            )

            self.information_found = {
                "isbn": isbn,
                "title": title,
                "author": author_text,
                "publisher": publisher_text,
                "publication_year": publish_date,
                "language": language_text,
                "description": description
            }

            text = (
                f"ISBN: {isbn}\n\n"
                f"Kitap: {title}\n"
                f"Yazar: {author_text}\n"
                f"Yayınevi: {publisher_text}\n"
                f"Yayın tarihi: {publish_date}\n"
                f"Dil: {language_text}\n\n"
                f"Açıklama:\n{description}"
            )

            self.result_text.setPlainText(text)
            self.transfer_button.setEnabled(True)

        except requests.RequestException as exc:

            QMessageBox.critical(
                self,
                "Bağlantı Hatası",
                f"ISBN servisine bağlanılamadı.\n\n{exc}"
            )

        except Exception as exc:

            QMessageBox.warning(
                self,
                "Bilgi Bulunamadı",
                str(exc)
            )

    def transfer(self):

        if not self.information_found:
            return

        self.accept()


# =========================================================
# KİTAP DETAY PENCERESİ
# =========================================================

class BookDetailsDialog(QDialog):

    def __init__(self, db, book_id, parent=None):
        super().__init__(parent)

        self.db = db
        self.book_id = book_id

        self.setWindowTitle("Kitap Detayı")
        self.resize(950, 700)

        layout = QVBoxLayout(self)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)

        layout.addWidget(self.info_label)

        copies_group = QGroupBox("Fiziksel Nüshalar")

        copies_layout = QVBoxLayout(copies_group)

        self.copies_table = QTableWidget()
        self.copies_table.setColumnCount(5)
        self.copies_table.setHorizontalHeaderLabels([
            "ID",
            "Kitap No",
            "Raf",
            "Durum",
            "Not"
        ])

        self.copies_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.copies_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.copies_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        copies_layout.addWidget(self.copies_table)

        layout.addWidget(copies_group)

        history_group = QGroupBox("Ödünç / İade Geçmişi")

        history_layout = QVBoxLayout(history_group)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(7)

        self.history_table.setHorizontalHeaderLabels([
            "Kitap No",
            "Üye No",
            "Üye",
            "Ödünç",
            "Son İade",
            "İade",
            "Durum"
        ])

        self.history_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        history_layout.addWidget(self.history_table)

        layout.addWidget(history_group)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Close
        )

        buttons.rejected.connect(self.reject)

        layout.addWidget(buttons)

        self.load_data()

    def load_data(self):

        book = self.db.get_book(self.book_id)

        if not book:
            return

        self.info_label.setText(
            f"<b>Kitap:</b> {book['title']}<br>"
            f"<b>ISBN:</b> {book['isbn'] or '-'}<br>"
            f"<b>Yazar:</b> {book['author'] or '-'}<br>"
            f"<b>Yayınevi:</b> {book['publisher'] or '-'}<br>"
            f"<b>Yayın yılı:</b> {book['publication_year'] or '-'}<br>"
            f"<b>Baskı:</b> {book['edition'] or '-'}<br>"
            f"<b>Dil:</b> {book['language'] or '-'}<br>"
            f"<b>Kategori:</b> {book['category'] or '-'}<br>"
            f"<b>Durum:</b> {book['status']}"
        )

        copies = self.db.get_book_copies(
            self.book_id
        )

        self.copies_table.setRowCount(
            len(copies)
        )

        for r, copy in enumerate(copies):

            values = [
                copy["id"],
                copy["book_number"] or "-",
                copy["shelf"] or "-",
                copy["status"],
                copy["notes"] or "-"
            ]

            for c, value in enumerate(values):
                self.copies_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )

        history = self.db.get_book_history(
            self.book_id
        )

        self.history_table.setRowCount(
            len(history)
        )

        for r, item in enumerate(history):

            status = (
                "İade edildi"
                if item["returned_at"]
                else (
                    "Gecikmiş"
                    if item["due_at"] < now_string()
                    else "Ödünçte"
                )
            )

            values = [
                item["book_number"] or "-",
                item["member_number"] or "-",
                f"{item['first_name']} {item['last_name']}",
                display_datetime(item["borrowed_at"]),
                display_datetime(item["due_at"]),
                display_datetime(item["returned_at"]),
                status
            ]

            for c, value in enumerate(values):
                self.history_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )


# =========================================================
# ÜYE DETAY PENCERESİ
# =========================================================

class MemberDetailsDialog(QDialog):

    def __init__(self, db, member_id, parent=None):
        super().__init__(parent)

        self.db = db
        self.member_id = member_id

        self.setWindowTitle("Üye Detayı")
        self.resize(900, 650)

        layout = QVBoxLayout(self)

        self.info_label = QLabel()
        self.info_label.setWordWrap(True)

        layout.addWidget(self.info_label)

        current_group = QGroupBox(
            "Üyenin Üzerindeki Kitaplar"
        )

        current_layout = QVBoxLayout(current_group)

        self.current_table = QTableWidget()
        self.current_table.setColumnCount(6)

        self.current_table.setHorizontalHeaderLabels([
            "Ödünç ID",
            "Kitap No",
            "Kitap",
            "ISBN",
            "Son İade",
            "Durum"
        ])

        self.current_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.current_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.current_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        current_layout.addWidget(self.current_table)

        self.return_button = QPushButton(
            "Seçili Kitabı İade Al"
        )

        current_layout.addWidget(
            self.return_button
        )

        layout.addWidget(current_group)

        history_group = QGroupBox(
            "Üye Geçmişi"
        )

        history_layout = QVBoxLayout(history_group)

        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)

        self.history_table.setHorizontalHeaderLabels([
            "Kitap No",
            "Kitap",
            "ISBN",
            "Ödünç Tarihi",
            "Son İade",
            "İade Tarihi"
        ])

        self.history_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.history_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        history_layout.addWidget(
            self.history_table
        )

        layout.addWidget(history_group)

        close = QPushButton("Kapat")
        close.clicked.connect(self.accept)

        layout.addWidget(close)

        self.return_button.clicked.connect(
            self.return_selected
        )

        self.load_data()

    def load_data(self):

        member = self.db.get_member(
            self.member_id
        )

        if not member:
            return

        self.info_label.setText(
            f"<b>Üye No:</b> {member['member_number'] or '-'}<br>"
            f"<b>Ad Soyad:</b> "
            f"{member['first_name']} {member['last_name']}<br>"
            f"<b>Telefon:</b> {member['phone'] or '-'}<br>"
            f"<b>E-posta:</b> {member['email'] or '-'}<br>"
            f"<b>Kayıt:</b> {display_datetime(member['registration_date'])}<br>"
            f"<b>Durum:</b> {member['status']}"
        )

        current = self.db.get_active_loans_for_member(
            self.member_id
        )

        self.current_table.setRowCount(
            len(current)
        )

        for r, item in enumerate(current):

            status = (
                "Gecikmiş"
                if item["due_at"] < now_string()
                else "Ödünçte"
            )

            values = [
                item["id"],
                item["book_number"] or "-",
                item["title"],
                item["isbn"] or "-",
                display_datetime(item["due_at"]),
                status
            ]

            for c, value in enumerate(values):
                self.current_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )

        history = self.db.get_member_history(
            self.member_id
        )

        self.history_table.setRowCount(
            len(history)
        )

        for r, item in enumerate(history):

            values = [
                item["book_number"] or "-",
                item["title"],
                item["isbn"] or "-",
                display_datetime(item["borrowed_at"]),
                display_datetime(item["due_at"]),
                display_datetime(item["returned_at"])
            ]

            for c, value in enumerate(values):
                self.history_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )

    def return_selected(self):

        row = self.current_table.currentRow()

        if row < 0:
            QMessageBox.warning(
                self,
                "Uyarı",
                "İade alınacak kitabı seçin."
            )
            return

        loan_id = int(
            self.current_table.item(
                row,
                0
            ).text()
        )

        answer = QMessageBox.question(
            self,
            "İade Onayı",
            "Seçili kitabı iade almak istediğinizden emin misiniz?"
        )

        if answer != QMessageBox.Yes:
            return

        try:
            self.db.return_book(
                loan_id
            )

            QMessageBox.information(
                self,
                "Başarılı",
                "Kitap iade alındı."
            )

            self.load_data()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Hata",
                str(exc)
            )


# =========================================================
# ANA UYGULAMA
# =========================================================

# =========================================================
# HIZLI KOMUT PALETİ (Ctrl+K)
# =========================================================

class CommandPaletteDialog(QDialog):

    def __init__(self, pages, parent=None):
        # pages: [(title, widget), ...] -> sidebar'daki gezinme sırasıyla
        super().__init__(parent)

        self.pages = pages
        self.selected_widget = None

        self.setWindowTitle("Hızlı Git")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Bir sayfa adı yazın (örn. Raporlar, Üyeler)...")
        self.search_edit.textChanged.connect(self.filter_list)
        layout.addWidget(self.search_edit)

        self.list_widget = QListWidget()
        self.list_widget.itemActivated.connect(self.choose_current)
        layout.addWidget(self.list_widget)

        self.search_edit.installEventFilter(self)

        self.filter_list("")
        self.search_edit.setFocus()

    def filter_list(self, text):
        self.list_widget.clear()
        text = text.strip().lower()

        for title, widget in self.pages:
            if text in title.lower():
                item = QListWidgetItem(title)
                item.setData(Qt.UserRole, widget)
                self.list_widget.addItem(item)

        if self.list_widget.count() > 0:
            self.list_widget.setCurrentRow(0)

    def choose_current(self, item=None):
        if item is None:
            item = self.list_widget.currentItem()

        if item is not None:
            self.selected_widget = item.data(Qt.UserRole)
            self.accept()

    def eventFilter(self, obj, event):
        if obj is self.search_edit and event.type() == event.Type.KeyPress:
            if event.key() in (Qt.Key_Down, Qt.Key_Up):
                current_row = self.list_widget.currentRow()
                if event.key() == Qt.Key_Down:
                    self.list_widget.setCurrentRow(
                        min(current_row + 1, self.list_widget.count() - 1)
                    )
                else:
                    self.list_widget.setCurrentRow(max(current_row - 1, 0))
                return True

            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                self.choose_current()
                return True

        return super().eventFilter(obj, event)


# =========================================================
# ADMİN ŞİFRESİ KURULUM VE GİRİŞ DİYALOGLARI
# =========================================================

class AdminSetupDialog(QDialog):
    """
    Uygulama ilk kez çalıştırıldığında (henüz admin şifresi
    belirlenmemişse) gösterilir. Şifre belirlenmeden kapatılamaz.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("İlk Kurulum - Admin Şifresi")
        self.setModal(True)
        self.setMinimumWidth(380)

        layout = QVBoxLayout(self)

        info_label = QLabel(
            "Uygulamayı ilk kez çalıştırıyorsunuz.\n"
            "Yönetim Paneli'ne (Ayarlar) erişim için bir admin "
            "şifresi belirleyin."
        )
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        form = QFormLayout()

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)

        self.confirm_edit = QLineEdit()
        self.confirm_edit.setEchoMode(QLineEdit.Password)

        form.addRow("Admin Şifresi:", self.password_edit)
        form.addRow("Şifre (Tekrar):", self.confirm_edit)
        layout.addLayout(form)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #EF4444;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.try_accept)
        layout.addWidget(buttons)

        self.password = None

    def try_accept(self):
        p1 = self.password_edit.text()
        p2 = self.confirm_edit.text()

        if len(p1) < 4:
            self.error_label.setText("Şifre en az 4 karakter olmalıdır.")
            return

        if p1 != p2:
            self.error_label.setText("Girdiğiniz şifreler eşleşmiyor.")
            self.confirm_edit.clear()
            return

        self.password = p1
        self.accept()

    def closeEvent(self, event):
        # Admin şifresi belirlenmeden pencere kapatılıp atlanamasın
        event.ignore()


class AdminLoginDialog(QDialog):
    """Yönetim Paneli'ne (Ayarlar) girerken admin şifresi ister."""

    def __init__(self, db, parent=None):
        super().__init__(parent)

        self.db = db

        self.setWindowTitle("Yönetim Paneli Girişi")
        self.setModal(True)
        self.setMinimumWidth(340)

        layout = QVBoxLayout(self)

        layout.addWidget(
            QLabel("Bu alana girmek için admin şifresini giriniz:")
        )

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.returnPressed.connect(self.try_accept)
        layout.addWidget(self.password_edit)

        self.error_label = QLabel("")
        self.error_label.setStyleSheet("color: #EF4444;")
        layout.addWidget(self.error_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.try_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.password_edit.setFocus()

    def try_accept(self):
        if self.db.verify_admin_password(self.password_edit.text()):
            self.accept()
        else:
            self.error_label.setText("Şifre hatalı, tekrar deneyin.")
            self.password_edit.clear()
            self.password_edit.setFocus()


class LibraryApp(QMainWindow):

    def __init__(self):

        super().__init__()

        self.db = Database()

        self.setWindowTitle(
            "Kütüphane Takip Sistemi"
        )

        self.resize(
            1400,
            850
        )

        # Sidebar navigasyonu ve tema durumunu tutan yapılar
        self.nav_buttons = {}
        self._accordion_widgets = set()
        self.is_dark_mode = False

        # Yönetim Paneli (Ayarlar) bu oturumda şifreyle açıldı mı?
        self.admin_unlocked = False

        # İlk çalıştırma: admin şifresi henüz belirlenmemişse,
        # belirlenene kadar bu diyalog kapatılamaz.
        while not self.db.is_admin_password_set():
            setup_dialog = AdminSetupDialog(self)
            setup_dialog.exec()

            if setup_dialog.password:
                self.db.set_admin_password(setup_dialog.password)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        root_layout.addWidget(self.create_sidebar())

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.setObjectName("ContentStack")
        root_layout.addWidget(self.stacked_widget, 1)

        self.create_home_tab()
        self.create_books_tab()
        self.create_members_tab()
        self.create_add_book_tab()
        self.create_add_member_tab()
        self.create_loan_tab()
        self.create_return_tab()
        self.create_overdue_tab()
        self.create_reports_tab()
        self.create_export_tab()
        self.create_settings_tab()

        self.sidebar_nav_layout.addStretch()

        self.stacked_widget.currentChanged.connect(
            self.tab_changed
        )

        self.apply_theme()

        self.refresh_users_everywhere()

        self.go_to(self.home_tab)

        self.refresh_all()

        self.setup_shortcuts()

    # =====================================================
    # KLAVYE KISAYOLLARI (Ctrl+F / Ctrl+K)
    # =====================================================

    def setup_shortcuts(self):

        # Sayfa -> o sayfadaki birincil arama kutusu eşlemesi.
        # Yeni bir arama kutusu eklenirse buraya bir satır eklemek yeterli.
        self.page_search_fields = {
            self.books_tab: self.book_search_edit,
            self.members_tab: self.member_search_edit,
            self.loan_tab: self.loan_member_search_edit,
            self.return_tab: self.return_member_search_edit,
        }

        self.search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        self.search_shortcut.activated.connect(self.focus_current_search_field)

        self.palette_shortcut = QShortcut(QKeySequence("Ctrl+K"), self)
        self.palette_shortcut.activated.connect(self.open_command_palette)

    def focus_current_search_field(self):

        current_widget = self.stacked_widget.currentWidget()
        search_field = self.page_search_fields.get(current_widget)

        if search_field is not None:
            search_field.setFocus()
            search_field.selectAll()

    def open_command_palette(self):

        pages = [
            (button.text().strip(), widget)
            for widget, button in self.nav_buttons.items()
        ]

        dialog = CommandPaletteDialog(pages, self)

        if dialog.exec() == QDialog.Accepted and dialog.selected_widget is not None:
            self.go_to(dialog.selected_widget)

    # =====================================================
    # SOL NAVİGASYON (SIDEBAR) + AKORDEON + TEMA
    # =====================================================

    def create_sidebar(self):

        sidebar = QFrame()
        sidebar.setObjectName("SidebarFrame")
        sidebar.setFixedWidth(250)

        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(14, 20, 14, 20)
        layout.setSpacing(6)

        title = QLabel("📚 Kütüphane Takip")
        title.setObjectName("AppTitle")
        title.setWordWrap(True)
        layout.addWidget(title)

        self.theme_toggle_button = QPushButton("🌙  Karanlık Moda Geç")
        self.theme_toggle_button.setObjectName("ThemeToggleButton")
        self.theme_toggle_button.setCheckable(True)
        self.theme_toggle_button.clicked.connect(self.toggle_theme)
        layout.addWidget(self.theme_toggle_button)

        layout.addSpacing(12)

        # ---- İşlemi yapan kullanıcı (basit, şifresiz seçim) ----
        active_user_label = QLabel("İşlemi Yapan Kullanıcı")
        active_user_label.setObjectName("SidebarSectionLabel")
        layout.addWidget(active_user_label)

        self.active_user_combo = QComboBox()
        self.active_user_combo.currentIndexChanged.connect(
            self.on_active_user_changed
        )
        layout.addWidget(self.active_user_combo)

        layout.addSpacing(12)

        # Normal (akordeon dışı) navigasyon butonlarının ekleneceği alan
        self.sidebar_nav_layout = QVBoxLayout()
        self.sidebar_nav_layout.setSpacing(4)
        layout.addLayout(self.sidebar_nav_layout)

        layout.addSpacing(10)

        # ---- Akordeon: Yönetim Paneli ----
        self.accordion_header_button = QPushButton("▸  Yönetim Paneli")
        self.accordion_header_button.setObjectName("AccordionHeaderButton")
        self.accordion_header_button.setCheckable(True)
        self.accordion_header_button.clicked.connect(self.toggle_accordion)
        layout.addWidget(self.accordion_header_button)

        self.accordion_container = QWidget()
        self.accordion_container.setObjectName("AccordionContainer")
        self.accordion_layout = QVBoxLayout(self.accordion_container)
        self.accordion_layout.setContentsMargins(14, 4, 0, 4)
        self.accordion_layout.setSpacing(4)

        self.accordion_container.setMaximumHeight(0)
        self.accordion_container.setMinimumHeight(0)

        layout.addWidget(self.accordion_container)

        self._accordion_animation = QPropertyAnimation(
            self.accordion_container, b"maximumHeight"
        )
        self._accordion_animation.setDuration(220)
        self._accordion_animation.setEasingCurve(QEasingCurve.InOutCubic)

        layout.addStretch()

        return sidebar

    def _add_page(self, widget, title, in_accordion=False):

        index = self.stacked_widget.addWidget(widget)

        button = QPushButton(title)
        button.setCheckable(True)
        button.setProperty("class", "nav-btn")
        button.setProperty("accordionItem", in_accordion)
        button.clicked.connect(lambda checked=False, w=widget: self.go_to(w))

        self.nav_buttons[widget] = button

        if in_accordion:
            self._accordion_widgets.add(widget)
            self.accordion_layout.addWidget(button)
        else:
            self.sidebar_nav_layout.addWidget(button)

        return index

    def go_to(self, widget):

        if widget is self.settings_tab and not self.admin_unlocked:

            login_dialog = AdminLoginDialog(self.db, self)

            if login_dialog.exec() != QDialog.Accepted:
                # Girişten vazgeçildi / şifre doğrulanamadı:
                # navigasyonu iptal edip buton durumlarını eski
                # (mevcut) sayfaya göre düzelt.
                current_widget = self.stacked_widget.currentWidget()

                for page_widget, button in self.nav_buttons.items():
                    button.setChecked(page_widget is current_widget)

                return

            self.admin_unlocked = True

        self.stacked_widget.setCurrentWidget(widget)

        for page_widget, button in self.nav_buttons.items():
            button.setChecked(page_widget is widget)

        if widget in self._accordion_widgets:
            self.set_accordion_expanded(True)

    def on_active_user_changed(self):
        self.db.current_user_id = self.active_user_combo.currentData()

    def refresh_active_users_combo(self):

        current_id = self.active_user_combo.currentData()

        self.active_user_combo.blockSignals(True)
        self.active_user_combo.clear()
        self.active_user_combo.addItem("— Belirtilmedi —", None)

        select_index = 0

        for index, user in enumerate(self.db.get_active_users(), start=1):
            self.active_user_combo.addItem(user["username"], user["id"])

            if user["id"] == current_id:
                select_index = index

        self.active_user_combo.setCurrentIndex(select_index)
        self.active_user_combo.blockSignals(False)

        self.on_active_user_changed()

    def refresh_users_everywhere(self):
        self.refresh_active_users_combo()
        self.refresh_users_table()

    def toggle_accordion(self):
        self.set_accordion_expanded(
            self.accordion_header_button.isChecked()
        )

    def set_accordion_expanded(self, expanded):

        self.accordion_header_button.setChecked(expanded)
        self.accordion_header_button.setText(
            ("▾" if expanded else "▸") + "  Yönetim Paneli"
        )

        target_height = (
            self.accordion_container.sizeHint().height() if expanded else 0
        )

        self._accordion_animation.stop()
        self._accordion_animation.setStartValue(
            self.accordion_container.maximumHeight()
        )
        self._accordion_animation.setEndValue(target_height)
        self._accordion_animation.start()

    def toggle_theme(self):
        self.is_dark_mode = self.theme_toggle_button.isChecked()
        self.apply_theme()

    def apply_theme(self):

        style = DARK_THEME_QSS if self.is_dark_mode else LIGHT_THEME_QSS

        app_instance = QApplication.instance()
        if app_instance is not None:
            app_instance.setStyleSheet(style)
        else:
            self.setStyleSheet(style)

        if self.is_dark_mode:
            self.theme_toggle_button.setText("☀  Aydınlık Moda Geç")
        else:
            self.theme_toggle_button.setText("🌙  Karanlık Moda Geç")

    # =====================================================
    # ANA SAYFA
    # =====================================================

    def create_home_tab(self):

        self.home_tab = QWidget()
        layout = QVBoxLayout(
            self.home_tab
        )

        title = QLabel(
            "Kütüphane Takip Sistemi"
        )

        title.setStyleSheet(
            "font-size: 26px; font-weight: bold;"
        )

        layout.addWidget(title)

        subtitle = QLabel(
            "Kitap, fiziksel nüsha, üye, ödünç ve iade işlemlerini yönetin."
        )

        layout.addWidget(
            subtitle
        )

        grid = QGridLayout()

        self.stat_labels = {}

        stats = [
            ("works", "Kitap Eseri"),
            ("copies", "Fiziksel Nüsha"),
            ("available", "Mevcut"),
            ("borrowed", "Ödünçte"),
            ("overdue", "Geciken"),
            ("lost", "Kayıp"),
            ("damaged", "Hasarlı"),
            ("members", "Toplam Üye"),
            ("active_members", "Aktif Üye"),
        ]

        for index, (key, text) in enumerate(stats):

            box = QGroupBox(text)

            box_layout = QVBoxLayout(
                box
            )

            label = QLabel("0")

            label.setAlignment(
                Qt.AlignCenter
            )

            label.setStyleSheet(
                "font-size: 28px; font-weight: bold;"
            )

            box_layout.addWidget(
                label
            )

            self.stat_labels[key] = label

            row = index // 3
            col = index % 3

            grid.addWidget(
                box,
                row,
                col
            )

        layout.addLayout(
            grid
        )

        overdue_button = QPushButton(
            "Geciken Kitapları Gör"
        )

        overdue_button.clicked.connect(
            lambda: self.go_to(self.overdue_tab)
        )

        layout.addWidget(
            overdue_button
        )

        layout.addStretch()

        self._add_page(self.home_tab, "🏠  Ana Sayfa", in_accordion=False)

    # =====================================================
    # KİTAPLAR
    # =====================================================

    def create_books_tab(self):

        self.books_tab = QWidget()

        layout = QVBoxLayout(
            self.books_tab
        )

        top = QHBoxLayout()

        self.book_search_edit = QLineEdit()

        self.book_search_edit.setPlaceholderText(
            "ISBN / barkod / Kitap Numarası / kitap adı / yazar..."
        )

        self.book_search_button = QPushButton(
            "Ara"
        )

        self.book_search_button.clicked.connect(
            self.refresh_books
        )

        self.book_search_edit.returnPressed.connect(
            self.refresh_books
        )

        lookup_button = QPushButton(
            "ISBN / Barkod ile Kitap Bilgisi Ara"
        )

        lookup_button.clicked.connect(
            self.open_isbn_lookup
        )

        add_button = QPushButton(
            "Yeni Kitap Ekle"
        )

        add_button.clicked.connect(
            lambda: self.go_to(self.add_book_tab)
        )

        top.addWidget(
            self.book_search_edit
        )

        top.addWidget(
            self.book_search_button
        )

        top.addWidget(
            lookup_button
        )

        top.addWidget(
            add_button
        )

        layout.addLayout(
            top
        )

        splitter = QSplitter(
            Qt.Vertical
        )

        self.books_table = QTableWidget()

        self.books_table.setColumnCount(7)

        self.books_table.setHorizontalHeaderLabels([
            "ID",
            "ISBN",
            "Kitap",
            "Yazar",
            "Eser Durumu",
            "Nüsha",
            "Mevcut"
        ])

        self.books_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.books_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.books_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.books_table.itemSelectionChanged.connect(
            self.book_selected
        )

        self.books_table.cellDoubleClicked.connect(
            self.show_book_details
        )

        splitter.addWidget(
            self.books_table
        )

        bottom = QWidget()

        bottom_layout = QVBoxLayout(
            bottom
        )

        self.selected_book_label = QLabel(
            "Kitap seçilmedi."
        )

        bottom_layout.addWidget(
            self.selected_book_label
        )

        self.copy_table = QTableWidget()

        self.copy_table.setColumnCount(5)

        self.copy_table.setHorizontalHeaderLabels([
            "ID",
            "Kitap No",
            "Raf",
            "Durum",
            "Not"
        ])

        self.copy_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.copy_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        bottom_layout.addWidget(
            self.copy_table
        )

        buttons = QHBoxLayout()

        self.add_copy_button = QPushButton(
            "Seçili Kitaba Fiziksel Nüsha Ekle"
        )

        self.add_copy_button.clicked.connect(
            self.add_copy_to_selected_book
        )

        details_button = QPushButton(
            "Detay / Geçmiş"
        )

        details_button.clicked.connect(
            self.open_selected_book_details
        )

        buttons.addWidget(
            self.add_copy_button
        )

        buttons.addWidget(
            details_button
        )

        bottom_layout.addLayout(
            buttons
        )

        splitter.addWidget(
            bottom
        )

        layout.addWidget(
            splitter
        )

        self._add_page(self.books_tab, "📚  Kitaplar", in_accordion=False)

    def refresh_books(self):

        text = self.book_search_edit.text()

        books = self.db.search_books(
            text
        )

        self.books_table.setRowCount(
            len(books)
        )

        for r, book in enumerate(books):

            values = [
                book["id"],
                book["isbn"] or "-",
                book["title"],
                book["author"] or "-",
                book["status"],
                book["copy_count"] or 0,
                book["available_count"] or 0
            ]

            for c, value in enumerate(values):
                self.books_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )

        self.copy_table.setRowCount(0)

        self.selected_book_label.setText(
            "Kitap seçilmedi."
        )

    def book_selected(self):

        row = self.books_table.currentRow()

        if row < 0:
            return

        book_id = int(
            self.books_table.item(
                row,
                0
            ).text()
        )

        book = self.db.get_book(
            book_id
        )

        if not book:
            return

        self.selected_book_label.setText(
            f"Seçili kitap: "
            f"{book['title']} | "
            f"ISBN: {book['isbn'] or '-'}"
        )

        copies = self.db.get_book_copies(
            book_id
        )

        self.copy_table.setRowCount(
            len(copies)
        )

        for r, copy in enumerate(copies):

            values = [
                copy["id"],
                copy["book_number"] or "-",
                copy["shelf"] or "-",
                copy["status"],
                copy["notes"] or "-"
            ]

            for c, value in enumerate(values):
                self.copy_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )

    def show_book_details(self, row, column):

        item = self.books_table.item(
            row,
            0
        )

        if not item:
            return

        dialog = BookDetailsDialog(
            self.db,
            int(item.text()),
            self
        )

        dialog.exec()

    def open_selected_book_details(self):

        row = self.books_table.currentRow()

        if row < 0:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Önce bir kitap seçin."
            )
            return

        book_id = int(
            self.books_table.item(
                row,
                0
            ).text()
        )

        dialog = BookDetailsDialog(
            self.db,
            book_id,
            self
        )

        dialog.exec()

    def add_copy_to_selected_book(self):

        row = self.books_table.currentRow()

        if row < 0:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Önce bir kitap seçin."
            )
            return

        book_id = int(
            self.books_table.item(
                row,
                0
            ).text()
        )

        book = self.db.get_book(
            book_id
        )

        dialog = QDialog(
            self
        )

        dialog.setWindowTitle(
            "Fiziksel Nüsha Ekle"
        )

        form = QFormLayout(
            dialog
        )

        number_edit = QLineEdit()
        shelf_edit = QLineEdit()
        notes_edit = QLineEdit()

        form.addRow(
            "Kitap:",
            QLabel(book["title"])
        )

        form.addRow(
            "Kitap Numarası:",
            number_edit
        )

        form.addRow(
            "Raf:",
            shelf_edit
        )

        form.addRow(
            "Not:",
            notes_edit
        )

        info = QLabel(
            "Kitap Numarası isteğe bağlıdır."
        )

        form.addRow(
            "",
            info
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.Save |
            QDialogButtonBox.Cancel
        )

        buttons.accepted.connect(
            dialog.accept
        )

        buttons.rejected.connect(
            dialog.reject
        )

        form.addRow(
            buttons
        )

        if dialog.exec() != QDialog.Accepted:
            return

        try:
            self.db.add_copy(
                book_id,
                number_edit.text(),
                shelf_edit.text(),
                "Mevcut",
                notes_edit.text()
            )

            QMessageBox.information(
                self,
                "Başarılı",
                "Fiziksel nüsha eklendi."
            )

            self.refresh_books()
            self.refresh_home()

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Hata",
                str(exc)
            )

    def open_isbn_lookup(self):

        dialog = ISBNLookupDialog(
            self
        )

        if dialog.exec() == QDialog.Accepted:

            data = dialog.information_found

            if not data:
                return

            self.go_to(self.add_book_tab)

            self.fill_book_form(
                data
            )

    # =====================================================
    # KİTAP EKLE
    # =====================================================

    def create_add_book_tab(self):

        self.add_book_tab = QWidget()

        layout = QVBoxLayout(
            self.add_book_tab
        )

        title = QLabel(
            "Yeni Kitap / Fiziksel Nüsha Kaydı"
        )

        title.setStyleSheet(
            "font-size: 22px; font-weight: bold;"
        )

        layout.addWidget(
            title
        )

        form = QFormLayout()

        self.add_isbn_edit = QLineEdit()

        self.add_title_edit = QLineEdit()
        self.add_author_edit = QLineEdit()
        self.add_publisher_edit = QLineEdit()

        self.add_year_edit = QSpinBox()
        self.add_year_edit.setRange(
            0,
            3000
        )

        self.add_edition_edit = QLineEdit()
        self.add_language_edit = QLineEdit()
        self.add_category_edit = QLineEdit()

        self.add_description_edit = QTextEdit()

        self.add_book_number_edit = QLineEdit()
        self.add_shelf_edit = QLineEdit()
        self.add_copy_notes_edit = QLineEdit()

        form.addRow(
            "ISBN / Barkod:",
            self.add_isbn_edit
        )

        form.addRow(
            "Kitap Adı:",
            self.add_title_edit
        )

        form.addRow(
            "Yazar:",
            self.add_author_edit
        )

        form.addRow(
            "Yayınevi:",
            self.add_publisher_edit
        )

        form.addRow(
            "Yayın Yılı:",
            self.add_year_edit
        )

        form.addRow(
            "Baskı:",
            self.add_edition_edit
        )

        form.addRow(
            "Dil:",
            self.add_language_edit
        )

        form.addRow(
            "Kategori:",
            self.add_category_edit
        )

        form.addRow(
            "Açıklama:",
            self.add_description_edit
        )

        form.addRow(
            "Kitap Numarası:",
            self.add_book_number_edit
        )

        form.addRow(
            "Raf:",
            self.add_shelf_edit
        )

        form.addRow(
            "Nüsha Notu:",
            self.add_copy_notes_edit
        )

        layout.addLayout(
            form
        )

        info = QLabel(
            "Not: Kitap Numarası fiziksel nüshaya aittir ve isteğe bağlıdır. "
            "Aynı ISBN için birden fazla fiziksel nüsha eklenebilir."
        )

        info.setWordWrap(True)

        layout.addWidget(
            info
        )

        buttons = QHBoxLayout()

        save_button = QPushButton(
            "Kitabı Kaydet"
        )

        clear_button = QPushButton(
            "Temizle"
        )

        save_button.clicked.connect(
            self.save_book
        )

        clear_button.clicked.connect(
            self.clear_book_form
        )

        buttons.addWidget(
            save_button
        )

        buttons.addWidget(
            clear_button
        )

        buttons.addStretch()

        layout.addLayout(
            buttons
        )

        layout.addStretch()

        self._add_page(self.add_book_tab, "➕  Kitap Ekle", in_accordion=False)

    def fill_book_form(self, data):

        self.add_isbn_edit.setText(
            data.get("isbn", "")
        )

        self.add_title_edit.setText(
            data.get("title", "")
        )

        self.add_author_edit.setText(
            data.get("author", "")
        )

        self.add_publisher_edit.setText(
            data.get("publisher", "")
        )

        year = data.get(
            "publication_year",
            ""
        )

        match = re.search(
            r"\d{4}",
            str(year)
        )

        if match:
            self.add_year_edit.setValue(
                int(match.group())
            )

        self.add_language_edit.setText(
            data.get("language", "")
        )

        self.add_description_edit.setPlainText(
            data.get("description", "")
        )

    def clear_book_form(self):

        self.add_isbn_edit.clear()
        self.add_title_edit.clear()
        self.add_author_edit.clear()
        self.add_publisher_edit.clear()
        self.add_year_edit.setValue(0)
        self.add_edition_edit.clear()
        self.add_language_edit.clear()
        self.add_category_edit.clear()
        self.add_description_edit.clear()
        self.add_book_number_edit.clear()
        self.add_shelf_edit.clear()
        self.add_copy_notes_edit.clear()

    def save_book(self):

        isbn = normalize_isbn(
            self.add_isbn_edit.text()
        )

        title = self.add_title_edit.text().strip()

        if not title:
            QMessageBox.warning(
                self,
                "Eksik Bilgi",
                "Kitap adı zorunludur."
            )
            return

        existing = None

        if isbn:
            existing = self.db.find_book_by_isbn(
                isbn
            )

        if existing:

            answer = QMessageBox.question(
                self,
                "ISBN zaten kayıtlı",
                "Bu ISBN zaten kayıtlı.\n\n"
                "Yeni bir kitap eseri oluşturmak yerine "
                "mevcut kitaba fiziksel nüsha eklemek ister misiniz?"
            )

            if answer != QMessageBox.Yes:
                return

            try:
                self.db.add_copy(
                    existing["id"],
                    self.add_book_number_edit.text(),
                    self.add_shelf_edit.text(),
                    "Mevcut",
                    self.add_copy_notes_edit.text()
                )

                QMessageBox.information(
                    self,
                    "Başarılı",
                    "Mevcut kitaba fiziksel nüsha eklendi."
                )

                self.clear_book_form()
                self.refresh_books()
                self.refresh_home()

            except Exception as exc:
                QMessageBox.critical(
                    self,
                    "Hata",
                    str(exc)
                )

            return

        year = self.add_year_edit.value()

        if year == 0:
            year = None

        try:

            book_id = self.db.add_book(
                isbn,
                title,
                self.add_author_edit.text(),
                self.add_publisher_edit.text(),
                year,
                self.add_edition_edit.text(),
                self.add_language_edit.text(),
                self.add_category_edit.text(),
                self.add_description_edit.toPlainText()
            )

            self.db.add_copy(
                book_id,
                self.add_book_number_edit.text(),
                self.add_shelf_edit.text(),
                "Mevcut",
                self.add_copy_notes_edit.text()
            )

            QMessageBox.information(
                self,
                "Başarılı",
                "Kitap ve fiziksel nüsha kaydedildi."
            )

            self.clear_book_form()
            self.refresh_books()
            self.refresh_home()

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Hata",
                str(exc)
            )

    # =====================================================
    # ÜYELER
    # =====================================================

    def create_members_tab(self):

        self.members_tab = QWidget()

        layout = QVBoxLayout(
            self.members_tab
        )

        top = QHBoxLayout()

        self.member_search_edit = QLineEdit()

        self.member_search_edit.setPlaceholderText(
            "Üye No / ad / soyad / tam ad / telefon..."
        )

        search_button = QPushButton(
            "Ara"
        )

        search_button.clicked.connect(
            self.refresh_members
        )

        self.member_search_edit.returnPressed.connect(
            self.refresh_members
        )

        add_button = QPushButton(
            "Yeni Üye Ekle"
        )

        add_button.clicked.connect(
            lambda: self.go_to(self.add_member_tab)
        )

        top.addWidget(
            self.member_search_edit
        )

        top.addWidget(
            search_button
        )

        top.addWidget(
            add_button
        )

        layout.addLayout(
            top
        )

        self.members_table = QTableWidget()

        self.members_table.setColumnCount(7)

        self.members_table.setHorizontalHeaderLabels([
            "ID",
            "Üye No",
            "Ad",
            "Soyad",
            "Telefon",
            "Durum",
            "Kayıt Tarihi"
        ])

        self.members_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.members_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.members_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.members_table.cellDoubleClicked.connect(
            self.show_member_details
        )

        layout.addWidget(
            self.members_table
        )

        buttons = QHBoxLayout()

        detail_button = QPushButton(
            "Üye Detayı / Geçmiş"
        )

        detail_button.clicked.connect(
            self.open_selected_member
        )

        buttons.addWidget(
            detail_button
        )

        layout.addLayout(
            buttons
        )

        self._add_page(self.members_tab, "👥  Üyeler", in_accordion=False)

    def refresh_members(self):

        members = self.db.search_members(
            self.member_search_edit.text()
        )

        self.members_table.setRowCount(
            len(members)
        )

        for r, member in enumerate(members):

            values = [
                member["id"],
                member["member_number"] or "-",
                member["first_name"],
                member["last_name"],
                member["phone"] or "-",
                member["status"],
                display_datetime(
                    member["registration_date"]
                )
            ]

            for c, value in enumerate(values):
                self.members_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )

    def show_member_details(self, row, column):

        item = self.members_table.item(
            row,
            0
        )

        if not item:
            return

        dialog = MemberDetailsDialog(
            self.db,
            int(item.text()),
            self
        )

        dialog.exec()

        self.refresh_home()

    def open_selected_member(self):

        row = self.members_table.currentRow()

        if row < 0:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Önce bir üye seçin."
            )
            return

        member_id = int(
            self.members_table.item(
                row,
                0
            ).text()
        )

        dialog = MemberDetailsDialog(
            self.db,
            member_id,
            self
        )

        dialog.exec()

        self.refresh_home()

    # =====================================================
    # ÜYE EKLE
    # =====================================================

    def create_add_member_tab(self):

        self.add_member_tab = QWidget()

        layout = QVBoxLayout(
            self.add_member_tab
        )

        title = QLabel(
            "Yeni Üye Ekle"
        )

        title.setStyleSheet(
            "font-size: 22px; font-weight: bold;"
        )

        layout.addWidget(
            title
        )

        form = QFormLayout()

        self.member_number_edit = QLineEdit()
        self.member_first_name_edit = QLineEdit()
        self.member_last_name_edit = QLineEdit()
        self.member_phone_edit = QLineEdit()
        self.member_email_edit = QLineEdit()
        self.member_notes_edit = QTextEdit()

        form.addRow(
            "Üye Numarası:",
            self.member_number_edit
        )

        form.addRow(
            "Ad:",
            self.member_first_name_edit
        )

        form.addRow(
            "Soyad:",
            self.member_last_name_edit
        )

        form.addRow(
            "Telefon:",
            self.member_phone_edit
        )

        form.addRow(
            "E-posta:",
            self.member_email_edit
        )

        form.addRow(
            "Not:",
            self.member_notes_edit
        )

        layout.addLayout(
            form
        )

        info = QLabel(
            "Üye Numarası isteğe bağlıdır."
        )

        layout.addWidget(
            info
        )

        buttons = QHBoxLayout()

        save_button = QPushButton(
            "Üyeyi Kaydet"
        )

        clear_button = QPushButton(
            "Temizle"
        )

        save_button.clicked.connect(
            self.save_member
        )

        clear_button.clicked.connect(
            self.clear_member_form
        )

        buttons.addWidget(
            save_button
        )

        buttons.addWidget(
            clear_button
        )

        buttons.addStretch()

        layout.addLayout(
            buttons
        )

        layout.addStretch()

        self._add_page(self.add_member_tab, "➕  Üye Ekle", in_accordion=False)

    def save_member(self):

        first_name = self.member_first_name_edit.text().strip()
        last_name = self.member_last_name_edit.text().strip()

        if not first_name or not last_name:

            QMessageBox.warning(
                self,
                "Eksik Bilgi",
                "Ad ve soyad zorunludur."
            )

            return

        try:

            self.db.add_member(
                self.member_number_edit.text(),
                first_name,
                last_name,
                self.member_phone_edit.text(),
                self.member_email_edit.text(),
                self.member_notes_edit.toPlainText()
            )

            QMessageBox.information(
                self,
                "Başarılı",
                "Üye kaydedildi."
            )

            self.clear_member_form()
            self.refresh_members()
            self.refresh_home()

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Hata",
                str(exc)
            )

    def clear_member_form(self):

        self.member_number_edit.clear()
        self.member_first_name_edit.clear()
        self.member_last_name_edit.clear()
        self.member_phone_edit.clear()
        self.member_email_edit.clear()
        self.member_notes_edit.clear()

    # =====================================================
    # ÖDÜNÇ VERME
    # =====================================================

    def create_loan_tab(self):

        self.loan_tab = QWidget()

        layout = QVBoxLayout(
            self.loan_tab
        )

        title = QLabel(
            "Kitap Ödünç Verme"
        )

        title.setStyleSheet(
            "font-size: 22px; font-weight: bold;"
        )

        layout.addWidget(
            title
        )

        # Üye
        member_group = QGroupBox(
            "1. Üyeyi Bul"
        )

        member_layout = QVBoxLayout(
            member_group
        )

        member_search = QHBoxLayout()

        self.loan_member_search_edit = QLineEdit()

        self.loan_member_search_edit.setPlaceholderText(
            "Üye numarası, ad, soyad veya telefon..."
        )

        member_search_button = QPushButton(
            "Üye Ara"
        )

        member_search_button.clicked.connect(
            self.search_loan_members
        )

        member_search.addWidget(
            self.loan_member_search_edit
        )

        member_search.addWidget(
            member_search_button
        )

        member_layout.addLayout(
            member_search
        )

        self.loan_member_table = QTableWidget()

        self.loan_member_table.setColumnCount(5)

        self.loan_member_table.setHorizontalHeaderLabels([
            "ID",
            "Üye No",
            "Ad Soyad",
            "Telefon",
            "Durum"
        ])

        self.loan_member_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.loan_member_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.loan_member_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.loan_member_table.itemSelectionChanged.connect(
            self.loan_member_selected
        )

        member_layout.addWidget(
            self.loan_member_table
        )

        self.loan_selected_member_label = QLabel(
            "Seçili üye: Yok"
        )

        member_layout.addWidget(
            self.loan_selected_member_label
        )

        layout.addWidget(
            member_group
        )

        # Kitap
        book_group = QGroupBox(
            "2. Kitabı Bul"
        )

        book_layout = QVBoxLayout(
            book_group
        )

        book_search = QHBoxLayout()

        self.loan_book_search_edit = QLineEdit()

        self.loan_book_search_edit.setPlaceholderText(
            "ISBN / barkod / Kitap Numarası okutun veya girin..."
        )

        book_search_button = QPushButton(
            "Kitabı Bul"
        )

        book_search_button.clicked.connect(
            self.search_loan_book
        )

        self.loan_book_search_edit.returnPressed.connect(
            self.search_loan_book
        )

        book_search.addWidget(
            self.loan_book_search_edit
        )

        book_search.addWidget(
            book_search_button
        )

        book_layout.addLayout(
            book_search
        )

        self.loan_copy_table = QTableWidget()

        self.loan_copy_table.setColumnCount(6)

        self.loan_copy_table.setHorizontalHeaderLabels([
            "ID",
            "Kitap No",
            "Kitap",
            "ISBN",
            "Yazar",
            "Durum"
        ])

        self.loan_copy_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.loan_copy_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.loan_copy_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.loan_copy_table.itemSelectionChanged.connect(
            self.loan_copy_selected
        )

        book_layout.addWidget(
            self.loan_copy_table
        )

        self.loan_selected_book_label = QLabel(
            "Seçili kitap: Yok"
        )

        book_layout.addWidget(
            self.loan_selected_book_label
        )

        layout.addWidget(
            book_group
        )

        # Tarih
        options = QGroupBox(
            "3. Ödünç Bilgileri"
        )

        options_layout = QFormLayout(
            options
        )

        self.loan_due_date_edit = QDateEdit()

        self.loan_due_date_edit.setCalendarPopup(
            True
        )

        self.loan_due_date_edit.setDate(
            QDate.currentDate().addDays(14)
        )

        self.loan_notes_edit = QLineEdit()

        options_layout.addRow(
            "Son İade Tarihi:",
            self.loan_due_date_edit
        )

        options_layout.addRow(
            "Not:",
            self.loan_notes_edit
        )

        layout.addWidget(
            options
        )

        self.borrow_button = QPushButton(
            "ÖDÜNÇ VER"
        )

        self.borrow_button.setMinimumHeight(
            45
        )

        self.borrow_button.clicked.connect(
            self.borrow_selected
        )

        layout.addWidget(
            self.borrow_button
        )

        self._add_page(self.loan_tab, "📖  Ödünç Verme", in_accordion=False)

    def search_loan_members(self):

        members = self.db.search_members(
            self.loan_member_search_edit.text()
        )

        self.loan_member_table.setRowCount(
            len(members)
        )

        for r, member in enumerate(members):

            values = [
                member["id"],
                member["member_number"] or "-",
                f"{member['first_name']} {member['last_name']}",
                member["phone"] or "-",
                member["status"]
            ]

            for c, value in enumerate(values):
                self.loan_member_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )

    def loan_member_selected(self):

        row = self.loan_member_table.currentRow()

        if row < 0:
            return

        member_id = int(
            self.loan_member_table.item(
                row,
                0
            ).text()
        )

        member = self.db.get_member(
            member_id
        )

        if member:

            self.loan_selected_member_label.setText(
                f"Seçili üye: "
                f"{member['first_name']} "
                f"{member['last_name']} "
                f"({member['member_number'] or 'Numarasız'})"
            )

    def search_loan_book(self):

        value = self.loan_book_search_edit.text().strip()

        self.loan_copy_table.setRowCount(
            0
        )

        if not value:
            return

        copy = self.db.get_copy_by_number(
            value
        )

        if copy:

            copies = [copy]

        else:

            isbn = normalize_isbn(
                value
            )

            copies = self.db.get_available_copies_by_isbn(
                isbn
            )

            # Eğer barkod/ISBN ile mevcut olmayanlar da
            # görülmek isteniyorsa ayrı olarak tüm nüshaları
            # gösteriyoruz.
            if not copies and is_valid_isbn(isbn):
                copies = self.db.get_copies_by_isbn(
                    isbn
                )

        self.loan_copy_table.setRowCount(
            len(copies)
        )

        for r, copy in enumerate(copies):

            values = [
                copy["id"],
                copy["book_number"] or "-",
                copy["title"],
                copy["isbn"] or "-",
                copy["author"] or "-",
                copy["status"]
            ]

            for c, value in enumerate(values):
                self.loan_copy_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )

    def loan_copy_selected(self):

        row = self.loan_copy_table.currentRow()

        if row < 0:
            return

        copy_id = int(
            self.loan_copy_table.item(
                row,
                0
            ).text()
        )

        copy = self.db.get_copy(
            copy_id
        )

        if copy:

            self.loan_selected_book_label.setText(
                f"Seçili kitap: "
                f"{copy['title']} | "
                f"Kitap No: {copy['book_number'] or '-'} | "
                f"Durum: {copy['status']}"
            )

    def borrow_selected(self):

        member_row = self.loan_member_table.currentRow()
        copy_row = self.loan_copy_table.currentRow()

        if member_row < 0:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Önce üye seçin."
            )
            return

        if copy_row < 0:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Önce kitap nüshası seçin."
            )
            return

        member_id = int(
            self.loan_member_table.item(
                member_row,
                0
            ).text()
        )

        copy_id = int(
            self.loan_copy_table.item(
                copy_row,
                0
            ).text()
        )

        due_date = (
            self.loan_due_date_edit.date()
            .toString("yyyy-MM-dd")
            + " 23:59:59"
        )

        answer = QMessageBox.question(
            self,
            "Ödünç Onayı",
            "Seçilen kitabı seçilen üyeye ödünç vermek istiyor musunuz?"
        )

        if answer != QMessageBox.Yes:
            return

        try:

            self.db.borrow_book(
                copy_id,
                member_id,
                due_date,
                self.loan_notes_edit.text()
            )

            QMessageBox.information(
                self,
                "Başarılı",
                "Kitap ödünç verildi."
            )

            self.loan_copy_table.setRowCount(0)
            self.loan_selected_book_label.setText(
                "Seçili kitap: Yok"
            )

            self.refresh_books()
            self.refresh_home()
            self.refresh_overdue()

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Hata",
                str(exc)
            )

    # =====================================================
    # İADE
    # =====================================================

    def create_return_tab(self):

        self.return_tab = QWidget()

        layout = QVBoxLayout(
            self.return_tab
        )

        title = QLabel(
            "Kitap İade Alma"
        )

        title.setStyleSheet(
            "font-size: 22px; font-weight: bold;"
        )

        layout.addWidget(
            title
        )

        # Üye arama
        group = QGroupBox(
            "Üye Ara"
        )

        group_layout = QVBoxLayout(
            group
        )

        search_layout = QHBoxLayout()

        self.return_member_search_edit = QLineEdit()

        self.return_member_search_edit.setPlaceholderText(
            "Üye No / ad / soyad..."
        )

        return_member_search_button = QPushButton(
            "Ara"
        )

        return_member_search_button.clicked.connect(
            self.search_return_members
        )

        search_layout.addWidget(
            self.return_member_search_edit
        )

        search_layout.addWidget(
            return_member_search_button
        )

        group_layout.addLayout(
            search_layout
        )

        self.return_member_table = QTableWidget()

        self.return_member_table.setColumnCount(4)

        self.return_member_table.setHorizontalHeaderLabels([
            "ID",
            "Üye No",
            "Ad Soyad",
            "Durum"
        ])

        self.return_member_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.return_member_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.return_member_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.return_member_table.itemSelectionChanged.connect(
            self.return_member_selected
        )

        group_layout.addWidget(
            self.return_member_table
        )

        layout.addWidget(
            group
        )

        self.return_selected_member_label = QLabel(
            "Seçili üye: Yok"
        )

        layout.addWidget(
            self.return_selected_member_label
        )

        # Kitap/barkod arama
        book_search_group = QGroupBox(
            "Kitap / Barkod ile Bul"
        )

        book_search_layout = QHBoxLayout(
            book_search_group
        )

        self.return_book_search_edit = QLineEdit()

        self.return_book_search_edit.setPlaceholderText(
            "Kitap Numarası veya ISBN/barkod..."
        )

        return_book_button = QPushButton(
            "Bul"
        )

        return_book_button.clicked.connect(
            self.search_return_book
        )

        self.return_book_search_edit.returnPressed.connect(
            self.search_return_book
        )

        book_search_layout.addWidget(
            self.return_book_search_edit
        )

        book_search_layout.addWidget(
            return_book_button
        )

        layout.addWidget(
            book_search_group
        )

        self.return_book_result_label = QLabel(
            "Kitap sonucu: Yok"
        )

        layout.addWidget(
            self.return_book_result_label
        )

        current_group = QGroupBox(
            "Seçili Üyenin Üzerindeki Kitaplar"
        )

        current_layout = QVBoxLayout(
            current_group
        )

        self.return_loans_table = QTableWidget()

        self.return_loans_table.setColumnCount(7)

        self.return_loans_table.setHorizontalHeaderLabels([
            "Ödünç ID",
            "Kitap No",
            "Kitap",
            "ISBN",
            "Ödünç Tarihi",
            "Son İade",
            "Durum"
        ])

        self.return_loans_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.return_loans_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.return_loans_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        self.return_loans_table.itemSelectionChanged.connect(
            self.return_loan_selected
        )

        current_layout.addWidget(
            self.return_loans_table
        )

        self.return_selected_label = QLabel(
            "İade için seçili kayıt: Yok"
        )

        current_layout.addWidget(
            self.return_selected_label
        )

        return_button = QPushButton(
            "İADE AL"
        )

        return_button.setMinimumHeight(
            45
        )

        return_button.clicked.connect(
            self.return_selected_loan
        )

        current_layout.addWidget(
            return_button
        )

        layout.addWidget(
            current_group
        )

        self._add_page(self.return_tab, "↩  İade Alma", in_accordion=False)

    def search_return_members(self):

        members = self.db.search_members(
            self.return_member_search_edit.text()
        )

        self.return_member_table.setRowCount(
            len(members)
        )

        for r, member in enumerate(members):

            values = [
                member["id"],
                member["member_number"] or "-",
                f"{member['first_name']} {member['last_name']}",
                member["status"]
            ]

            for c, value in enumerate(values):
                self.return_member_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )

    def return_member_selected(self):

        row = self.return_member_table.currentRow()

        if row < 0:
            return

        member_id = int(
            self.return_member_table.item(
                row,
                0
            ).text()
        )

        member = self.db.get_member(
            member_id
        )

        if not member:
            return

        self.return_selected_member_label.setText(
            f"Seçili üye: "
            f"{member['first_name']} "
            f"{member['last_name']} "
            f"({member['member_number'] or '-'})"
        )

        self.load_return_loans(
            member_id
        )

    def load_return_loans(self, member_id):

        loans = self.db.get_active_loans_for_member(
            member_id
        )

        self.return_loans_table.setRowCount(
            len(loans)
        )

        for r, loan in enumerate(loans):

            status = (
                "Gecikmiş"
                if loan["due_at"] < now_string()
                else "Ödünçte"
            )

            values = [
                loan["id"],
                loan["book_number"] or "-",
                loan["title"],
                loan["isbn"] or "-",
                display_datetime(loan["borrowed_at"]),
                display_datetime(loan["due_at"]),
                status
            ]

            for c, value in enumerate(values):
                self.return_loans_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )

    def search_return_book(self):

        value = self.return_book_search_edit.text().strip()

        if not value:
            return

        copy = self.db.get_copy_by_number(
            value
        )

        if copy:

            loan = self.db.get_copy_active_loan(
                copy["id"]
            )

            if loan:

                self.return_book_result_label.setText(
                    f"Kitap: {loan['title']} | "
                    f"Kitap No: {loan['book_number'] or '-'} | "
                    f"Üye: {loan['first_name']} {loan['last_name']} | "
                    f"Son İade: {display_datetime(loan['due_at'])}"
                )

                self.select_return_loan_by_id(
                    loan["id"]
                )

                return

            self.return_book_result_label.setText(
                "Bu fiziksel nüsha şu anda ödünçte değil."
            )

            return

        isbn = normalize_isbn(
            value
        )

        loans = self.db.search_active_loans_by_isbn(
            isbn
        )

        if not loans:

            self.return_book_result_label.setText(
                "Aktif ödünç kaydı bulunamadı."
            )

            return

        self.return_book_result_label.setText(
            f"Bu ISBN için {len(loans)} aktif ödünç kaydı bulundu."
        )

        if len(loans) == 1:
            self.select_return_loan_by_id(
                loans[0]["id"]
            )

    def select_return_loan_by_id(self, loan_id):

        for row in range(
            self.return_loans_table.rowCount()
        ):

            item = self.return_loans_table.item(
                row,
                0
            )

            if item and int(item.text()) == loan_id:

                self.return_loans_table.selectRow(
                    row
                )

                break

    def return_loan_selected(self):

        row = self.return_loans_table.currentRow()

        if row < 0:
            self.return_selected_label.setText(
                "İade için seçili kayıt: Yok"
            )
            return

        loan_id = self.return_loans_table.item(
            row,
            0
        ).text()

        book = self.return_loans_table.item(
            row,
            2
        ).text()

        self.return_selected_label.setText(
            f"İade için seçili kayıt: "
            f"#{loan_id} - {book}"
        )

    def return_selected_loan(self):

        row = self.return_loans_table.currentRow()

        if row < 0:

            QMessageBox.warning(
                self,
                "Uyarı",
                "İade alınacak kitabı seçin."
            )

            return

        loan_id = int(
            self.return_loans_table.item(
                row,
                0
            ).text()
        )

        answer = QMessageBox.question(
            self,
            "İade Onayı",
            "Seçili kitabı iade almak istediğinizden emin misiniz?"
        )

        if answer != QMessageBox.Yes:
            return

        try:

            self.db.return_book(
                loan_id
            )

            QMessageBox.information(
                self,
                "Başarılı",
                "Kitap iade alındı."
            )

            member_row = self.return_member_table.currentRow()

            if member_row >= 0:

                member_id = int(
                    self.return_member_table.item(
                        member_row,
                        0
                    ).text()
                )

                self.load_return_loans(
                    member_id
                )

            self.return_book_result_label.setText(
                "Kitap iade edildi."
            )

            self.refresh_books()
            self.refresh_home()
            self.refresh_overdue()

        except Exception as exc:

            QMessageBox.critical(
                self,
                "Hata",
                str(exc)
            )

    # =====================================================
    # GECİKENLER
    # =====================================================

    def create_overdue_tab(self):

        self.overdue_tab = QWidget()

        layout = QVBoxLayout(
            self.overdue_tab
        )

        title = QLabel(
            "Geciken Kitaplar"
        )

        title.setStyleSheet(
            "font-size: 22px; font-weight: bold;"
        )

        layout.addWidget(
            title
        )

        info = QLabel(
            "Son iade tarihi geçmiş ve henüz iade edilmemiş kitaplar."
        )

        layout.addWidget(
            info
        )

        refresh_button = QPushButton(
            "Listeyi Yenile"
        )

        refresh_button.clicked.connect(
            self.refresh_overdue
        )

        layout.addWidget(
            refresh_button
        )

        self.overdue_table = QTableWidget()

        self.overdue_table.setColumnCount(8)

        self.overdue_table.setHorizontalHeaderLabels([
            "Üye No",
            "Üye",
            "Kitap No",
            "Kitap",
            "ISBN",
            "Ödünç Tarihi",
            "Son İade",
            "Gecikme"
        ])

        self.overdue_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.overdue_table.setSelectionBehavior(
            QAbstractItemView.SelectRows
        )

        self.overdue_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        layout.addWidget(
            self.overdue_table
        )

        self._add_page(self.overdue_tab, "⏰  Geciken Kitaplar", in_accordion=False)

    def refresh_overdue(self):

        loans = self.db.get_overdue_loans()

        self.overdue_table.setRowCount(
            len(loans)
        )

        for r, loan in enumerate(loans):

            try:

                due = datetime.strptime(
                    loan["due_at"],
                    "%Y-%m-%d %H:%M:%S"
                )

                days = (
                    datetime.now() - due
                ).days

                delay = f"{days} gün"

            except Exception:

                delay = "-"

            values = [
                loan["member_number"] or "-",
                f"{loan['first_name']} {loan['last_name']}",
                loan["book_number"] or "-",
                loan["title"],
                loan["isbn"] or "-",
                display_datetime(loan["borrowed_at"]),
                display_datetime(loan["due_at"]),
                delay
            ]

            for c, value in enumerate(values):
                self.overdue_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(str(value))
                )

    # =====================================================
    # RAPORLAR
    # =====================================================

    def create_reports_tab(self):

        self.reports_tab = QWidget()

        layout = QVBoxLayout(
            self.reports_tab
        )

        title = QLabel(
            "Raporlar"
        )

        title.setStyleSheet(
            "font-size: 22px; font-weight: bold;"
        )

        layout.addWidget(
            title
        )

        filters = QGroupBox(
            "Rapor Filtresi"
        )

        filter_layout = QGridLayout(
            filters
        )

        self.report_type_combo = QComboBox()

        self.report_type_combo.addItems([
            "Genel Durum",
            "Ödünç / İade",
            "Üye Raporu",
            "Kitap Kullanım",
            "Geciken Kitaplar",
            "Kitap Numarası Geçmişi"
        ])

        self.report_start_date = QDateEdit()

        self.report_start_date.setCalendarPopup(
            True
        )

        self.report_start_date.setDate(
            QDate.currentDate().addMonths(-1)
        )

        self.report_end_date = QDateEdit()

        self.report_end_date.setCalendarPopup(
            True
        )

        self.report_end_date.setDate(
            QDate.currentDate()
        )

        self.report_date_mode = QComboBox()

        self.report_date_mode.addItems([
            "Ödünç tarihi",
            "İade tarihi",
            "Son iade tarihi"
        ])

        self.report_book_number_edit = QLineEdit()

        self.report_book_number_edit.setPlaceholderText(
            "Kitap Numarası - opsiyonel"
        )

        filter_layout.addWidget(
            QLabel("Rapor:"),
            0,
            0
        )

        filter_layout.addWidget(
            self.report_type_combo,
            0,
            1
        )

        filter_layout.addWidget(
            QLabel("Başlangıç:"),
            0,
            2
        )

        filter_layout.addWidget(
            self.report_start_date,
            0,
            3
        )

        filter_layout.addWidget(
            QLabel("Bitiş:"),
            0,
            4
        )

        filter_layout.addWidget(
            self.report_end_date,
            0,
            5
        )

        filter_layout.addWidget(
            QLabel("Tarih alanı:"),
            1,
            0
        )

        filter_layout.addWidget(
            self.report_date_mode,
            1,
            1
        )

        filter_layout.addWidget(
            QLabel("Kitap No:"),
            1,
            2
        )

        filter_layout.addWidget(
            self.report_book_number_edit,
            1,
            3,
            1,
            3
        )

        layout.addWidget(
            filters
        )

        generate_button = QPushButton(
            "Raporu Oluştur"
        )

        generate_button.clicked.connect(
            self.generate_report
        )

        layout.addWidget(
            generate_button
        )

        self.report_table = QTableWidget()

        self.report_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.report_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        layout.addWidget(
            self.report_table
        )

        self._add_page(self.reports_tab, "📊  Raporlar", in_accordion=True)

    def get_report_date_mode(self):

        text = self.report_date_mode.currentText()

        return {
            "Ödünç tarihi": "borrowed_at",
            "İade tarihi": "returned_at",
            "Son iade tarihi": "due_at"
        }.get(
            text,
            "borrowed_at"
        )

    def generate_report(self):

        start, end = date_range_from_widgets(
            self.report_start_date,
            self.report_end_date
        )

        headers, rows = self.db.generate_report(
            self.report_type_combo.currentText(),
            start,
            end,
            self.get_report_date_mode(),
            self.report_book_number_edit.text()
        )

        self.show_report_table(
            headers,
            rows
        )

    def show_report_table(self, headers, rows):

        self.report_table.setColumnCount(
            len(headers)
        )

        self.report_table.setHorizontalHeaderLabels(
            headers
        )

        self.report_table.setRowCount(
            len(rows)
        )

        for r, row in enumerate(rows):

            for c, value in enumerate(row):

                self.report_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )

    # =====================================================
    # RAPOR DIŞA AKTAR
    # =====================================================

    def create_export_tab(self):

        self.export_tab = QWidget()

        layout = QVBoxLayout(
            self.export_tab
        )

        title = QLabel(
            "Raporları Dışa Aktar"
        )

        title.setStyleSheet(
            "font-size: 22px; font-weight: bold;"
        )

        layout.addWidget(
            title
        )

        filters = QGroupBox(
            "Dışa Aktarma Filtresi"
        )

        grid = QGridLayout(
            filters
        )

        self.export_type_combo = QComboBox()

        self.export_type_combo.addItems([
            "Genel Durum",
            "Ödünç / İade",
            "Üye Raporu",
            "Kitap Kullanım",
            "Geciken Kitaplar",
            "Kitap Numarası Geçmişi"
        ])

        self.export_start_date = QDateEdit()

        self.export_start_date.setCalendarPopup(
            True
        )

        self.export_start_date.setDate(
            QDate.currentDate().addMonths(-1)
        )

        self.export_end_date = QDateEdit()

        self.export_end_date.setCalendarPopup(
            True
        )

        self.export_end_date.setDate(
            QDate.currentDate()
        )

        self.export_date_mode = QComboBox()

        self.export_date_mode.addItems([
            "Ödünç tarihi",
            "İade tarihi",
            "Son iade tarihi"
        ])

        self.export_book_number_edit = QLineEdit()

        self.export_book_number_edit.setPlaceholderText(
            "Kitap Numarası - opsiyonel"
        )

        grid.addWidget(
            QLabel("Rapor:"),
            0,
            0
        )

        grid.addWidget(
            self.export_type_combo,
            0,
            1
        )

        grid.addWidget(
            QLabel("Başlangıç:"),
            0,
            2
        )

        grid.addWidget(
            self.export_start_date,
            0,
            3
        )

        grid.addWidget(
            QLabel("Bitiş:"),
            0,
            4
        )

        grid.addWidget(
            self.export_end_date,
            0,
            5
        )

        grid.addWidget(
            QLabel("Tarih alanı:"),
            1,
            0
        )

        grid.addWidget(
            self.export_date_mode,
            1,
            1
        )

        grid.addWidget(
            QLabel("Kitap No:"),
            1,
            2
        )

        grid.addWidget(
            self.export_book_number_edit,
            1,
            3,
            1,
            3
        )

        layout.addWidget(
            filters
        )

        preview_button = QPushButton(
            "Verileri Getir / Önizle"
        )

        preview_button.clicked.connect(
            self.prepare_export
        )

        layout.addWidget(
            preview_button
        )

        self.export_preview_table = QTableWidget()

        self.export_preview_table.setEditTriggers(
            QAbstractItemView.NoEditTriggers
        )

        self.export_preview_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )

        layout.addWidget(
            self.export_preview_table
        )

        columns_group = QGroupBox(
            "Dışa Aktarılacak Alanlar"
        )

        self.export_columns_layout = QGridLayout(
            columns_group
        )

        layout.addWidget(
            columns_group
        )

        format_layout = QHBoxLayout()

        format_layout.addWidget(
            QLabel("Format:")
        )

        self.export_format_combo = QComboBox()

        self.export_format_combo.addItems([
            "Excel (.xlsx)",
            "CSV (.csv)"
        ])

        format_layout.addWidget(
            self.export_format_combo
        )

        format_layout.addStretch()

        export_button = QPushButton(
            "Raporu Dışa Aktar"
        )

        export_button.clicked.connect(
            self.export_report
        )

        format_layout.addWidget(
            export_button
        )

        layout.addLayout(
            format_layout
        )

        self.export_headers = []
        self.export_rows = []
        self.export_checks = []

        self._add_page(self.export_tab, "📤  Rapor Dışa Aktar", in_accordion=False)

    def export_date_mode_value(self):

        text = self.export_date_mode.currentText()

        return {
            "Ödünç tarihi": "borrowed_at",
            "İade tarihi": "returned_at",
            "Son iade tarihi": "due_at"
        }.get(
            text,
            "borrowed_at"
        )

    def prepare_export(self):

        start, end = date_range_from_widgets(
            self.export_start_date,
            self.export_end_date
        )

        headers, rows = self.db.generate_report(
            self.export_type_combo.currentText(),
            start,
            end,
            self.export_date_mode_value(),
            self.export_book_number_edit.text()
        )

        self.export_headers = headers
        self.export_rows = rows

        self.export_preview_table.setColumnCount(
            len(headers)
        )

        self.export_preview_table.setHorizontalHeaderLabels(
            headers
        )

        self.export_preview_table.setRowCount(
            len(rows)
        )

        for r, row in enumerate(rows):

            for c, value in enumerate(row):

                self.export_preview_table.setItem(
                    r,
                    c,
                    QTableWidgetItem(
                        str(value)
                    )
                )

        # Eski checkboxları temizle
        while self.export_columns_layout.count():

            item = self.export_columns_layout.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

        self.export_checks = []

        for i, header in enumerate(headers):

            checkbox = QCheckBox(
                header
            )

            checkbox.setChecked(
                True
            )

            self.export_checks.append(
                checkbox
            )

            row = i // 3
            col = i % 3

            self.export_columns_layout.addWidget(
                checkbox,
                row,
                col
            )

    def export_report(self):

        if not self.export_headers:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Önce verileri getirip önizleyin."
            )
            return

        selected_indexes = [
            i
            for i, checkbox in enumerate(
                self.export_checks
            )
            if checkbox.isChecked()
        ]

        if not selected_indexes:

            QMessageBox.warning(
                self,
                "Uyarı",
                "En az bir alan seçin."
            )

            return

        headers = [
            self.export_headers[i]
            for i in selected_indexes
        ]

        rows = []

        for row in self.export_rows:

            rows.append([
                row[i]
                for i in selected_indexes
            ])

        format_text = self.export_format_combo.currentText()

        if "CSV" in format_text:

            filename, _ = QFileDialog.getSaveFileName(
                self,
                "CSV Kaydet",
                "kutuphane_raporu.csv",
                "CSV Dosyaları (*.csv)"
            )

            if not filename:
                return

            try:

                with open(
                    filename,
                    "w",
                    newline="",
                    encoding="utf-8-sig"
                ) as file:

                    writer = csv.writer(
                        file
                    )

                    writer.writerow(
                        headers
                    )

                    writer.writerows(
                        rows
                    )

                QMessageBox.information(
                    self,
                    "Başarılı",
                    f"Rapor dışa aktarıldı:\n{filename}"
                )

            except Exception as exc:

                QMessageBox.critical(
                    self,
                    "Hata",
                    str(exc)
                )

        else:

            filename, _ = QFileDialog.getSaveFileName(
                self,
                "Excel Kaydet",
                "kutuphane_raporu.xlsx",
                "Excel Dosyaları (*.xlsx)"
            )

            if not filename:
                return

            try:

                from openpyxl import Workbook

                workbook = Workbook()

                sheet = workbook.active

                sheet.title = "Rapor"

                sheet.append(
                    headers
                )

                for row in rows:
                    sheet.append(
                        row
                    )

                for column in sheet.columns:

                    max_length = 0

                    column_letter = column[0].column_letter

                    for cell in column:

                        value = (
                            ""
                            if cell.value is None
                            else str(cell.value)
                        )

                        max_length = max(
                            max_length,
                            len(value)
                        )

                    sheet.column_dimensions[
                        column_letter
                    ].width = min(
                        max_length + 2,
                        50
                    )

                workbook.save(
                    filename
                )

                QMessageBox.information(
                    self,
                    "Başarılı",
                    f"Excel raporu dışa aktarıldı:\n{filename}"
                )

            except ImportError:

                QMessageBox.warning(
                    self,
                    "Excel Modülü Eksik",
                    "Excel dışa aktarma için openpyxl gerekli.\n\n"
                    "Kurmak için:\n"
                    "python -m pip install openpyxl"
                )

            except Exception as exc:

                QMessageBox.critical(
                    self,
                    "Hata",
                    str(exc)
                )

    # =====================================================
    # AYARLAR
    # =====================================================

    def create_settings_tab(self):

        self.settings_tab = QWidget()

        layout = QVBoxLayout(
            self.settings_tab
        )

        title = QLabel(
            "Ayarlar"
        )

        title.setStyleSheet(
            "font-size: 22px; font-weight: bold;"
        )

        layout.addWidget(
            title
        )

        database_group = QGroupBox(
            "Veritabanı"
        )

        database_layout = QFormLayout(
            database_group
        )

        database_layout.addRow(
            "Veritabanı dosyası:",
            QLabel(
                os.path.abspath(
                    DB_FILE
                )
            )
        )

        database_layout.addRow(
            "İşlem geçmişi veritabanı:",
            QLabel(
                os.path.abspath(
                    LOG_DB_FILE
                )
            )
        )

        layout.addWidget(
            database_group
        )

        status_group = QGroupBox(
            "Durumlar"
        )

        status_layout = QVBoxLayout(
            status_group
        )

        status_layout.addWidget(
            QLabel(
                "Fiziksel nüsha durumları:"
            )
        )

        status_layout.addWidget(
            QLabel(
                "Mevcut / Ödünçte / Kayıp / Hasarlı / "
                "Bakımda / Arşivde"
            )
        )

        status_layout.addWidget(
            QLabel(
                "Üye durumları: Aktif / Pasif"
            )
        )

        layout.addWidget(
            status_group
        )

        api_group = QGroupBox(
            "ISBN Bilgi Servisi"
        )

        api_layout = QVBoxLayout(
            api_group
        )

        api_layout.addWidget(
            QLabel(
                "ISBN / barkod bilgi araması Open Library servisi "
                "üzerinden yapılır."
            )
        )

        layout.addWidget(
            api_group
        )

        users_group = QGroupBox(
            "Kullanıcı Yönetimi"
        )

        users_layout = QVBoxLayout(
            users_group
        )

        users_layout.addWidget(
            QLabel(
                "Ödünç verme / iade alma / ekleme işlemlerinde "
                "kimin işlem yaptığını takip etmek için basit "
                "kullanıcılar tanımlayın. Bu kullanıcılar şifresizdir; "
                "sadece sol menüdeki listeden seçilir."
            )
        )

        add_user_row = QHBoxLayout()

        self.new_username_edit = QLineEdit()
        self.new_username_edit.setPlaceholderText("Yeni kullanıcı adı...")
        self.new_username_edit.returnPressed.connect(self.save_new_user)

        add_user_button = QPushButton("Kullanıcı Ekle")
        add_user_button.clicked.connect(self.save_new_user)

        add_user_row.addWidget(self.new_username_edit)
        add_user_row.addWidget(add_user_button)

        users_layout.addLayout(add_user_row)

        self.users_table = QTableWidget()
        self.users_table.setColumnCount(3)
        self.users_table.setHorizontalHeaderLabels([
            "Kullanıcı Adı",
            "Rol",
            "Durum"
        ])
        self.users_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.users_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        users_layout.addWidget(self.users_table)

        layout.addWidget(
            users_group
        )

        layout.addStretch()

        self._add_page(self.settings_tab, "⚙  Ayarlar", in_accordion=True)

    def save_new_user(self):

        username = self.new_username_edit.text().strip()

        if not username:
            QMessageBox.warning(
                self,
                "Uyarı",
                "Kullanıcı adı boş olamaz."
            )
            return

        try:
            self.db.add_user(username)
            self.new_username_edit.clear()
            self.refresh_users_everywhere()

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Hata",
                str(exc)
            )

    def refresh_users_table(self):

        users = self.db.get_all_users()

        self.users_table.setRowCount(len(users))

        for row, user in enumerate(users):
            self.users_table.setItem(
                row, 0, QTableWidgetItem(user["username"])
            )
            self.users_table.setItem(
                row, 1, QTableWidgetItem(user["role"] or "")
            )
            self.users_table.setItem(
                row, 2, QTableWidgetItem(user["status"] or "")
            )

    # =====================================================
    # YENİLEME
    # =====================================================

    def refresh_home(self):

        stats = self.db.dashboard_stats()

        for key, label in self.stat_labels.items():

            label.setText(
                str(
                    stats.get(
                        key,
                        0
                    )
                )
            )

    def refresh_all(self):

        self.refresh_home()
        self.refresh_books()
        self.refresh_members()
        self.refresh_overdue()

    def tab_changed(self, index):

        widget = self.stacked_widget.widget(
            index
        )

        if widget == self.home_tab:
            self.refresh_home()

        elif widget == self.books_tab:
            self.refresh_books()

        elif widget == self.members_tab:
            self.refresh_members()

        elif widget == self.overdue_tab:
            self.refresh_overdue()


# =========================================================
# PROGRAMI BAŞLAT
# =========================================================

def main():

    app = QApplication(
        sys.argv
    )

    app.setStyle(
        "Fusion"
    )

    window = LibraryApp()

    window.show()

    sys.exit(
        app.exec()
    )


if __name__ == "__main__":
    main()