import threading
import logging
from Event import InnerControlPackage
import time

logger = logging.getLogger(__name__)

class ControlPackageSender:
    def __init__(self, main_queue, uuid):
        self.main_queue = main_queue
        self.uuid = uuid

        self.running = True
        self.thread = None

    def control_package_sender_main(self):
        logger.info('Start Control Package sender thread.')
        while True:
            if self.main_queue.empty():
                self.main_queue.put(InnerControlPackage())
                time.sleep(0.05)

    def run(self):
        self.thread = threading.Thread(target=self.control_package_sender_main, args=())
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        logger.info('Stop Control Package sender thread')
        self.running = False
        self.thread.join()
