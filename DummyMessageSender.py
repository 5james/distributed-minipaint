import threading
import logging
from Event import DummyMessageEvent
import time

logger = logging.getLogger(__name__)


# Because we are relying on a TCP connection information when detecting we detect  failed connections
# we have to put dummy events to send so we can detect the fails all the time even if the data is not flowing
# through the network. This is the thread responsible for putting this dummy event if the queue is empty.


class DummyMessageSender:
    def __init__(self, main_queue, uuid):
        self.main_queue = main_queue
        self.uuid = uuid

        self.running = True
        self.thread = None

    def dummy_message_sender_main(self):
        logger.info('Start Dummy Message sender thread.')
        while True:
            if self.main_queue.empty():
                self.main_queue.put(DummyMessageEvent(self.uuid))
                # logger.info('Dummy Message put in queue.')
                time.sleep(0.05)

    def run(self):
        self.thread = threading.Thread(target=self.dummy_message_sender_main, args=())
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        logger.info('Stop Dummy Message sender thread')
        self.running = False
        self.thread.join()
