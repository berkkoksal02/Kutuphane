import sys
import sqlite3
from datetime import datetime, timedelta
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (
    QApplication, QFrame, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMainWindow, QPushButton, QStackedWidget,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
    QDialog, QFormLayout, QMessageBox, QComboBox, QSpinBox
)

DB_FILE = "library.db"

def now_string():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# -------------------------------------------------------------
# 1. VERİTABANI KATMANI (TRANSACTION-SAFE DATABASE)
# -------------------------------------------------------------
class Database:
    def __init__(self, filename=DB_FILE):
        self.conn = sqlite3.connect(filename)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.create_tables()
        self.create_indexes()

    def create_tables(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS books (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    isbn TEXT,
                    title TEXT NOT NULL,
                    author TEXT,
                    publisher TEXT,
                    category TEXT,
                    created_at TEXT
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS book_copies (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_id INTEGER NOT NULL,
                    book_number TEXT UNIQUE,
                    shelf TEXT,
                    status TEXT DEFAULT 'Mevcut',
                    FOREIGN KEY(book_id) REFERENCES books(id) ON DELETE CASCADE
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    member_number TEXT UNIQUE,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    phone TEXT,
                    email TEXT,
                    status TEXT DEFAULT 'Aktif'
                )
            """)

            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS loans (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    book_copy_id INTEGER NOT NULL,
                    member_id INTEGER NOT NULL,
                    borrowed_at TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    returned_at TEXT,
                    FOREIGN KEY(book_copy_id) REFERENCES book_copies(id),
                    FOREIGN KEY(member_id) REFERENCES members(id)
                )
            """)

    def create_indexes(self):
        with self.conn:
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_books_isbn ON books(isbn)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_copies_book ON book_copies(book_id)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_loans_active ON loans(book_copy_id) WHERE returned_at IS NULL")

    def get_stats(self):
        cur = self.conn.cursor()
        total_books = cur.execute("SELECT COUNT(*) FROM books").fetchone()[0]
        total_copies = cur.execute("SELECT COUNT(*) FROM book_copies").fetchone()[0]
        borrowed = cur.execute("SELECT COUNT(*) FROM book_copies WHERE status = 'Ödünçte'").fetchone()[0]
        
        now = now_string()
        overdue = cur.execute("""
            SELECT COUNT(*) FROM loans 
            WHERE returned_at IS NULL AND due_at < ?
        """, (now,)).fetchone()[0]
        
        return {
            "total_books": total_books,
            "total_copies": total_copies,
            "borrowed": borrowed,
            "available": total_copies - borrowed,
            "overdue": overdue
        }

    def add_book_with_copies(self, isbn, title, author, publisher, category, copy_count, shelf):
        with self.conn:
            cur = self.conn.cursor()
            cur.execute("""
                INSERT INTO books (isbn, title, author, publisher, category, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (isbn, title, author, publisher, category, now_string()))
            book_id = cur.lastrowid

            for i in range(1, copy_count + 1):
                copy_no = f"{isbn}-{book_id}-{i}"
                cur.execute("""
                    INSERT INTO book_copies (book_id, book_number, shelf, status)
                    VALUES (?, ?, ?, 'Mevcut')
                """, (book_id, copy_no, shelf))

    def add_member(self, member_no, first_name, last_name, phone, email):
        with self.conn:
            self.conn.execute("""
                INSERT INTO members (member_number, first_name, last_name, phone, email)
                VALUES (?, ?, ?, ?, ?)
            """, (member_no, first_name, last_name, phone, email))

    def search_books(self, text=""):
        like = f"%{text.strip()}%"
        sql = """
            SELECT 
                b.id, b.isbn, b.title, b.author, b.category,
                COUNT(c.id) as total_copies,
                COALESCE(SUM(CASE WHEN c.status = 'Mevcut' THEN 1 ELSE 0 END), 0) as available_copies
            FROM books b
            LEFT JOIN book_copies c ON c.book_id = b.id
            WHERE b.title LIKE ? OR b.author LIKE ? OR b.isbn LIKE ? OR b.category LIKE ?
            GROUP BY b.id
            ORDER BY b.title COLLATE NOCASE
        """
        cur = self.conn.cursor()
        return cur.execute(sql, (like, like, like, like)).fetchall()

    def search_members(self, text=""):
        like = f"%{text.strip()}%"
        sql = """
            SELECT id, member_number, first_name || ' ' || last_name as full_name, phone, email, status
            FROM members
            WHERE first_name LIKE ? OR last_name LIKE ? OR member_number LIKE ?
            ORDER BY first_name COLLATE NOCASE
        """
        cur = self.conn.cursor()
        return cur.execute(sql, (like, like, like)).fetchall()

    def get_available_copy(self, book_id):
        cur = self.conn.cursor()
        return cur.execute("""
            SELECT id FROM book_copies WHERE book_id = ? AND status = 'Mevcut' LIMIT 1
        """, (book_id,)).fetchone()

    def borrow_book(self, book_id, member_id, days=14):
        copy = self.get_available_copy(book_id)
        if not copy:
            raise ValueError("Bu kitabın boşta olan kullanılabilir nüshası yok!")

        due_date = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d 23:59:59")
        copy_id = copy["id"]

        with self.conn:
            self.conn.execute("""
                INSERT INTO loans (book_copy_id, member_id, borrowed_at, due_at)
                VALUES (?, ?, ?, ?)
            """, (copy_id, member_id, now_string(), due_date))

            self.conn.execute("""
                UPDATE book_copies SET status = 'Ödünçte' WHERE id = ?
            """, (copy_id,))

    def get_active_loans(self):
        sql = """
            SELECT 
                l.id as loan_id,
                b.title as book_title,
                m.first_name || ' ' || m.last_name as member_name,
                l.borrowed_at,
                l.due_at,
                c.book_number
            FROM loans l
            JOIN book_copies c ON l.book_copy_id = c.id
            JOIN books b ON c.book_id = b.id
            JOIN members m ON l.member_id = m.id
            WHERE l.returned_at IS NULL
            ORDER BY l.due_at ASC
        """
        cur = self.conn.cursor()
        return cur.execute(sql).fetchall()

    def return_loan(self, loan_id):
        cur = self.conn.cursor()
        loan = cur.execute("SELECT book_copy_id FROM loans WHERE id = ?", (loan_id,)).fetchone()
        if not loan:
            raise ValueError("Ödünç kaydı bulunamadı!")

        with self.conn:
            self.conn.execute("UPDATE loans SET returned_at = ? WHERE id = ?", (now_string(), loan_id))
            self.conn.execute("UPDATE book_copies SET status = 'Mevcut' WHERE id = ?", (loan["book_copy_id"],))

# -------------------------------------------------------------
# 2. QSS MODERN DARK THEME
# -------------------------------------------------------------
MODERN_STYLE = """
QMainWindow { background-color: #121214; }
#SidebarFrame { background-color: #18181B; border-right: 1px solid #27272A; }
#AppTitle { color: #F4F4F5; font-size: 18px; font-weight: bold; padding: 10px 0px; }

QPushButton.nav-btn {
    background-color: transparent; color: #A1A1AA; border: none;
    border-radius: 8px; padding: 12px 16px; font-size: 14px; font-weight: 500; text-align: left;
}
QPushButton.nav-btn:hover { background-color: #27272A; color: #F4F4F5; }
QPushButton.nav-btn:checked { background-color: #6366F1; color: #FFFFFF; font-weight: bold; }

#ContentArea { background-color: #121214; }
#PageTitle { color: #F4F4F5; font-size: 22px; font-weight: bold; }

QFrame.card { background-color: #18181B; border: 1px solid #27272A; border-radius: 12px; }
QLabel.card-title { color: #A1A1AA; font-size: 12px; font-weight: 600; text-transform: uppercase; }
QLabel.card-value { color: #F4F4F5; font-size: 24px; font-weight: bold; }

QLineEdit, QComboBox, QSpinBox {
    background-color: #18181B; border: 1px solid #27272A; border-radius: 8px;
    color: #F4F4F5; padding: 8px 12px; font-size: 14px;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #6366F1; }

QPushButton.primary-btn {
    background-color: #6366F1; color: #FFFFFF; border: none;
    border-radius: 8px; padding: 10px 18px; font-size: 14px; font-weight: bold;
}
QPushButton.primary-btn:hover { background-color: #4F46E5; }

QPushButton.action-btn {
    background-color: #27272A; color: #F4F4F5; border: 1px solid #3F3F46;
    border-radius: 6px; padding: 4px 10px; font-size: 12px;
}
QPushButton.action-btn:hover { background-color: #3F3F46; }

QTableWidget {
    background-color: #18181B; border: 1px solid #27272A; border-radius: 12px;
    color: #F4F4F5; gridline-color: #27272A; selection-background-color: #312E81;
}
QHeaderView::section {
    background-color: #27272A; color: #A1A1AA; padding: 10px; border: none; font-weight: bold;
}
"""

# -------------------------------------------------------------
# 3. MODAL PENCERELER (FORMLAR)
# -------------------------------------------------------------
class AddBookDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Kitap ve Nüsha Ekle")
        self.setFixedWidth(400)
        
        layout = QFormLayout(self)
        self.isbn = QLineEdit()
        self.title = QLineEdit()
        self.author = QLineEdit()
        self.publisher = QLineEdit()
        self.category = QLineEdit()
        self.copies = QSpinBox()
        self.copies.setRange(1, 100)
        self.copies.setValue(1)
        self.shelf = QLineEdit()

        layout.addRow("ISBN:", self.isbn)
        layout.addRow("Kitap Adı:", self.title)
        layout.addRow("Yazar:", self.author)
        layout.addRow("Yayın Evi:", self.publisher)
        layout.addRow("Kategori:", self.category)
        layout.addRow("Adet (Nüsha):", self.copies)
        layout.addRow("Raf Konumu:", self.shelf)

        btn_save = QPushButton("Kaydet")
        btn_save.setProperty("class", "primary-btn")
        btn_save.clicked.connect(self.accept)
        layout.addRow(btn_save)

class AddMemberDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Yeni Üye Kaydı")
        self.setFixedWidth(400)

        layout = QFormLayout(self)
        self.member_no = QLineEdit()
        self.first_name = QLineEdit()
        self.last_name = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()

        layout.addRow("Üye No:", self.member_no)
        layout.addRow("Ad:", self.first_name)
        layout.addRow("Soyad:", self.last_name)
        layout.addRow("Telefon:", self.phone)
        layout.addRow("E-Posta:", self.email)

        btn_save = QPushButton("Üye Kaydet")
        btn_save.setProperty("class", "primary-btn")
        btn_save.clicked.connect(self.accept)
        layout.addRow(btn_save)

class BorrowBookDialog(QDialog):
    def __init__(self, db, parent=None):
        super().__init__(parent)
        self.db = db
        self.setWindowTitle("Kitap Ödünç Ver")
        self.setFixedWidth(420)

        layout = QFormLayout(self)
        self.combo_books = QComboBox()
        self.combo_members = QComboBox()
        self.days_box = QSpinBox()
        self.days_box.setRange(1, 90)
        self.days_box.setValue(14)

        # Kitapları doldur (Sadece mevcut nüshası olanlar)
        books = self.db.search_books()
        for b in books:
            if b["available_copies"] > 0:
                self.combo_books.addItem(f"{b['title']} - {b['author']} (Stok: {b['available_copies']})", b["id"])

        # Üyeleri doldur
        members = self.db.search_members()
        for m in members:
            self.combo_members.addItem(f"{m['member_number']} - {m['full_name']}", m["id"])

        layout.addRow("Kitap Seç:", self.combo_books)
        layout.addRow("Üye Seç:", self.combo_members)
        layout.addRow("Süre (Gün):", self.days_box)

        btn_save = QPushButton("Ödünç İşlemini Tamamla")
        btn_save.setProperty("class", "primary-btn")
        btn_save.clicked.connect(self.accept)
        layout.addRow(btn_save)

# -------------------------------------------------------------
# 4. ANA PENCERE VE ARAYÜZ MANTIĞI
# -------------------------------------------------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = Database()
        self.setWindowTitle("Kütüphane Yönetim Otomasyonu")
        self.resize(1150, 750)
        self.setStyleSheet(MODERN_STYLE)

        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Sidebar & Content Area
        main_layout.addWidget(self.create_sidebar())

        self.content_area = QFrame()
        self.content_area.setObjectName("ContentArea")
        content_layout = QVBoxLayout(self.content_area)
        content_layout.setContentsMargins(28, 28, 28, 28)

        self.stacked_widget = QStackedWidget()
        self.stacked_widget.addWidget(self.create_dashboard_page())
        self.stacked_widget.addWidget(self.create_books_page())
        self.stacked_widget.addWidget(self.create_members_page())
        self.stacked_widget.addWidget(self.create_loans_page())

        content_layout.addWidget(self.stacked_widget)
        main_layout.addWidget(self.content_area)

        # Verileri İlk Kez Yükle
        self.refresh_all_data()

    def create_sidebar(self):
        sidebar = QFrame()
        sidebar.setObjectName("SidebarFrame")
        sidebar.setFixedWidth(240)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(8)

        title = QLabel("📚 LibManager Pro")
        title.setObjectName("AppTitle")
        layout.addWidget(title)
        layout.addSpacing(20)

        self.btn_dash = self.create_nav_btn(" Dashboard", 0)
        self.btn_books = self.create_nav_btn(" Kitap Yönetimi", 1)
        self.btn_members = self.create_nav_btn(" Üye Yönetimi", 2)
        self.btn_loans = self.create_nav_btn(" Ödünç / İade", 3)

        self.nav_buttons = [self.btn_dash, self.btn_books, self.btn_members, self.btn_loans]
        self.btn_dash.setChecked(True)

        for btn in self.nav_buttons:
            layout.addWidget(btn)
        
        layout.addStretch()
        return sidebar

    def create_nav_btn(self, text, page_index):
        btn = QPushButton(text)
        btn.setProperty("class", "nav-btn")
        btn.setCheckable(True)
        btn.clicked.connect(lambda: self.switch_page(page_index, btn))
        return btn

    def switch_page(self, index, active_btn):
        for btn in self.nav_buttons:
            btn.setChecked(False)
        active_btn.setChecked(True)
        self.stacked_widget.setCurrentIndex(index)
        self.refresh_all_data()

    # --- PAGES ---
    def create_dashboard_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(24)

        header = QLabel("Genel Durum Paneli")
        header.setObjectName("PageTitle")
        layout.addWidget(header)

        cards_layout = QHBoxLayout()
        cards_layout.setSpacing(16)

        self.card_total_books = self.create_card("TOPLAM KİTAP", "0")
        self.card_total_copies = self.create_card("TOPLAM NÜSHA", "0")
        self.card_borrowed = self.create_card("ÖDÜNÇTE", "0")
        self.card_overdue = self.create_card("GECİKEN İADELER", "0")

        cards_layout.addWidget(self.card_total_books)
        cards_layout.addWidget(self.card_total_copies)
        cards_layout.addWidget(self.card_borrowed)
        cards_layout.addWidget(self.card_overdue)

        layout.addLayout(cards_layout)
        layout.addStretch()
        return page

    def create_card(self, title_text, value_text):
        card = QFrame()
        card.setProperty("class", "card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 20, 20, 20)

        t_label = QLabel(title_text)
        t_label.setProperty("class", "card-title")
        v_label = QLabel(value_text)
        v_label.setProperty("class", "card-value")

        card_layout.addWidget(t_label)
        card_layout.addWidget(v_label)
        card.value_label = v_label
        return card

    def create_books_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        top_bar = QHBoxLayout()
        self.search_books_input = QLineEdit()
        self.search_books_input.setPlaceholderText("Kitap adı, yazar, ISBN veya kategori ara...")
        self.search_books_input.textChanged.connect(self.load_books_table)

        btn_add = QPushButton("+ Yeni Kitap Ekle")
        btn_add.setProperty("class", "primary-btn")
        btn_add.clicked.connect(self.open_add_book_dialog)

        top_bar.addWidget(self.search_books_input, stretch=3)
        top_bar.addWidget(btn_add, stretch=1)
        layout.addLayout(top_bar)

        self.books_table = QTableWidget(0, 6)
        self.books_table.setHorizontalHeaderLabels(["ID", "ISBN", "Kitap Adı", "Yazar", "Kategori", "Mevcut / Toplam"])
        self.books_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.books_table.verticalHeader().setVisible(False)
        layout.addWidget(self.books_table)

        return page

    def create_members_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        top_bar = QHBoxLayout()
        self.search_members_input = QLineEdit()
        self.search_members_input.setPlaceholderText("Üye adı, soyadı veya üye numarası ara...")
        self.search_members_input.textChanged.connect(self.load_members_table)

        btn_add = QPushButton("+ Yeni Üye Ekle")
        btn_add.setProperty("class", "primary-btn")
        btn_add.clicked.connect(self.open_add_member_dialog)

        top_bar.addWidget(self.search_members_input, stretch=3)
        top_bar.addWidget(btn_add, stretch=1)
        layout.addLayout(top_bar)

        self.members_table = QTableWidget(0, 5)
        self.members_table.setHorizontalHeaderLabels(["ID", "Üye No", "Ad Soyad", "Telefon", "E-Posta"])
        self.members_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.members_table.verticalHeader().setVisible(False)
        layout.addWidget(self.members_table)

        return page

    def create_loans_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setSpacing(16)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("Aktif Ödünç Verilen Kitaplar", objectName="PageTitle"))
        
        btn_borrow = QPushButton("📖 Kitap Ödünç Ver")
        btn_borrow.setProperty("class", "primary-btn")
        btn_borrow.clicked.connect(self.open_borrow_dialog)
        top_bar.addWidget(btn_borrow, alignment=Qt.AlignRight)

        layout.addLayout(top_bar)

        self.loans_table = QTableWidget(0, 6)
        self.loans_table.setHorizontalHeaderLabels(["Ödünç ID", "Kitap", "Nüsha Kod", "Üye", "Son Teslim", "İşlem"])
        self.loans_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.loans_table.verticalHeader().setVisible(False)
        layout.addWidget(self.loans_table)

        return page

    # --- DATA LOADING & DIALOG ACTIONS ---
    def refresh_all_data(self):
        # Stats
        stats = self.db.get_stats()
        self.card_total_books.value_label.setText(str(stats["total_books"]))
        self.card_total_copies.value_label.setText(str(stats["total_copies"]))
        self.card_borrowed.value_label.setText(str(stats["borrowed"]))
        self.card_overdue.value_label.setText(str(stats["overdue"]))

        # Tables
        self.load_books_table()
        self.load_members_table()
        self.load_loans_table()

    def load_books_table(self):
        query = self.search_books_input.text()
        books = self.db.search_books(query)
        self.books_table.setRowCount(len(books))
        for row, b in enumerate(books):
            self.books_table.setItem(row, 0, QTableWidgetItem(str(b["id"])))
            self.books_table.setItem(row, 1, QTableWidgetItem(b["isbn"]))
            self.books_table.setItem(row, 2, QTableWidgetItem(b["title"]))
            self.books_table.setItem(row, 3, QTableWidgetItem(b["author"]))
            self.books_table.setItem(row, 4, QTableWidgetItem(b["category"]))
            stock_text = f"{b['available_copies']} / {b['total_copies']}"
            self.books_table.setItem(row, 5, QTableWidgetItem(stock_text))

    def load_members_table(self):
        query = self.search_members_input.text()
        members = self.db.search_members(query)
        self.members_table.setRowCount(len(members))
        for row, m in enumerate(members):
            self.members_table.setItem(row, 0, QTableWidgetItem(str(m["id"])))
            self.members_table.setItem(row, 1, QTableWidgetItem(m["member_number"]))
            self.members_table.setItem(row, 2, QTableWidgetItem(m["full_name"]))
            self.members_table.setItem(row, 3, QTableWidgetItem(m["phone"]))
            self.members_table.setItem(row, 4, QTableWidgetItem(m["email"]))

    def load_loans_table(self):
        loans = self.db.get_active_loans()
        self.loans_table.setRowCount(len(loans))
        for row, l in enumerate(loans):
            self.loans_table.setItem(row, 0, QTableWidgetItem(str(l["loan_id"])))
            self.loans_table.setItem(row, 1, QTableWidgetItem(l["book_title"]))
            self.loans_table.setItem(row, 2, QTableWidgetItem(l["book_number"]))
            self.loans_table.setItem(row, 3, QTableWidgetItem(l["member_name"]))
            
            # Gecikme Kontrolü Renklendirmesi
            due_item = QTableWidgetItem(l["due_at"][:10])
            if l["due_at"] < now_string():
                due_item.setForeground(QColor("#EF4444")) # Kırmızı uyarı
            self.loans_table.setItem(row, 4, due_item)

            # İade Et Butonu
            btn_return = QPushButton("İade Al")
            btn_return.setProperty("class", "action-btn")
            loan_id = l["loan_id"]
            btn_return.clicked.connect(lambda _, lid=loan_id: self.return_book_action(lid))
            self.loans_table.setCellWidget(row, 5, btn_return)

    def open_add_book_dialog(self):
        dlg = AddBookDialog(self)
        if dlg.exec() == QDialog.Accepted:
            if not dlg.title.text():
                QMessageBox.warning(self, "Hata", "Kitap adı boş olamaz!")
                return
            self.db.add_book_with_copies(
                dlg.isbn.text(), dlg.title.text(), dlg.author.text(),
                dlg.publisher.text(), dlg.category.text(), dlg.copies.value(), dlg.shelf.text()
            )
            self.refresh_all_data()

    def open_add_member_dialog(self):
        dlg = AddMemberDialog(self)
        if dlg.exec() == QDialog.Accepted:
            if not dlg.first_name.text() or not dlg.member_no.text():
                QMessageBox.warning(self, "Hata", "Üye No ve Ad alanları zorunludur!")
                return
            try:
                self.db.add_member(
                    dlg.member_no.text(), dlg.first_name.text(),
                    dlg.last_name.text(), dlg.phone.text(), dlg.email.text()
                )
                self.refresh_all_data()
            except sqlite3.IntegrityError:
                QMessageBox.critical(self, "Hata", "Bu Üye Numarası zaten kayıtlı!")

    def open_borrow_dialog(self):
        dlg = BorrowBookDialog(self.db, self)
        if dlg.exec() == QDialog.Accepted:
            book_id = dlg.combo_books.currentData()
            member_id = dlg.combo_members.currentData()
            days = dlg.days_box.value()

            if not book_id or not member_id:
                QMessageBox.warning(self, "Hata", "Geçerli bir kitap ve üye seçmelisiniz.")
                return

            try:
                self.db.borrow_book(book_id, member_id, days)
                self.refresh_all_data()
            except Exception as e:
                QMessageBox.critical(self, "Hata", str(e))

    def return_book_action(self, loan_id):
        try:
            self.db.return_loan(loan_id)
            self.refresh_all_data()
            QMessageBox.information(self, "Başarılı", "Kitap iade alındı ve stok güncellendi.")
        except Exception as e:
            QMessageBox.critical(self, "Hata", str(e))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    font = QFont("Inter", 10)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())