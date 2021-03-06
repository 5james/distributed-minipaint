import socket
import logging
import threading
from Event import *
import utils
import json

logger = logging.getLogger(__name__)


class PreviousHopListener:
    def __init__(self, main_queue, connection, previous_hop_address):
        self.main_queue = main_queue
        self.conn = connection
        self.previous_hop_address = previous_hop_address
        self.running = True
        self.thread = None

    def listen_to_clients(self):
        global message
        logger.info('P. Start thread to listening messages from {}:{}'.format(self.previous_hop_address[0],
                                                                          self.previous_hop_address[1]))
        while self.running:
            try:
                message_size = b''
                while len(message_size) < 8:
                    packet = self.conn.recv(8 - len(message_size))
                    if not packet:
                        return None
                    message_size += packet

                message_size = int.from_bytes(message_size, byteorder='big')
                message = b''
                while len(message) < message_size:
                    packet = self.conn.recv(message_size - len(message))
                    if not packet:
                        return None
                    message += packet
                parsed_message = json.loads(message.decode('utf-8'))
                self.handle_message(parsed_message)
            except Exception as ex:
                if message == b'':
                    # Check if connection ended cleanly
                    return
                else:
                    # Else try to parse and pass message
                    try:
                        message = json.loads(message.decode('utf-8'))
                        self.handle_message(message)
                    except Exception:
                        pass
                logger.error(ex)
                self.running = False
                # self.stop()
        logger.info('Stop thread to listening messages from previous hop')
        self.conn.close()

    def handle_message(self, parsed_message):
        message_type = EventType(parsed_message['type'])
        data = parsed_message['data']
        if message_type == EventType.DRAWING_INFORMATION:
            self.main_queue.put(
                DrawingInformationEvent(data['client_uuid'], data['timestamp'], data['points'],
                                        data['color'])
            )
        elif message_type == EventType.TOKEN_PASS:
            self.main_queue.put(TokenPassEvent(data['token']))
        elif message_type == EventType.SET_NEW_NEXT_NEXT_HOP:
            self.main_queue.put(NewNextNextHop(data['new_address'], data['destination_next_hop']))
        elif message_type == EventType.ENTERED_CRITICAL_SECTION:
            self.main_queue.put(EnteredCriticalSectionEvent(data['timestamp'], data['client_uuid']))
        elif message_type == EventType.LEAVING_CRITICAL_SECTION:
            self.main_queue.put(LeavingCriticalSectionEvent(data['timestamp'], data['client_uuid']))
        elif message_type == EventType.TOKEN_RECEIVED_QUESTION:
            self.main_queue.put(TokenReceivedQuestionEvent(data['token']))
        elif message_type == EventType.CONTROL_PACKAGE:
            self.main_queue.put(ControlPackageEvent(data['uuid']))
        else:
            logger.error(parsed_message)
            raise Exception("Not implemented yet")

    def run(self):
        self.thread = threading.Thread(target=self.listen_to_clients, args=())
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        logger.info('Stop thread to listening messages from previous hop')
        self.running = False
        self.conn.close()
        self.thread.join()
