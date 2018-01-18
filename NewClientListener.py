import socket
import logging
import threading
from Event import *
from utils import *
import utils

logger = logging.getLogger(__name__)


class NewClientListener:
    def __init__(self, event_queue, port=0):
        self.socket = self.create_new_socket(port)
        self.event_queue = event_queue
        self.running = True
        self.thread = None

    def create_new_socket(self, port):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((utils.get_my_ip_address(), port))
        sock.listen()
        return sock

    def listen_to_clients(self):
        logger.info('Start listening to new clients on port {}'.format(self.socket.getsockname()[1]))
        while self.running:
            try:
                connection, addr = self.socket.accept()
                logger.info('New Client: {}:{}'.format(addr[0], addr[1]))
                self.event_queue.put(InnerNewClientRequestEvent(connection, addr))
            except OSError as e:
                if self.running:
                    logger.error('New Client Listener failed to accept, {}'.format(type(e)))
                else:
                    pass

    def run(self):
        self.thread = threading.Thread(target=self.listen_to_clients, args=())
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        logger.info('Stop listening to new clients')
        self.socket.close()
        self.running = False
        self.thread.join()
