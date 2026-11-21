
import re
import sqlite3
import time

from datetime import datetime
from pathlib import Path
from urllib.parse import (
    urljoin,
    urlparse,
    parse_qs,
    urlencode,
    urlunparse
)

import httpx
from bs4 import BeautifulSoup
from PySide6.QtCore import QThread, Signal


# =========================================================
# 기본 설정
# =========================================================

BASE_URL = "https://kidult-hobby.co.kr"

DB_PATH = Path(__file__).parent / "database" / "products.db"

REQUEST_INTERVAL = 0.5

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    )
}


# =========================================================
# 수집 대상 카테고리
# =========================================================

CATEGORIES = [
    {
        "code": "009020",
        "name": "미니카 본체",
        "parent": "009",
        "included": 1,
        "necessity": "미정"
    },
    {
        "code": "009002001",
        "name": "싱글 샤프트 모터",
        "parent": "009002",
        "included": 1,
        "necessity": "필수"
    },
    {
        "code": "009002002",
        "name": "더블 샤프트 모터",
        "parent": "009002",
        "included": 1,
        "necessity": "필수"
    },
    {
        "code": "009009002",
        "name": "캐미컬",
        "parent": "009009",
        "included": 1,
        "necessity": "미정"
    },
    {
        "code": "009009005",
        "name": "롤러",
        "parent": "009009",
        "included": 1,
        "necessity": "필수"
    },
    {
        "code": "009009006",
        "name": "플레이트",
        "parent": "009009",
        "included": 1,
        "necessity": "미정"
    },
    {
        "code": "009009007",
        "name": "브레이크",
        "parent": "009009",
        "included": 1,
        "necessity": "미정"
    },
    {
        "code": "009009008",
        "name": "튠업세트",
        "parent": "009009",
        "included": 1,
        "necessity": "미정"
    },
    {
        "code": "009009009",
        "name": "베어링",
        "parent": "009009",
        "included": 1,
        "necessity": "미정"
    },
    {
        "code": "009009010",
        "name": "샤프트",
        "parent": "009009",
        "included": 1,
        "necessity": "미정"
    },
    {
        "code": "009009011",
        "name": "댐퍼",
        "parent": "009009",
        "included": 1,
        "necessity": "미정"
    },
    {
        "code": "009009012",
        "name": "기어 및 터미널",
        "parent": "009009",
        "included": 1,
        "necessity": "필수"
    },
    {
        "code": "009009013",
        "name": "섀시 파트",
        "parent": "009009",
        "included": 1,
        "necessity": "필수"
    },
    {
        "code": "009009014",
        "name": "보디 파트",
        "parent": "009009",
        "included": 1,
        "necessity": "미정"
    },
    {
        "code": "009009015",
        "name": "휠 및 타이어",
        "parent": "009009",
        "included": 1,
        "necessity": "필수"
    },
    {
        "code": "009009016",
        "name": "나사류 및 와셔",
        "parent": "009009",
        "included": 1,
        "necessity": "미정"
    },
    {
        "code": "009009017",
        "name": "스태빌라이저",
        "parent": "009009",
        "included": 1,
        "necessity": "미정"
    },
    {
        "code": "009023",
        "name": "스티커",
        "parent": "009",
        "included": 1,
        "necessity": "미정"
    }
]


# =========================================================
# DB 관리
# =========================================================

class ProductDatabase:

    def __init__(self, db_path=DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.connection = sqlite3.connect(
            str(self.db_path),
            timeout=30
        )

        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.execute("PRAGMA journal_mode = WAL")

        self.cursor = self.connection.cursor()

        self.register_categories()

    def register_categories(self):

        parent_categories = [
            ("009", "미니카(4WD)", None),
            ("009002", "모터", "009"),
            ("009009", "옵션파트", "009"),
        ]

        for code, name, parent in parent_categories:
            self.cursor.execute("""
                INSERT OR IGNORE INTO categories (
                    category_code,
                    name,
                    parent_code,
                    included,
                    necessity
                )
                VALUES (?, ?, ?, 0, '미정')
            """, (code, name, parent))

        for category in CATEGORIES:
            self.cursor.execute("""
                INSERT OR IGNORE INTO categories (
                    category_code,
                    name,
                    parent_code,
                    included,
                    necessity
                )
                VALUES (?, ?, ?, ?, ?)
            """, (
                category["code"],
                category["name"],
                category["parent"],
                category["included"],
                category["necessity"]
            ))

        self.connection.commit()

    def save_product(self, product):

        now = datetime.now().isoformat(timespec="seconds")

        self.cursor.execute("""
            INSERT INTO products (
                goods_no,
                product_no,
                name,
                price,
                sale_status,
                price_checked_at,
                image_path,
                product_url,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)

            ON CONFLICT(goods_no)
            DO UPDATE SET

                product_no = COALESCE(
                    excluded.product_no,
                    products.product_no
                ),

                name = excluded.name,

                price = COALESCE(
                    excluded.price,
                    products.price
                ),

                sale_status = CASE
                    WHEN excluded.sale_status != 'unknown'
                    THEN excluded.sale_status
                    ELSE products.sale_status
                END,

                price_checked_at = CASE
                    WHEN excluded.price IS NOT NULL
                    THEN excluded.price_checked_at
                    ELSE products.price_checked_at
                END,

                image_path = COALESCE(
                    excluded.image_path,
                    products.image_path
                ),

                product_url = excluded.product_url,

                updated_at = excluded.updated_at

        """, (
            product["goods_no"],
            product["product_no"],
            product["name"],
            product["price"],
            product["sale_status"],
            now if product["price"] is not None else None,
            product["image_path"],
            product["product_url"],
            now
        ))

        self.cursor.execute("""
            INSERT OR IGNORE INTO product_categories (
                goods_no,
                category_code
            )
            VALUES (?, ?)
        """, (
            product["goods_no"],
            product["category_code"]
        ))

    def add_error(self, goods_no, error_type, message):

        self.cursor.execute("""
            INSERT INTO crawl_errors (
                goods_no,
                error_type,
                error_message
            )
            VALUES (?, ?, ?)
        """, (
            goods_no,
            error_type,
            str(message)[:1000]
        ))

    def cleanup_old_errors(self):

        self.cursor.execute("""
            DELETE FROM crawl_errors
            WHERE occurred_at < datetime('now', '-7 days')
        """)

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.commit()
        self.connection.close()


# =========================================================
# 크롤러
# =========================================================

class TamiyaCrawler:

    def __init__(self, database, log_callback=None):

        self.database = database
        self.log_callback = log_callback

        self.client = httpx.Client(
            headers=HEADERS,
            timeout=20,
            follow_redirects=True
        )

    def log(self, message):

        if self.log_callback:
            self.log_callback(message)

    @staticmethod
    def extract_goods_no(url):

        query = parse_qs(urlparse(url).query)
        values = query.get("goodsNo", [])

        return values[0] if values else None

    @staticmethod
    def extract_product_no(name):

        match = re.search(r"\[(\d{4,6})\]", name)

        if match:
            return match.group(1)

        return None

    @staticmethod
    def extract_price(text):

        if not text:
            return None

        cleaned = text.replace(",", "").replace("원", "")
        match = re.search(r"\d+", cleaned)

        if match:
            return int(match.group())

        return None

    def request_page(self, url):

        response = self.client.get(url)
        response.raise_for_status()

        time.sleep(REQUEST_INTERVAL)

        return BeautifulSoup(response.text, "html.parser")

    # -----------------------------------------------------
    # 상세 페이지 판매 상태 확인
    # -----------------------------------------------------

    def get_detail_sale_status(self, product_url):

        try:
            soup = self.request_page(product_url)

            page_text = soup.get_text(" ", strip=True)

            # 회원 제한 문구를 먼저 확인한다.
            if (
                "회원전용상품" in page_text
                or "로그인해주세요" in page_text
            ):
                return "member_restricted"

            # 활성화된 구매 버튼 확인
            active_buttons = soup.select(
                ".btn_add_cart:not([disabled]), "
                ".btn_add_order:not([disabled]), "
                ".btn_shop_cart:not([disabled]), "
                ".btn_shop_buy:not([disabled])"
            )

            if active_buttons:
                return "available"

            # 상세 페이지의 실제 품절 표시 확인
            soldout_images = soup.select(
                "img[alt='품절']"
            )

            soldout_buttons = soup.select(
                ".btn_shop_soldout, .btn_add_soldout"
            )

            has_soldout_text = "품절" in page_text

            if soldout_images or soldout_buttons or has_soldout_text:
                return "sold_out"

            return "unknown"

        except Exception as error:

            self.log(
                f"[상세 상태 확인 실패] {product_url} / {error}"
            )

            return "unknown"

    # -----------------------------------------------------
    # 상품 목록 추출
    # -----------------------------------------------------

    def get_product_cards(self, soup):

        cards = soup.select(
            ".item_basket_type li, .item_gallery_type li"
        )

        results = []

        for card in cards:

            link = card.select_one(
                "a[href*='goods_view.php']"
            )

            if not link:
                continue

            product_url = urljoin(
                BASE_URL,
                link.get("href", "")
            )

            goods_no = self.extract_goods_no(product_url)

            if not goods_no:
                continue

            name_element = card.select_one(".item_name")

            if name_element:
                name = name_element.get_text(" ", strip=True)
            else:
                name = link.get_text(" ", strip=True)

            if not name:
                continue

            price_element = card.select_one(".item_price")

            price = None

            if price_element:
                price = self.extract_price(
                    price_element.get_text(" ", strip=True)
                )

            image_element = card.select_one("img")

            image_url = None

            if image_element:

                image_url = (
                    image_element.get("data-src")
                    or image_element.get("src")
                )

                if image_url:
                    image_url = urljoin(BASE_URL, image_url)

            card_classes = set(card.get("class", []))

            soldout_marker = card.select_one(
                ".item_soldout_bg, "
                ".item_icon_box img[alt='품절']"
            )

            cart_button = card.select_one(
                ".btn_add_cart_, .btn_basket_cart"
            )

            # 기본 상태 판별
            if (
                "item_soldout" in card_classes
                or soldout_marker is not None
            ):

                # 목록의 품절 표시만으로 최종 판단하지 않는다.
                # 상세 페이지에서 회원 제한 여부를 추가 확인한다.
                sale_status = self.get_detail_sale_status(
                    product_url
                )

                if sale_status == "unknown":
                    sale_status = "sold_out"

            elif cart_button is not None:

                sale_status = "available"

            else:

                sale_status = "unknown"

            results.append({
                "goods_no": goods_no,
                "product_no": self.extract_product_no(name),
                "name": name,
                "price": price,
                "sale_status": sale_status,
                "image_path": image_url,
                "product_url": product_url
            })

        return results

    # -----------------------------------------------------
    # 페이지 이동 링크 수집
    # -----------------------------------------------------

    def get_page_urls(self, soup, current_url, category_code):

        urls = set()

        for link in soup.select("a[href]"):

            href = link.get("href", "")

            if "goods_list.php" not in href:
                continue

            full_url = urljoin(current_url, href)

            parsed = urlparse(full_url)
            query = parse_qs(parsed.query)

            current_category = query.get(
                "cateCd",
                [None]
            )[0]

            if current_category not in (None, category_code):
                continue

            page_values = query.get("page", [])

            if not page_values:
                continue

            if not page_values[0].isdigit():
                continue

            query["cateCd"] = [category_code]

            new_query = urlencode(
                query,
                doseq=True
            )

            full_url = urlunparse((
                parsed.scheme,
                parsed.netloc,
                parsed.path,
                parsed.params,
                new_query,
                parsed.fragment
            ))

            urls.add(full_url)

        return urls

    # -----------------------------------------------------
    # 카테고리 수집
    # -----------------------------------------------------

    def crawl_category(self, category, progress_callback=None):

        category_code = category["code"]

        start_url = (
            f"{BASE_URL}/goods/goods_list.php"
            f"?cateCd={category_code}"
        )

        pending_urls = [start_url]
        visited_urls = set()

        saved_count = 0

        while pending_urls:

            url = pending_urls.pop(0)

            if url in visited_urls:
                continue

            visited_urls.add(url)

            try:

                soup = self.request_page(url)

                next_urls = self.get_page_urls(
                    soup,
                    url,
                    category_code
                )

                for next_url in next_urls:

                    if (
                        next_url not in visited_urls
                        and next_url not in pending_urls
                    ):
                        pending_urls.append(next_url)

                products = self.get_product_cards(soup)

                for product in products:

                    product["category_code"] = category_code

                    try:

                        self.database.save_product(product)
                        saved_count += 1

                    except Exception as error:

                        self.database.add_error(
                            product.get("goods_no"),
                            "database_error",
                            error
                        )

                self.database.commit()

                if progress_callback:

                    progress_callback(
                        category["name"],
                        len(visited_urls),
                        len(visited_urls) + len(pending_urls)
                    )

                self.log(
                    f"[{category['name']}] "
                    f"{len(products)}개 상품 확인"
                )

            except Exception as error:

                self.database.add_error(
                    None,
                    "page_error",
                    f"{url} : {error}"
                )

                self.database.commit()

                self.log(
                    f"[오류] {category['name']} / {url} / {error}"
                )

        return saved_count

    def close(self):
        self.client.close()


# =========================================================
# PySide6 백그라운드 작업
# =========================================================

class CrawlerWorker(QThread):

    progress = Signal(str, int, int)
    log_message = Signal(str)
    completed = Signal(int, int)
    failed = Signal(str)

    def __init__(self, db_path=DB_PATH):

        super().__init__()

        self.db_path = Path(db_path)

    def run(self):

        database = None
        crawler = None

        total_saved = 0
        failed_categories = 0

        try:

            database = ProductDatabase(self.db_path)

            crawler = TamiyaCrawler(
                database,
                log_callback=self.log_message.emit
            )

            for category in CATEGORIES:

                if self.isInterruptionRequested():
                    break

                self.log_message.emit(
                    f"카테고리 시작: {category['name']}"
                )

                try:

                    count = crawler.crawl_category(
                        category,
                        progress_callback=lambda name, current, total:
                            self.progress.emit(
                                name,
                                current,
                                total
                            )
                    )

                    total_saved += count

                    self.log_message.emit(
                        f"카테고리 완료: {category['name']} "
                        f"({count}개 확인)"
                    )

                except Exception as error:

                    failed_categories += 1

                    database.add_error(
                        None,
                        "category_error",
                        f"{category['name']} : {error}"
                    )

                    self.log_message.emit(
                        f"카테고리 오류: {category['name']} / {error}"
                    )

                database.commit()

            database.cleanup_old_errors()
            database.commit()

            self.completed.emit(
                total_saved,
                failed_categories
            )

        except Exception as error:

            self.failed.emit(str(error))

        finally:

            if crawler:
                crawler.close()

            if database:
                database.close()
