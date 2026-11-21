import ctypes
import sys
import json
import sqlite3
import time
from pathlib import Path
from collections import deque

from PySide6.QtCore import Qt, QTimer, Signal, QUrl
from PySide6.QtGui import QPixmap, QFont, QDesktopServices, QIcon
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest, QNetworkReply
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel,
    QPushButton, QLineEdit, QVBoxLayout, QHBoxLayout,
    QSplitter, QListWidget, QListWidgetItem, QScrollArea,
    QGridLayout, QSpinBox, QMessageBox, QInputDialog,
    QSizePolicy, QDialog, QProgressBar, QComboBox
)


# =========================================================
# 경로
# =========================================================

BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "database" / "products.db"
IMAGE_CACHE_DIR = BASE_DIR / "assets" / "images" / "products"
APP_ICON_PATH = BASE_DIR / "LHJ.ico"


# =========================================================
# 검색 별칭
# =========================================================

SEARCH_ALIASES = {
    "샤시": "섀시",
    "차체": "섀시",
    "룰러": "롤러",
    "로라": "롤러",
    "타야": "타이어",
    "모타": "모터",
    "기어": "기어",
    "베아링": "베어링",
    "베어링": "베어링",
    "브레이크": "브레이크",
    "플레이트": "플레이트",
    "댐퍼": "댐퍼",
    "스테빌": "스태빌라이저",
    "스태빌": "스태빌라이저",
    "보디": "보디",
    "바디": "보디",
}


PART_BUTTONS = [
    ("전체", None),
    ("모터", "모터"),
    ("기어", "기어"),
    ("섀시", "섀시"),
    ("타이어", "타이어"),
    ("롤러", "롤러"),
    ("브레이크", "브레이크"),
    ("플레이트", "플레이트"),
    ("베어링", "베어링"),
    ("샤프트", "샤프트"),
    ("댐퍼", "댐퍼"),
    ("보디", "보디"),
    ("나사류", "나사류"),
    ("스태빌라이저", "스태빌라이저"),
    ("스티커", "스티커"),
    ("캐미컬", "캐미컬"),
]


# =========================================================
# 스타일
# =========================================================

STYLE = """
QMainWindow, QWidget {
    background-color: #171a20;
    color: #e6e9ef;
    font-family: 'Malgun Gothic';
    font-size: 9pt;
}

QFrame#Header {
    background-color: #20252e;
    border: 1px solid #303744;
    border-radius: 7px;
}

QFrame#Panel {
    background-color: #20252e;
    border: 1px solid #303744;
    border-radius: 7px;
}

QFrame#ProductCard {
    background-color: #252b35;
    border: 1px solid #353e4b;
    border-radius: 7px;
}

QFrame#ProductCard:hover {
    border: 1px solid #5689d4;
    background-color: #2a3240;
}

QLabel#MainTitle {
    font-size: 17pt;
    font-weight: bold;
    color: #ffffff;
}

QLabel#SectionTitle {
    font-size: 11pt;
    font-weight: bold;
    color: #f1f3f7;
}

QLabel#Muted {
    color: #929dad;
}

QLabel#Price {
    color: #83b5ff;
    font-size: 12pt;
    font-weight: bold;
}

QLineEdit {
    background-color: #171c24;
    border: 1px solid #3a4351;
    border-radius: 5px;
    padding: 9px;
    color: white;
}

QLineEdit:focus {
    border: 1px solid #5689d4;
}

QPushButton {
    background-color: #303846;
    border: 1px solid #414d5e;
    border-radius: 5px;
    padding: 7px 10px;
    color: #e7ebf2;
}

QPushButton:hover {
    background-color: #3c485a;
}

QPushButton:pressed {
    background-color: #252c37;
}

QPushButton#Primary {
    background-color: #2868bb;
    border: 1px solid #397bcf;
    font-weight: bold;
}

QPushButton#Primary:hover {
    background-color: #367bd1;
}

QPushButton#SelectedCategory {
    background-color: #315f99;
    border: 1px solid #528bd0;
    color: white;
    font-weight: bold;
}

QPushButton#SmallDanger {
    background-color: #663940;
    border: 1px solid #88505a;
    padding: 4px 8px;
}

QListWidget {
    background-color: transparent;
    border: none;
    outline: none;
}

QListWidget::item {
    background-color: #272e39;
    border: 1px solid #343e4d;
    border-radius: 5px;
    padding: 10px;
    margin: 3px 1px;
}

QListWidget::item:selected {
    background-color: #31547e;
    border: 1px solid #5488c4;
}

QScrollArea {
    border: none;
    background-color: transparent;
}

QSpinBox {
    background-color: #171c24;
    border: 1px solid #414d5e;
    border-radius: 4px;
    padding: 4px;
}

QComboBox {
    background-color: #171c24;
    border: 1px solid #414d5e;
    border-radius: 5px;
    padding: 7px 9px;
    color: #e6e9ef;
    min-width: 125px;
}

QComboBox:hover {
    border: 1px solid #5689d4;
}

QComboBox::drop-down {
    border: none;
    width: 25px;
}

QComboBox QAbstractItemView {
    background-color: #252b35;
    color: #e6e9ef;
    selection-background-color: #315f99;
    border: 1px solid #414d5e;
}

QFrame#Ticker {
    background-color: #202a38;
    border: 1px solid #34445b;
    border-radius: 5px;
}

QProgressBar {
    background-color: #171c24;
    border: 1px solid #3a4351;
    border-radius: 5px;
    min-height: 13px;
    max-height: 13px;
}

QProgressBar::chunk {
    background-color: #367bd1;
    border-radius: 4px;
}
"""


# =========================================================
# 데이터베이스
# =========================================================

class ProductDatabase:

    def __init__(self):
        if not DATABASE_PATH.exists():
            raise FileNotFoundError(
                f"DB 파일을 찾을 수 없습니다.\n{DATABASE_PATH}"
            )

        self.conn = sqlite3.connect(
            DATABASE_PATH,
            timeout=30
        )
        self.conn.row_factory = sqlite3.Row

    def get_products(self):
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT
                p.goods_no,
                p.product_no,
                p.name,
                p.price,
                p.sale_status,
                p.image_path,
                p.product_url,
                p.specifications,
                p.compatibility,
                GROUP_CONCAT(DISTINCT c.name) AS category_names
            FROM products p
            LEFT JOIN product_categories pc
                ON p.goods_no = pc.goods_no
            LEFT JOIN categories c
                ON pc.category_code = c.category_code
            GROUP BY p.goods_no
            ORDER BY p.name COLLATE NOCASE
        """)

        return cursor.fetchall()

    def get_setting(self, key, default=None):
        cursor = self.conn.cursor()

        cursor.execute("""
            SELECT setting_value
            FROM settings
            WHERE setting_key = ?
        """, (key,))

        result = cursor.fetchone()

        return result["setting_value"] if result else default

    def save_setting(self, key, value):
        self.conn.execute("""
            INSERT INTO settings (setting_key, setting_value)
            VALUES (?, ?)
            ON CONFLICT(setting_key)
            DO UPDATE SET setting_value = excluded.setting_value
        """, (key, value))

        self.conn.commit()

    def close(self):
        self.conn.close()


# =========================================================
# 이미지 라벨
# =========================================================

class ProductImageLabel(QLabel):

    def __init__(self, parent=None):
        super().__init__(parent)

        self.source_pixmap = None

        self.setAlignment(Qt.AlignCenter)
        self.setMinimumWidth(0)
        self.setFixedHeight(190)

    def set_source_pixmap(self, pixmap):

        if pixmap is None or pixmap.isNull():
            return

        self.source_pixmap = pixmap
        self.setText("")
        self.update_image()

    def update_image(self):

        if self.source_pixmap is None:
            return

        if self.source_pixmap.isNull():
            return

        width = max(1, self.width() - 16)
        height = max(1, self.height() - 16)

        scaled = self.source_pixmap.scaled(
            width,
            height,
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )

        self.setPixmap(scaled)

    def resizeEvent(self, event):

        super().resizeEvent(event)
        self.update_image()


# =========================================================
# 공지 티커
# =========================================================

class NoticeTicker(QFrame):

    def __init__(self):
        super().__init__()

        self.setObjectName("Ticker")
        self.setFixedHeight(37)

        self.messages = [
            "[안내] 상품 데이터 업데이트 후 새로고침하면 최신 상품을 확인할 수 있습니다.",
            "[알림] 신규 상품이 등록되었는지 업데이트를 확인해 보세요.",
            "[안내] 할인 정보는 실제 확인된 경우에만 표시됩니다.",
        ]

        self.message_index = 0
        self.position = 0

        self.label = QLabel(self)
        self.label.setStyleSheet(
            "color: #dce7f6; font-weight: bold; background: transparent;"
        )

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.move_text)
        self.timer.start(25)

        self.set_message()

    def set_message(self):
        self.label.setText(self.messages[self.message_index])
        self.label.adjustSize()

        self.position = self.width()
        self.label.move(self.position, 9)

    def move_text(self):
        self.position += 2
        self.label.move(self.position, 9)

        if self.position + self.label.width() < 0:
            self.message_index = (
                self.message_index + 1
            ) % len(self.messages)

            self.set_message()

    def resizeEvent(self, event):
        if self.position == 0:
            self.position = self.width()

        super().resizeEvent(event)


# =========================================================
# 비동기 상품 이미지 다운로드 및 캐시
# =========================================================

class ImageDownloadManager:

    def __init__(self, parent=None, max_concurrent=6):
        self.network = QNetworkAccessManager(parent)
        self.max_concurrent = max_concurrent
        self.active_count = 0

        self.queue = deque()

        self.pending = set()
        self.waiters = {}

        IMAGE_CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def cache_path(self, goods_no):
        return IMAGE_CACHE_DIR / f"{goods_no}.png"

    @staticmethod
    def set_label_image(label, pixmap):

        if label is None or pixmap.isNull():
            return

        try:

            if isinstance(label, ProductImageLabel):
                label.set_source_pixmap(pixmap)

            else:
                width = max(1, label.width() - 12)
                height = max(1, label.height() - 10)

                label.setPixmap(
                    pixmap.scaled(
                        width,
                        height,
                        Qt.KeepAspectRatio,
                        Qt.SmoothTransformation
                    )
                )

                label.setText("")

        except RuntimeError:
            pass

    def request(self, goods_no, image_url, label):

        goods_no = str(goods_no)

        if not image_url:
            label.setText("이미지 없음")
            return

        image_url = str(image_url)

        if not image_url.startswith(("http://", "https://")):

            local_path = Path(image_url)

            if not local_path.is_absolute():
                local_path = BASE_DIR / local_path

            if local_path.exists():
                pixmap = QPixmap(str(local_path))

                if not pixmap.isNull():
                    self.set_label_image(label, pixmap)
                    return

            label.setText("이미지 없음")
            return

        cache_file = self.cache_path(goods_no)

        if cache_file.exists():
            pixmap = QPixmap(str(cache_file))

            if not pixmap.isNull():
                self.set_label_image(label, pixmap)
                return

            try:
                cache_file.unlink()
            except OSError:
                pass

        label.setText("이미지 로딩 중...")

        self.waiters.setdefault(goods_no, []).append(label)

        if goods_no not in self.pending:
            self.pending.add(goods_no)
            self.queue.append((goods_no, image_url))
            self._start_next()

    def _start_next(self):

        while (
            self.queue
            and self.active_count < self.max_concurrent
        ):

            goods_no, image_url = self.queue.popleft()

            request = QNetworkRequest(QUrl(image_url))

            request.setRawHeader(
                b"User-Agent",
                b"Mozilla/5.0"
            )

            request.setRawHeader(
                b"Accept",
                b"image/avif,image/webp,image/apng,image/*,*/*;q=0.8"
            )

            reply = self.network.get(request)

            self.active_count += 1

            reply.finished.connect(
                lambda code=goods_no, url=image_url, rep=reply:
                    self._download_finished(code, url, rep)
            )

    def _download_finished(self, goods_no, image_url, reply):

        pixmap = QPixmap()

        try:
            status = reply.attribute(
                QNetworkRequest.HttpStatusCodeAttribute
            )

            data = bytes(reply.readAll())

            if (
                reply.error() == QNetworkReply.NetworkError.NoError
                and (status is None or int(status) == 200)
                and data
                and pixmap.loadFromData(data)
            ):

                cache_file = self.cache_path(goods_no)

                if not pixmap.save(str(cache_file), "PNG"):
                    pixmap = QPixmap()

            else:
                pixmap = QPixmap()

        except Exception:
            pixmap = QPixmap()

        finally:
            reply.deleteLater()

            self.active_count = max(
                0,
                self.active_count - 1
            )

            self.pending.discard(goods_no)

        labels = self.waiters.pop(goods_no, [])

        for label in labels:
            if not pixmap.isNull():
                self.set_label_image(label, pixmap)
            else:
                try:
                    label.setText("이미지 없음")
                except RuntimeError:
                    pass

        self._start_next()


# =========================================================
# 상품 카드
# =========================================================

class ProductCard(QFrame):

    add_requested = Signal(str)
    detail_requested = Signal(str)

    def __init__(self, product, image_manager):
        super().__init__()

        self.product = product
        self.goods_no = str(product["goods_no"])

        self.setObjectName("ProductCard")
        self.setFixedHeight(370)
        self.setCursor(Qt.PointingHandCursor)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(11, 10, 11, 10)
        layout.setSpacing(6)

        image_label = ProductImageLabel()

        image_label.setStyleSheet(
            "background-color: #1b2028; border-radius: 5px;"
        )

        image_path = product["image_path"]

        image_manager.request(
            self.goods_no,
            image_path,
            image_label
        )

        layout.addWidget(image_label)

        name = QLabel(product["name"])
        name.setWordWrap(True)
        name.setMaximumHeight(38)

        name.setStyleSheet(
            "font-weight: bold; color: #f0f2f6;"
        )

        layout.addWidget(name)

        product_no = QLabel(
            f"제품 번호: {product['product_no'] or '-'}"
        )

        product_no.setObjectName("Muted")

        layout.addWidget(product_no)

        bottom = QHBoxLayout()

        if product["price"] is None:
            price_text = "가격 확인 필요"
        else:
            price_text = f"{int(product['price']):,}원"

        price = QLabel(price_text)
        price.setObjectName("Price")

        bottom.addWidget(price)
        bottom.addStretch()

        status = QLabel(
            self.get_status(product["sale_status"])
        )

        status.setObjectName("Muted")

        bottom.addWidget(status)

        layout.addLayout(bottom)

        buttons = QHBoxLayout()

        detail_button = QPushButton("상세")

        detail_button.clicked.connect(
            lambda: self.detail_requested.emit(self.goods_no)
        )

        add_button = QPushButton("담기")
        add_button.setObjectName("Primary")

        add_button.clicked.connect(
            lambda: self.add_requested.emit(self.goods_no)
        )

        buttons.addWidget(detail_button)
        buttons.addWidget(add_button)

        layout.addLayout(buttons)

    @staticmethod
    def get_status(status):

        names = {
            "available": "판매 가능",
            "unavailable": "구매 제한",
            "member_restricted": "회원 전용",
            "sold_out": "품절",
            "soldout": "품절",
            "unknown": "상태 확인 필요",
        }

        return names.get(
            (status or "unknown").lower(),
            "상태 확인 필요"
        )


# =========================================================
# 메인 윈도우
# =========================================================

class MiniCarWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        startup_start = time.perf_counter()

        db_start = time.perf_counter()

        self.db = ProductDatabase()

        print(
            f"[시작 측정] DB 연결: "
            f"{time.perf_counter() - db_start:.3f}초"
        )

        self.products = []

        self.product_by_goods_no = {}
        self.search_records = []

        self.image_manager = ImageDownloadManager(
            self,
            max_concurrent=6
        )

        self.current_category = None
        self.current_keyword = ""

        # 기본 정렬 방식
        self.current_sort = "기본순"

        self.cart = {}
        self.tuning_files = {}
        self.active_file = None

        self.products_loaded = False

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(200)
        self.search_timer.timeout.connect(
            self.refresh_products
        )

        self.render_timer = QTimer(self)
        self.render_timer.setInterval(16)
        self.render_timer.timeout.connect(
            self._render_product_batch
        )

        self.render_generation = 0
        self.render_results = []
        self.render_index = 0

        self.load_tuning_files()

        self.setWindowTitle("MINI 4WD TUNING")

        if APP_ICON_PATH.exists():
            self.setWindowIcon(QIcon(str(APP_ICON_PATH)))

        self.resize(1550, 920)
        self.setMinimumSize(1200, 750)

        self.setStyleSheet(STYLE)

        ui_start = time.perf_counter()

        self.setup_ui()
        self.refresh_files()
        self.refresh_order_panel()

        print(
            f"[시작 측정] 기본 UI 생성: "
            f"{time.perf_counter() - ui_start:.3f}초"
        )

        print(
            f"[시작 측정] 창 초기화 완료: "
            f"{time.perf_counter() - startup_start:.3f}초"
        )

        self.statusBar().showMessage(
            "상품 데이터를 불러올 준비가 되었습니다."
        )

    # -----------------------------------------------------
    # 상품 데이터 초기 로딩
    # -----------------------------------------------------

    def initialize_products(self):

        if self.products_loaded:
            return

        total_start = time.perf_counter()

        self.statusBar().showMessage(
            "상품 데이터를 불러오는 중..."
        )

        db_start = time.perf_counter()

        try:
            self.products = self.db.get_products()

        except Exception as error:

            self.statusBar().showMessage(
                f"상품 데이터 로딩 실패: {error}"
            )

            QMessageBox.critical(
                self,
                "상품 데이터 로딩 실패",
                str(error)
            )

            return

        db_elapsed = time.perf_counter() - db_start

        print(
            f"[시작 측정] 상품 DB 조회: "
            f"{db_elapsed:.3f}초 "
            f"({len(self.products):,}개)"
        )

        index_start = time.perf_counter()

        self.rebuild_product_indexes()

        index_elapsed = time.perf_counter() - index_start

        print(
            f"[시작 측정] 검색 인덱스 생성: "
            f"{index_elapsed:.3f}초"
        )

        self.products_loaded = True

        render_start = time.perf_counter()

        self.refresh_products()

        print(
            f"[시작 측정] 첫 상품 카드 생성 요청: "
            f"{time.perf_counter() - render_start:.3f}초"
        )

        print(
            f"[시작 측정] 상품 데이터 초기 처리: "
            f"{time.perf_counter() - total_start:.3f}초"
        )

    # -----------------------------------------------------
    # 상품 인덱스
    # -----------------------------------------------------

    def rebuild_product_indexes(self):

        self.product_by_goods_no = {}
        self.search_records = []

        for product in self.products:

            goods_no = str(product["goods_no"])

            self.product_by_goods_no[goods_no] = product

            name = (product["name"] or "").lower()

            categories = (
                product["category_names"] or ""
            ).lower()

            self.search_records.append(
                (product, name, categories)
            )

    # -----------------------------------------------------
    # 전체 화면
    # -----------------------------------------------------

    def setup_ui(self):

        central = QWidget()
        self.setCentralWidget(central)

        main = QVBoxLayout(central)

        main.setContentsMargins(10, 10, 10, 8)
        main.setSpacing(8)

        # 헤더
        header = QFrame()
        header.setObjectName("Header")
        header.setFixedHeight(56)

        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(14, 5, 14, 5)

        title = QLabel("MINI 4WD TUNING")
        title.setObjectName("MainTitle")

        header_layout.addWidget(title)
        header_layout.addStretch()

        self.refresh_button = QPushButton("⟳ 프로그램 리로드")
        self.refresh_button.setMinimumWidth(145)
        self.refresh_button.setObjectName("Primary")

        self.refresh_button.clicked.connect(
            self.refresh_database
        )

        header_layout.addWidget(self.refresh_button)

        main.addWidget(header)

        # 파츠 카테고리
        category_frame = QFrame()
        category_frame.setObjectName("Header")

        category_layout = QHBoxLayout(category_frame)

        category_layout.setContentsMargins(8, 7, 8, 7)
        category_layout.setSpacing(5)

        self.category_buttons = {}

        for label, category in PART_BUTTONS:

            button = QPushButton(label)
            button.setMinimumWidth(65)
            button.setCheckable(True)

            button.clicked.connect(
                lambda checked=False, value=category:
                    self.select_category(value)
            )

            self.category_buttons[label] = button
            category_layout.addWidget(button)

        # 선택된 조합 표시 영역은 없음
        category_layout.addStretch()

        main.addWidget(category_frame)

        # 검색창
        search_layout = QHBoxLayout()

        self.search_input = QLineEdit()

        self.search_input.setPlaceholderText(
            "상품명 또는 파츠 별칭 검색  (예: 샤시, 룰러, 타야)"
        )

        self.search_input.textChanged.connect(
            self.on_search_changed
        )

        search_layout.addWidget(self.search_input)

        main.addLayout(search_layout)

        # 중앙 화면
        splitter = QSplitter(Qt.Horizontal)

        splitter.addWidget(self.create_file_panel())
        splitter.addWidget(self.create_product_panel())
        splitter.addWidget(self.create_order_panel())

        splitter.setSizes([235, 850, 330])

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setStretchFactor(2, 0)

        main.addWidget(splitter, 1)

        self.ticker = NoticeTicker()
        main.addWidget(self.ticker)

        self.statusBar().showMessage(
            "상품 데이터 로딩 대기 중..."
        )

    # -----------------------------------------------------
    # 좌측 튜닝 파일
    # -----------------------------------------------------

    def create_file_panel(self):

        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setMinimumWidth(190)

        layout = QVBoxLayout(panel)

        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("TUNING FILES")
        title.setObjectName("SectionTitle")

        layout.addWidget(title)

        description = QLabel("저장된 튜닝 조합")
        description.setObjectName("Muted")

        layout.addWidget(description)

        self.file_list = QListWidget()

        self.file_list.currentItemChanged.connect(
            self.on_file_selected
        )

        layout.addWidget(self.file_list, 1)

        new_button = QPushButton("+ 새 조합")
        new_button.setObjectName("Primary")

        new_button.clicked.connect(
            self.create_new_file
        )

        layout.addWidget(new_button)

        save_button = QPushButton("현재 조합 저장")
        save_button.clicked.connect(
            self.save_active_file
        )

        layout.addWidget(save_button)

        file_buttons = QHBoxLayout()

        rename_button = QPushButton("이름 변경")
        rename_button.clicked.connect(
            self.rename_file
        )

        delete_button = QPushButton("삭제")
        delete_button.setObjectName("SmallDanger")

        delete_button.clicked.connect(
            self.delete_file
        )

        file_buttons.addWidget(rename_button)
        file_buttons.addWidget(delete_button)

        layout.addLayout(file_buttons)

        return panel

    # -----------------------------------------------------
    # 중앙 상품 패널
    # -----------------------------------------------------

    def create_product_panel(self):

        panel = QFrame()
        panel.setObjectName("Panel")

        layout = QVBoxLayout(panel)

        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # 상품 제목 + 정렬 메뉴
        top = QHBoxLayout()

        self.product_title = QLabel("전체 상품")
        self.product_title.setObjectName("SectionTitle")

        top.addWidget(self.product_title)
        top.addStretch()

        sort_label = QLabel("정렬")
        sort_label.setObjectName("Muted")

        top.addWidget(sort_label)

        self.sort_combo = QComboBox()

        self.sort_combo.addItems([
            "기본순",
            "낮은 가격순",
            "높은 가격순",
            "상품명순",
        ])

        self.sort_combo.setCurrentText("기본순")

        self.sort_combo.currentTextChanged.connect(
            self.on_sort_changed
        )

        top.addWidget(self.sort_combo)

        self.product_count = QLabel("로딩 대기 중")
        self.product_count.setObjectName("Muted")

        top.addWidget(self.product_count)

        layout.addLayout(top)

        self.product_scroll = QScrollArea()
        self.product_scroll.setWidgetResizable(True)

        self.product_container = QWidget()

        self.product_grid = QGridLayout(
            self.product_container
        )

        self.product_grid.setContentsMargins(4, 4, 4, 4)
        self.product_grid.setSpacing(10)
        self.product_grid.setAlignment(Qt.AlignTop)

        for column in range(3):
            self.product_grid.setColumnStretch(column, 1)

        self.product_scroll.setWidget(
            self.product_container
        )

        layout.addWidget(self.product_scroll, 1)

        return panel

    # -----------------------------------------------------
    # 우측 주문 패널
    # -----------------------------------------------------

    def create_order_panel(self):

        panel = QFrame()
        panel.setObjectName("Panel")
        panel.setMinimumWidth(270)
        panel.setMaximumWidth(410)

        layout = QVBoxLayout(panel)

        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        title = QLabel("ORDER / QUOTE")
        title.setObjectName("SectionTitle")

        layout.addWidget(title)

        self.order_count = QLabel("선택 파츠 0개")
        self.order_count.setObjectName("Muted")

        layout.addWidget(self.order_count)

        self.order_scroll = QScrollArea()
        self.order_scroll.setWidgetResizable(True)

        self.order_container = QWidget()

        self.order_layout = QVBoxLayout(
            self.order_container
        )

        self.order_layout.setContentsMargins(2, 2, 2, 2)
        self.order_layout.setSpacing(7)
        self.order_layout.setAlignment(Qt.AlignTop)

        self.order_scroll.setWidget(self.order_container)

        layout.addWidget(self.order_scroll, 1)

        self.quote_name = QLineEdit()
        self.quote_name.setPlaceholderText("튜닝 조합 이름")

        layout.addWidget(self.quote_name)

        self.budget_input = QSpinBox()

        self.budget_input.setRange(
            0,
            2_000_000_000
        )

        self.budget_input.setSingleStep(10000)
        self.budget_input.setSuffix(" 원")
        self.budget_input.setPrefix("예산 ")

        layout.addWidget(self.budget_input)

        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        divider.setStyleSheet("color: #3b4553;")

        layout.addWidget(divider)

        self.total_label = QLabel("0원")
        self.total_label.setObjectName("Price")

        self.total_label.setStyleSheet(
            "font-size: 20pt; font-weight: bold; color: #83b5ff;"
        )

        layout.addWidget(QLabel("예상 합계"))
        layout.addWidget(self.total_label)

        self.budget_label = QLabel("예산 미설정")
        self.budget_label.setObjectName("Muted")

        layout.addWidget(self.budget_label)

        self.quote_name.textChanged.connect(
            self.on_quote_info_changed
        )

        self.budget_input.valueChanged.connect(
            self.on_quote_info_changed
        )

        return panel

    # -----------------------------------------------------
    # 데이터 리로드
    # -----------------------------------------------------

    def refresh_database(self):

        if not self.refresh_button.isEnabled():
            return

        self.refresh_button.setEnabled(False)
        self.refresh_button.setText("리로드 중...")

        self.statusBar().showMessage(
            "프로그램 데이터를 다시 불러오는 중..."
        )

        self.reload_dialog = QDialog(self)

        self.reload_dialog.setWindowTitle("프로그램 리로드")
        self.reload_dialog.setModal(True)
        self.reload_dialog.setFixedSize(430, 155)

        self.reload_dialog.setWindowFlags(
            self.reload_dialog.windowFlags()
            & ~Qt.WindowContextHelpButtonHint
        )

        self.reload_dialog.setStyleSheet("""
            QDialog {
                background-color: #20252e;
                color: #e6e9ef;
                border: 1px solid #5689d4;
                border-radius: 9px;
            }
            QLabel {
                background: transparent;
                border: none;
            }
        """)

        dialog_layout = QVBoxLayout(
            self.reload_dialog
        )

        dialog_layout.setContentsMargins(24, 20, 24, 18)
        dialog_layout.setSpacing(12)

        loading_title = QLabel(
            "프로그램 데이터를 불러오고 있습니다"
        )

        loading_title.setStyleSheet(
            "font-size: 12pt; font-weight: bold; color: white;"
        )

        loading_title.setAlignment(Qt.AlignCenter)

        dialog_layout.addWidget(loading_title)

        loading_detail = QLabel(
            "상품 목록과 화면을 갱신하는 중입니다. 잠시만 기다려 주세요."
        )

        loading_detail.setObjectName("Muted")
        loading_detail.setAlignment(Qt.AlignCenter)

        dialog_layout.addWidget(loading_detail)

        progress = QProgressBar()
        progress.setRange(0, 0)
        progress.setTextVisible(False)

        dialog_layout.addWidget(progress)

        self.reload_dialog.show()

        QTimer.singleShot(
            450,
            self._perform_database_refresh
        )

    def _perform_database_refresh(self):

        try:
            self.products = self.db.get_products()

            self.rebuild_product_indexes()
            self.products_loaded = True

            self.refresh_products()
            self.refresh_order_panel()

            self.statusBar().showMessage(
                f"프로그램 리로드 완료 · DB 상품 {len(self.products):,}개",
                5000
            )

        except Exception as error:

            self.statusBar().showMessage(
                f"프로그램 리로드 실패: {error}",
                8000
            )

            QMessageBox.warning(
                self,
                "프로그램 리로드 실패",
                f"상품 목록을 다시 읽지 못했습니다.\n\n{error}"
            )

        finally:

            if hasattr(self, "reload_dialog") and self.reload_dialog:
                self.reload_dialog.close()
                self.reload_dialog.deleteLater()
                self.reload_dialog = None

            self.refresh_button.setEnabled(True)
            self.refresh_button.setText("⟳ 프로그램 리로드")

    # -----------------------------------------------------
    # 카테고리 / 검색
    # -----------------------------------------------------

    def select_category(self, category):

        self.current_category = category

        for label, value in PART_BUTTONS:

            button = self.category_buttons[label]

            selected = value == category

            button.setChecked(selected)

            button.setObjectName(
                "SelectedCategory" if selected else ""
            )

            button.style().unpolish(button)
            button.style().polish(button)

        self.refresh_products()

    def normalize_keyword(self, keyword):

        keyword = keyword.strip().lower()

        if keyword in SEARCH_ALIASES:
            return SEARCH_ALIASES[keyword]

        return keyword

    def on_search_changed(self, text):

        self.current_keyword = text.strip()
        self.search_timer.start()

    # -----------------------------------------------------
    # 정렬 기능
    # -----------------------------------------------------

    def on_sort_changed(self, sort_name):

        self.current_sort = sort_name

        # 검색어와 카테고리 조건은 유지하고
        # 현재 결과만 새 정렬 방식으로 다시 표시
        self.refresh_products()

    def sort_products(self, products):

        # 기본순은 DB에서 가져온 순서를 그대로 유지
        if self.current_sort == "기본순":
            return products

        if self.current_sort == "낮은 가격순":

            return sorted(
                products,
                key=lambda product: (
                    product["price"] is None,
                    (
                        int(product["price"])
                        if product["price"] is not None
                        else 0
                    )
                )
            )

        if self.current_sort == "높은 가격순":

            return sorted(
                products,
                key=lambda product: (
                    product["price"] is None,
                    -(
                        int(product["price"])
                        if product["price"] is not None
                        else 0
                    )
                )
            )

        if self.current_sort == "상품명순":

            return sorted(
                products,
                key=lambda product: (
                    product["name"] or ""
                ).casefold()
            )

        return products

    # -----------------------------------------------------
    # 상품 표시
    # -----------------------------------------------------

    def refresh_products(self):

        self.search_timer.stop()

        self.render_timer.stop()
        self.render_generation += 1

        self.clear_product_grid()

        keyword = self.current_keyword.lower()
        normalized = self.normalize_keyword(keyword)

        results = []

        # 먼저 카테고리와 검색어 필터링
        for product, name, categories in self.search_records:

            if self.current_category:

                if self.current_category not in categories:
                    continue

            if keyword:

                name_match = keyword in name
                normalized_match = normalized in name
                category_match = normalized in categories

                if not (
                    name_match
                    or normalized_match
                    or category_match
                ):
                    continue

            results.append(product)

        # 필터링된 결과에 정렬 적용
        results = self.sort_products(results)

        self.product_title.setText(
            self.current_category or "전체 상품"
        )

        self.product_count.setText(
            f"{len(results):,}개"
        )

        self.statusBar().showMessage(
            f"검색 결과 {len(results):,}개 · {self.current_sort}"
        )

        self.render_results = results
        self.render_index = 0

        if self.render_results:

            self._render_product_batch()

        else:

            self.render_timer.stop()

    def _render_product_batch(self):

        batch_size = 12

        end_index = min(
            self.render_index + batch_size,
            len(self.render_results)
        )

        columns = 3

        for index in range(self.render_index, end_index):

            product = self.render_results[index]

            card = ProductCard(
                product,
                self.image_manager
            )

            card.add_requested.connect(
                self.add_to_cart
            )

            card.detail_requested.connect(
                self.show_product_detail
            )

            row = index // columns
            column = index % columns

            self.product_grid.addWidget(
                card,
                row,
                column
            )

        self.render_index = end_index

        if self.render_index >= len(self.render_results):

            self.render_timer.stop()

            print(
                f"[상품 UI] 전체 카드 생성 완료: "
                f"{len(self.render_results):,}개"
            )

        else:

            if not self.render_timer.isActive():
                self.render_timer.start()

    def clear_product_grid(self):

        while self.product_grid.count():

            item = self.product_grid.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

    # -----------------------------------------------------
    # 상품 상세
    # -----------------------------------------------------

    def show_product_detail(self, goods_no):

        product = self.product_by_goods_no.get(
            str(goods_no)
        )

        if not product:
            return

        price = (
            "가격 확인 필요"
            if product["price"] is None
            else f"{int(product['price']):,}원"
        )

        message = (
            f"상품명: {product['name']}\n\n"
            f"제품 번호: {product['product_no'] or '-'}\n"
            f"내부 코드: {product['goods_no']}\n"
            f"카테고리: {product['category_names'] or '-'}\n"
            f"가격: {price}\n"
            f"판매 상태: {product['sale_status'] or 'unknown'}\n\n"
            f"규격:\n{product['specifications'] or '등록 정보 없음'}\n\n"
            f"호환 정보:\n{product['compatibility'] or '등록 정보 없음'}"
        )

        box = QMessageBox(self)

        box.setWindowTitle("상품 상세 정보")
        box.setText(message)
        box.setStandardButtons(QMessageBox.Ok)

        if product["product_url"]:

            shop_button = box.addButton(
                "타미야몰 열기",
                QMessageBox.ActionRole
            )

        else:
            shop_button = None

        box.exec()

        if shop_button and box.clickedButton() == shop_button:

            QDesktopServices.openUrl(
                QUrl(product["product_url"])
            )

    # -----------------------------------------------------
    # 장바구니 / 견적
    # -----------------------------------------------------

    def add_to_cart(self, goods_no):

        goods_no = str(goods_no)

        self.cart[goods_no] = (
            self.cart.get(goods_no, 0) + 1
        )

        self.refresh_order_panel()
        self.save_active_file()

        self.statusBar().showMessage(
            "현재 튜닝 조합에 파츠를 추가했습니다.",
            2500
        )

    def remove_from_cart(self, goods_no):

        self.cart.pop(str(goods_no), None)

        self.refresh_order_panel()
        self.save_active_file()

    def change_quantity(self, goods_no, quantity):

        self.cart[str(goods_no)] = quantity

        self.update_total()
        self.save_active_file()

    def refresh_order_panel(self):

        while self.order_layout.count():

            item = self.order_layout.takeAt(0)

            widget = item.widget()

            if widget:
                widget.deleteLater()

        valid_items = 0

        for goods_no, quantity in list(self.cart.items()):

            product = self.product_by_goods_no.get(
                str(goods_no)
            )

            if not product:
                continue

            valid_items += 1

            item_frame = QFrame()

            item_frame.setStyleSheet("""
                QFrame {
                    background-color: #272f3a;
                    border: 1px solid #384352;
                    border-radius: 5px;
                }
            """)

            item_layout = QVBoxLayout(item_frame)

            item_layout.setContentsMargins(8, 7, 8, 7)
            item_layout.setSpacing(5)

            name = QLabel(product["name"])
            name.setWordWrap(True)

            name.setStyleSheet(
                "font-weight: bold; border: none;"
            )

            item_layout.addWidget(name)

            row = QHBoxLayout()

            if product["price"] is None:
                price_text = "가격 확인 필요"
            else:
                price_text = f"{int(product['price']):,}원"

            price = QLabel(price_text)

            price.setStyleSheet(
                "color: #83b5ff; border: none;"
            )

            row.addWidget(price)
            row.addStretch()

            quantity_input = QSpinBox()

            quantity_input.setRange(1, 9999)
            quantity_input.setValue(quantity)
            quantity_input.setFixedWidth(75)

            quantity_input.valueChanged.connect(
                lambda value, code=goods_no:
                    self.change_quantity(code, value)
            )

            row.addWidget(quantity_input)

            remove_button = QPushButton("×")

            remove_button.setObjectName("SmallDanger")
            remove_button.setFixedWidth(28)

            remove_button.clicked.connect(
                lambda checked=False, code=goods_no:
                    self.remove_from_cart(code)
            )

            row.addWidget(remove_button)

            item_layout.addLayout(row)

            self.order_layout.addWidget(item_frame)

        self.order_count.setText(
            f"선택 파츠 {valid_items}종"
        )

        self.update_total()

    def update_total(self):

        total = 0

        for goods_no, quantity in self.cart.items():

            product = self.product_by_goods_no.get(
                str(goods_no)
            )

            if product and product["price"] is not None:

                total += (
                    int(product["price"]) * quantity
                )

        self.total_label.setText(
            f"{total:,}원"
        )

        budget = self.budget_input.value()

        if budget <= 0:

            self.budget_label.setText("예산 미설정")

        elif total > budget:

            self.budget_label.setText(
                f"예산 초과 {total - budget:,}원"
            )

        else:

            self.budget_label.setText(
                f"예산 잔액 {budget - total:,}원"
            )

    # -----------------------------------------------------
    # 튜닝 파일 관리
    # -----------------------------------------------------

    def load_tuning_files(self):

        saved = self.db.get_setting(
            "tuning_files",
            "{}"
        )

        try:

            data = json.loads(saved)

            self.tuning_files = data.get("files", {})
            self.active_file = data.get("active")

        except (ValueError, TypeError, json.JSONDecodeError):

            self.tuning_files = {}
            self.active_file = None

        if not self.tuning_files:

            self.tuning_files = {
                "기본 세팅": {
                    "cart": {},
                    "budget": 0
                }
            }

            self.active_file = "기본 세팅"

        if self.active_file not in self.tuning_files:

            self.active_file = next(
                iter(self.tuning_files)
            )

        self.load_active_file()

    def save_all_files(self):

        data = {
            "active": self.active_file,
            "files": self.tuning_files
        }

        self.db.save_setting(
            "tuning_files",
            json.dumps(data, ensure_ascii=False)
        )

    def load_active_file(self):

        if not self.active_file:
            self.cart = {}
            return

        data = self.tuning_files.get(
            self.active_file,
            {}
        )

        self.cart = {
            str(key): int(value)
            for key, value in data.get("cart", {}).items()
            if int(value) > 0
        }

    def save_active_file(self):

        if not self.active_file:
            return

        self.tuning_files[self.active_file] = {
            "cart": self.cart.copy(),
            "budget": self.budget_input.value()
                if hasattr(self, "budget_input") else 0
        }

        self.save_all_files()

    def refresh_files(self):

        self.file_list.blockSignals(True)
        self.file_list.clear()

        for name in self.tuning_files:

            item = QListWidgetItem(name)

            self.file_list.addItem(item)

            if name == self.active_file:
                self.file_list.setCurrentItem(item)

        self.file_list.blockSignals(False)

    def on_file_selected(self, current, previous):

        if not current:
            return

        new_name = current.text()

        if new_name == self.active_file:
            return

        self.save_active_file()

        self.active_file = new_name

        self.load_active_file()

        data = self.tuning_files.get(
            self.active_file,
            {}
        )

        self.budget_input.blockSignals(True)

        self.budget_input.setValue(
            int(data.get("budget", 0))
        )

        self.budget_input.blockSignals(False)

        self.refresh_order_panel()
        self.save_all_files()

    def create_new_file(self):

        name, accepted = QInputDialog.getText(
            self,
            "새 튜닝 조합",
            "새 조합 이름:"
        )

        if not accepted:
            return

        name = name.strip()

        if not name:
            return

        if name in self.tuning_files:

            QMessageBox.warning(
                self,
                "중복 이름",
                "이미 존재하는 조합 이름입니다."
            )

            return

        self.save_active_file()

        self.tuning_files[name] = {
            "cart": {},
            "budget": 0
        }

        self.active_file = name

        self.load_active_file()
        self.save_all_files()
        self.refresh_files()
        self.refresh_order_panel()

    def rename_file(self):

        if not self.active_file:
            return

        old_name = self.active_file

        new_name, accepted = QInputDialog.getText(
            self,
            "튜닝 조합 이름 변경",
            "새 이름:",
            text=old_name
        )

        if not accepted:
            return

        new_name = new_name.strip()

        if not new_name or new_name == old_name:
            return

        if new_name in self.tuning_files:

            QMessageBox.warning(
                self,
                "중복 이름",
                "이미 존재하는 이름입니다."
            )

            return

        self.save_active_file()

        self.tuning_files[new_name] = (
            self.tuning_files.pop(old_name)
        )

        self.active_file = new_name

        self.save_all_files()
        self.refresh_files()

    def delete_file(self):

        if not self.active_file:
            return

        if len(self.tuning_files) <= 1:

            QMessageBox.information(
                self,
                "삭제 불가",
                "마지막 튜닝 조합은 삭제할 수 없습니다."
            )

            return

        answer = QMessageBox.question(
            self,
            "튜닝 조합 삭제",
            f"'{self.active_file}' 조합을 삭제할까요?",
            QMessageBox.Yes | QMessageBox.No
        )

        if answer != QMessageBox.Yes:
            return

        del self.tuning_files[self.active_file]

        self.active_file = next(
            iter(self.tuning_files)
        )

        self.load_active_file()
        self.save_all_files()
        self.refresh_files()
        self.refresh_order_panel()

    def on_quote_info_changed(self):

        self.update_total()
        self.save_active_file()

    # -----------------------------------------------------
    # 종료
    # -----------------------------------------------------

    def closeEvent(self, event):

        self.search_timer.stop()
        self.render_timer.stop()

        self.save_active_file()
        self.save_all_files()

        self.db.close()

        event.accept()


# =========================================================
# 실행
# =========================================================


def main():

    # Windows 작업 표시줄 앱 식별자 설정
    # 반드시 QApplication 생성 전에 실행해야 함
    if sys.platform == "win32":
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
            "MiniCar.Tuning.Application"
        )

    app = QApplication(sys.argv)

    app.setFont(
        QFont("Malgun Gothic", 9)
    )

    # 아이콘 경로
    icon_path = BASE_DIR / "LHJ.ico"

    app_icon = QIcon(str(icon_path))

    if app_icon.isNull():
        print(f"[아이콘 오류] 아이콘 파일을 읽을 수 없습니다: {icon_path}")
    else:
        app.setWindowIcon(app_icon)
        print(f"[아이콘] QApplication 아이콘 적용: {icon_path}")

    try:

        window = MiniCarWindow()

        # 메인 창 아이콘 지정
        if not app_icon.isNull():
            window.setWindowIcon(app_icon)

        # 아이콘 설정 이후 창 표시
        window.show()

        QTimer.singleShot(
            0,
            window.initialize_products
        )

        sys.exit(app.exec())

    except Exception as error:

        QMessageBox.critical(
            None,
            "실행 오류",
            str(error)
        )

        sys.exit(1)


if __name__ == "__main__":
    main()
