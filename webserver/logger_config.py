# logger_setup.py

import logging
import logging.handlers
import os
import sys  # Import sys to use sys.stdout

def init_logger(console_level=logging.INFO,
                  file_level=logging.DEBUG,
                  log_file='logs/app.log',
                  max_bytes=0.5*1024*1024,  # 0.5 MB
                  backup_count=5):
    """
    Set up logging configuration.

    :param console_level: Logging level for console output.
    :param file_level: Logging level for file output.
    :param log_file: Path to the log file.
    :param max_bytes: Maximum size of log file before rotation.
    :param backup_count: Number of backup files to keep.
    """
    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)  # Set root logger to lowest level

    # Remove existing handlers, if any
    if logger.hasHandlers():
        logger.handlers.clear()

    # Create console handler with UTF-8 encoding
    console_handler = logging.StreamHandler(sys.stdout)  # Use sys.stdout
    console_handler.setLevel(console_level)

    # Create file handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count, encoding='utf-8')  # Ensure UTF-8 encoding
    file_handler.setLevel(file_level)

    # Create formatter and add it to the handlers
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Add handlers to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
