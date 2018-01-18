import ntplib
import threading
import logging
import time

SECONDS_TO_REFRESH_TIMER = 5.0
NTP_timer: threading.Timer = None
__NtpClient = ntplib.NTPClient()
time_offset = [0]


def set_offset():
    # logging.info('NTP timer tick.')
    global NTP_timer
    NTP_timer = threading.Timer(SECONDS_TO_REFRESH_TIMER, set_offset)
    NTP_timer.start()
    try:
        timer = __NtpClient.request('europe.pool.ntp.org', version=3)
        time_offset[0] = timer.offset
    except Exception:
        pass


def end_timer():
    global NTP_timer
    NTP_timer.cancel()
    logging.info('NTP timer ended.')


def get_timestamp():
    return int(time.time()) + time_offset[0]
