import sys
import sqlite3
from pathlib import Path

from PySide6.QtCore import QCoreApplication

from workers import CrawlerWorker


# ==========================================
# 경로 설정
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

DATABASE_DIR = BASE_DIR / "database"
DATABASE_PATH = DATABASE_DIR / "products.db"

CONFIG_DIR = BASE_DIR / "config"
IMAGE_DIR = BASE_DIR / "assets" / "images"


# ==========================================
# 폴더 초기화
# ==========================================

def initialize_directories():
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)


# ==========================================
# 데이터베이스 확인
# ==========================================

def check_database():

    if not DATABASE_PATH.exists():
        raise FileNotFoundError(
            f"데이터베이스 파일을 찾을 수 없습니다.\n{DATABASE_PATH}"
        )

    connection = sqlite3.connect(DATABASE_PATH)

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT name
            FROM sqlite_master
            WHERE type='table'
        """)

        tables = [row[0] for row in cursor.fetchall()]

        required_tables = [
            "products",
            "categories",
            "product_categories",
            "crawl_errors",
            "settings"
        ]

        for table in required_tables:
            if table not in tables:
                raise RuntimeError(
                    f"데이터베이스에 {table} 테이블이 없습니다."
                )

        cursor.execute("SELECT COUNT(*) FROM products")
        product_count = cursor.fetchone()[0]

        print("데이터베이스 연결 성공")
        print(f"등록된 상품: {product_count:,}개")

        return product_count

    finally:
        connection.close()


# ==========================================
# 프로그램 관리자
# ==========================================

class ApplicationManager:

    def __init__(self, app):

        self.app = app
        self.worker = None

    # --------------------------------------
    # 크롤러 시작
    # --------------------------------------

    def start_crawler(self):

        if self.worker is not None and self.worker.isRunning():
            print("이미 업데이트가 실행 중입니다.")
            return

        print()
        print("상품 업데이트를 시작합니다.")
        print("-" * 50)

        self.worker = CrawlerWorker()

        # 진행 상황
        self.worker.progress.connect(
            self.on_progress
        )

        # 로그
        self.worker.log_message.connect(
            self.on_log
        )

        # 작업 완료
        self.worker.completed.connect(
            self.on_completed
        )

        # 오류
        self.worker.failed.connect(
            self.on_failed
        )

        # 중요:
        # 작업 완료 신호가 아니라
        # QThread 자체가 완전히 종료된 후
        # 프로그램을 종료한다.
        self.worker.finished.connect(
            self.on_worker_finished
        )

        self.worker.start()

    # --------------------------------------
    # 진행 상황 출력
    # --------------------------------------

    def on_progress(self, message, current, total):

        if total > 0:

            percent = current / total * 100

            print(
                f"\r[{percent:6.2f}%] "
                f"{current}/{total} | {message}",
                end="",
                flush=True
            )

        else:
            print(f"\n{message}")

    # --------------------------------------
    # 로그 출력
    # --------------------------------------

    def on_log(self, message):

        print(f"\n{message}")

    # --------------------------------------
    # 크롤링 완료
    # --------------------------------------

    def on_completed(self, success_count, failed_count):

        print()
        print()
        print("=" * 50)
        print("상품 업데이트 완료")
        print("=" * 50)

        print(f"처리 상품: {success_count:,}개")
        print(f"실패 상품: {failed_count:,}개")

        print("=" * 50)

        # 여기서 app.quit()을 호출하지 않는다.
        # QThread.finished 신호에서 종료한다.

    # --------------------------------------
    # 크롤링 오류
    # --------------------------------------

    def on_failed(self, error_message):

        print()
        print("=" * 50)
        print("크롤러 실행 실패")
        print("=" * 50)

        print(error_message)

        # 스레드 종료를 기다린다.
        # 프로그램 종료는 on_worker_finished에서 처리한다.

    # --------------------------------------
    # 스레드 완전 종료
    # --------------------------------------

    def on_worker_finished(self):

        print()
        print("크롤러 스레드 종료 확인")
        print("프로그램을 종료합니다.")

        self.app.quit()


# ==========================================
# 프로그램 실행
# ==========================================

def main():

    print("=" * 50)
    print("미니카 상품 관리 프로그램")
    print("=" * 50)

    try:

        # 폴더 준비
        initialize_directories()

        # DB 확인
        check_database()

        # Qt 이벤트 루프
        app = QCoreApplication(sys.argv)

        # 프로그램 관리자
        manager = ApplicationManager(app)

        # 크롤러 시작
        manager.start_crawler()

        # 이벤트 루프 실행
        exit_code = app.exec()

        # 스레드가 아직 실행 중이라면 종료 대기
        if manager.worker is not None:
            if manager.worker.isRunning():
                manager.worker.wait()

        return exit_code

    except Exception as error:

        print()
        print("=" * 50)
        print("프로그램 실행 오류")
        print("=" * 50)
        print(error)

        return 1


# ==========================================
# 진입점
# ==========================================

if __name__ == "__main__":
    sys.exit(main())
