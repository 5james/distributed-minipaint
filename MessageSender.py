import socket
import logging
import threading
from Event import *
import utils

logger = logging.getLogger(__name__)

class MessageSender:
    def __init__(self, main_queue, message_queue, connection, address):
        self.main_queue = main_queue
        self.message_queue = message_queue
        self.conn = connection
        self.addr = address
        self.running = True
        self.thread = None

    def message_sender_main(self):
        logger.info('M. Start thread to sending messages to {}:{}'.format(self.addr[0], self.addr[1]))
        while self.running:
            (e) = self.message_queue.get()
            try:
                message = utils.event_to_message(e)
                message_size = (len(message)).to_bytes(8, byteorder='big')
                self.conn.send(message_size)
                self.conn.send(message)
            except OSError as e:
                if self.running:
                    logger.error('Failed on sending message to next hop')
                    self.main_queue.put(InnerNextHopBroken())
                    return
                else:
                    pass

    def run(self):
        self.thread = threading.Thread(target=self.message_sender_main, args=())
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        logger.info('Stop thread to sending messages to next_hop')
        self.running = False
        self.conn.close()
        self.thread.join()
