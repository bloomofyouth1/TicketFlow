import logging
import sys


def setup_logging():
    logger = logging.getLogger("ticketflow")

    logger.setLevel(logging.INFO)

    # 避免重复添加日志处理器
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)

        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)s | "
            "%(name)s | %(message)s"
        )

        handler.setFormatter(formatter)
        logger.addHandler(handler)

    # 防止日志继续传递给根 logger，造成重复输出
    logger.propagate = False
