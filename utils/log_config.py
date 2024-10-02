import logging
from datetime import datetime
import os
from colorama import Fore, Style, init
from dotenv import load_dotenv

init(autoreset=True)
load_dotenv()

class ColorFormatter(logging.Formatter):
    COLORS = {
        logging.DEBUG: Fore.CYAN + Style.BRIGHT,
        logging.INFO: Fore.GREEN + Style.BRIGHT,
        logging.WARNING: Fore.YELLOW + Style.BRIGHT,
        logging.ERROR: Fore.RED + Style.BRIGHT,
        logging.CRITICAL: Fore.RED + Style.BRIGHT + Style.BRIGHT
    }

    def format(self, record):
        log_fmt = f"%(asctime)s: {self.COLORS.get(record.levelno, '')}%(levelname)s{Style.RESET_ALL}: %(message)s"
        formatter = logging.Formatter(log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)

def logging_config():
    level = logging.INFO
    log_dir = os.getenv('LOG_DIR')
    now = datetime.now()
    date_time = now.strftime("%Y-%d-%m")
    log_file = f"{log_dir}/{date_time}_log.log"

    file_formatter = logging.Formatter('%(asctime)s:%(levelname)s:%(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    
    logger = logging.getLogger('main_log')
    logger.setLevel(level)
    
    if not logger.handlers:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(ColorFormatter())
        logger.addHandler(console_handler)
    
    return logger
