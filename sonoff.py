import logging
from logging.handlers import RotatingFileHandler
import time
from sonoff import Sonoff
from telegram import Bot
import os

class DeviceMonitor:
    def __init__(self):
        username = os.getenv('USERNAME')
        password = os.getenv('PASSWORD')
        api_region = os.getenv('API_REGION')
        device_id = os.getenv('DEVICE_ID')
        telegram_token = os.getenv('TELEGRAM_TOKEN')
        chat_id = os.getenv('CHAT_ID')
        log_file = os.getenv('LOG_FILE', 'device_monitor.log')

        self.sonoff = Sonoff(username, password, api_region)
        self.device_id = device_id
        self.telegram_bot = Bot(token=telegram_token)
        self.chat_id = chat_id
        self.last_status = None  # Variable to store the last known status of the device
        self.logger = self.setup_logger(log_file)

    def setup_logger(self, log_file):
        logger = logging.getLogger('DeviceMonitor')
        logger.setLevel(logging.INFO)
        handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def send_telegram_message(self, message):
        self.telegram_bot.send_message(chat_id=self.chat_id, text=message)
        self.logger.info(f"Telegram message sent: {message}")

    def get_device_status(self):
        try:
            device = self.sonoff.get_device(self.device_id)
            if device and 'online' in device:
                return device if device['online'] else 'offline'
        except Exception as e:
            self.logger.error(f"Error getting device status: {e}")
        return 'error'

    def control_device(self, channel_number, action):
        status = self.get_device_status()
        if status != self.last_status:
            self.handle_status_change(status)
            self.last_status = status  # Update the last known status

        if status in ['offline', 'error']:
            return False

        channel_status = status['params']['switches'][channel_number - 1]['switch']
        if channel_status == action:
            self.logger.info(f"Channel {channel_number} is already {action}.")
        else:
            self.logger.info(f"Turning channel {channel_number} {action}.")
            self.sonoff.switch(self.device_id, action, channel_number)
        return True

    def handle_status_change(self, status):
        if status == 'offline':
            message = "The device is offline. Possible power outage detected."
        elif status == 'error':
            message = "Error communicating with the device."
        else:
            message = "The device is back online."
        self.logger.warning(message)
        self.send_telegram_message(message)

    def monitor_and_control_device(self, channel_number=2, check_interval=20):
        while True:
            self.logger.info(f"Checking device status for channel {channel_number}.")
            if not self.control_device(channel_number, 'on'):
                time.sleep(60)  # Wait a minute before retrying
                continue

            time.sleep(check_interval * 60)  # Wait for the specified interval

            if not self.control_device(channel_number, 'off'):
                time.sleep(60)  # Wait a minute before retrying
                continue

# Usage
device_monitor = DeviceMonitor()
device_monitor.monitor_and_control_device()
