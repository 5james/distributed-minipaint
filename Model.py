from gui import PAINT_HEIGHT, PAINT_WIDTH
import queue
from NewClientListener import *
from NewPreviousHopListener import *
from MessageSender import *
from PreviousHopListener import *
import uuid
import NTP_timer
from ControlPackageSender import *

logger = logging.getLogger(__name__)

_SECONDS_IN_CRITICAL_SECTION = 5.0


class Model:
    def __init__(self, main_queue, paint_queue, new_client_listener: NewClientListener,
                 new_previous_hop_listener: NewPreviousHopListener):
        self.running = True
        self.thread = None

        self.main_queue = main_queue
        self.painting_queue = paint_queue
        # self.time_offset = time_offset

        self.sending_queue = None
        self.message_sender = None

        self.new_clients_listener = new_client_listener
        self.new_previous_hop_listener = new_previous_hop_listener

        self.previous_hop_listener = None

        self.next_hop_info = None
        self.next_next_hop_info = None
        self.previous_hop = None

        self.critical_section = None
        self.want_to_enter_critical_section = False

        self.last_token = 0
        # Unique uuid identifying clients in the network
        self.uuid = uuid.uuid4().hex

        # Initial board state
        self.board_state = [[0 for _ in range(PAINT_HEIGHT)] for _ in range(PAINT_WIDTH)]

    def run(self):
        self.thread = threading.Thread(target=self.model_main, args=())
        self.thread.daemon = True
        self.thread.start()

    def stop(self):
        logger.info('Stop model processing')
        # if self.previous_hop_listener:
        #     self.previous_hop_listener.stop()
        # if self.message_sender:
        #     self.message_sender.stop()
        self.running = False
        self.main_queue.put(InnerCloseMainQueue)
        self.thread.join()

    def model_main(self):
        logger.info('Start model processing')
        while self.running:
            (e) = self.main_queue.get()
            # print(e)
            if isinstance(e, InnerNewConnectionEvent):
                self.new_connection_to_node(e)
            elif isinstance(e, InnerNewClientRequestEvent):
                self.handle_new_client_request(e)
            elif isinstance(e, InnerNewPreviousHopRequestEvent):
                self.handle_new_previous_hop_request(e)
            elif isinstance(e, InnerDrawingInformationEvent):
                self.handle_inner_drawing_event(e)
            elif isinstance(e, DrawingInformationEvent):
                self.handle_drawing_event(e)
            elif isinstance(e, TokenPassEvent):
                self.handle_token_pass(e)
            elif isinstance(e, TokenReceivedQuestionEvent):
                self.handle_token_receiver_question(e)
            elif isinstance(e, EnteredCriticalSectionEvent):
                self.handle_entering_critical_section(e)
            elif isinstance(e, InnerLeavingCriticalSection):
                self.handle_inner_leave_critical_section(e)
            elif isinstance(e, LeavingCriticalSectionEvent):
                self.handle_leave_critical_section(e)
            elif isinstance(e, NewNextNextHop):
                self.handle_new_next_next_hop(e)
            elif isinstance(e, ControlPackageEvent):
                self.handle_control_package_event(e)
            elif isinstance(e, InnerNextHopBroken):
                self.handle_inner_next_hop_broken(e)
            elif isinstance(e, InnerControlPackage):
                self.handle_innder_control_package(e)
            elif isinstance(e, InnerWantToEnterCriticalSection):
                self.handle_inner_want_to_enter_critical_section(e)

    def new_connection_to_node(self, event: InnerNewConnectionEvent):
        self.clean_old_state()

        address = event.data['address']
        ip, port = address.split(':')

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        logger.info('Connecting to node: {}:{}'.format(ip, port))
        try:
            sock.settimeout(1)
            sock.connect((ip, int(port)))

            # We send the client request containing our data so anothe rclient could connect as a previous_hop
            new_client_request = NewClientRequestEvent(
                (self.new_previous_hop_listener.socket.getsockname()[0],
                 self.new_previous_hop_listener.socket.getsockname()[1]))
            message = utils.event_to_message(new_client_request)
            message_size = (len(message)).to_bytes(8, byteorder='big')
            sock.sendall(message_size)
            sock.sendall(message)

            message_size = sock.recv(8)
            message_size = int.from_bytes(message_size, byteorder='big')

            data = b''
            while len(data) < message_size:
                packet = sock.recv(message_size - len(data))
                if not packet:
                    return None
                data += packet

            init_data = (json.loads(data.decode('utf-8')))['data']

            self.next_hop_info = init_data['next_hop']
            logger.info('New next hop: {}'.format(self.next_hop_info))

            # Check if we are connecting to group founder (only 1 node in ring)
            if not init_data['next_next_hop']:
                # If so next next hop is this node
                self.next_next_hop_info = (self.new_previous_hop_listener.socket.getsockname()[0],
                                           self.new_previous_hop_listener.socket.getsockname()[1])
            else:
                self.next_next_hop_info = init_data['next_next_hop']
            logger.info('New next next hop: {}'.format(self.next_next_hop_info))

            ip, port = init_data['next_hop']
            sock2 = socket.create_connection((ip, int(port)))
            self.sending_queue = queue.Queue()
            self.message_sender = MessageSender(self.main_queue, self.sending_queue, sock2, (ip, port))
            self.message_sender.run()
            self.initialize_board(init_data['board_state'])
            self.initialize_critical_section(init_data['critical_section_state'])
            sock.shutdown(socket.SHUT_WR)
            sock.close()
        except (TimeoutError, ConnectionError, ConnectionRefusedError, ConnectionAbortedError,
                ConnectionResetError, socket.timeout, socket.gaierror) as e:
            logger.error('Error during connecting to socket')
            print(type(e))
            if self.painting_queue:
                self.painting_queue.put(PaintConnectionFail())
                return
        except Exception:
            logger.error('Error during connecting')
            sock.shutdown(socket.SHUT_WR)
            sock.close()
            return

        self.control_package_sender = ControlPackageSender(self.main_queue, self.uuid)
        self.control_package_sender.run()

    def initialize_board(self, board_state):
        for counter in range(len(board_state)):
            x, y = board_state[counter]
            self.painting_queue.put(PaintDrawing([(x, y)], 1))
            try:
                self.board_state[x][y] = 1
            except IndexError:
                return

    def initialize_critical_section(self, critical_section):
        if critical_section:
            self.critical_section = critical_section
            self.painting_queue.put(PaintBoardClosed())

    def handle_new_client_request(self, event: InnerNewClientRequestEvent):
        # Firstly, we make sure, that the client sends us his address
        message_size = event.data['connection'].recv(8)
        message_size = int.from_bytes(message_size, byteorder='big')
        message = b''
        while len(message) < message_size:
            packet = event.data['connection'].recv(message_size - len(message))
            if not packet:
                return None
            message += packet
        try:
            client_address = json.loads(message.decode('utf-8'))['data']['address']
        except (json.decoder.JSONDecodeError, KeyError):
            return

        bCreateToken = not self.next_hop_info

        # Start create init_data for client
        # 1. next hop
        if self.next_hop_info:
            next_hop = self.next_hop_info
        else:
            next_hop = (self.new_previous_hop_listener.socket.getsockname()[0],
                        self.new_previous_hop_listener.socket.getsockname()[1])
        # 2. Get list of drawn_pixels
        drawn_pixels = [(x, y) for x in range(len(self.board_state)) for y in range(len(self.board_state[x])) if
                        self.board_state[x][y] == 1]

        response = NewClientResponseEvent(next_hop,
                                          # self.new_previous_hop_listener.socket.getsockname()[1],
                                          self.next_next_hop_info,
                                          drawn_pixels,
                                          self.critical_section
                                          )
        message = utils.event_to_message(response)
        message_size = (len(message)).to_bytes(8, byteorder='big')
        event.data['connection'].send(message_size)
        event.data['connection'].send(message)

        # Wait until the socket is closed, so we know that client node has initialized itself
        try:
            message = event.data['connection'].recv(8)
        except Exception as ex:
            if message == b'':
                # Socket closed successfully
                pass
            else:
                logger.error(ex)
                # Client did not initialize correctly so we abort the process
                return

        # After successfully initialized client we can connect to the previous hop listener
        ip, port = client_address
        # We connect to the new client previous hop listener
        try:
            connection = socket.create_connection((ip, port), 100)
        except (TimeoutError, ConnectionError, ConnectionRefusedError, ConnectionAbortedError,
                ConnectionResetError, socket.timeout):
            # If we cannot connect, then we abort handling this request
            logger.error('Error during connecting to new client')
            return

        # After all connections are established we are sure, that we can start changing our model for new client
        # Update Next Next Hop
        if self.next_hop_info:
            # If we have next hop, make him next next hop, ...
            self.next_next_hop_info = self.next_hop_info
            logger.info('New next next hop: {}'.format(self.next_next_hop_info))
        else:
            # ... if not then we are group founder and next next hop is us
            self.next_next_hop_info = (
                self.new_previous_hop_listener.socket.getsockname()[0],
                self.new_previous_hop_listener.socket.getsockname()[1])
            logger.info('New next next hop: {}'.format(self.next_next_hop_info))

        # After this we can update our next hop as new client
        self.next_hop_info = client_address
        logger.info('New next hop: {}'.format(self.next_hop_info))

        # if self.message_sender:
        #     self.message_sender.stop()

        # create message sender and create token if necessary
        self.sending_queue = queue.Queue()
        self.message_sender = MessageSender(self.main_queue, self.sending_queue, connection, (ip, port))
        self.message_sender.run()
        if bCreateToken and self.last_token is not None:
            self.sending_queue.put(TokenPassEvent(self.last_token))

    def handle_new_previous_hop_request(self, event: InnerNewPreviousHopRequestEvent):
        self.previous_hop = event.data['address']
        logger.info('previous hop: {}'.format(self.previous_hop))

        connection = event.data['connection']
        if self.previous_hop_listener:
            self.previous_hop_listener.stop()
        self.previous_hop_listener = PreviousHopListener(self.main_queue, connection, self.previous_hop)
        self.previous_hop_listener.run()

        my_addr = (
            self.new_previous_hop_listener.socket.getsockname()[0],
            self.new_previous_hop_listener.socket.getsockname()[1])

        # Now we have to make everyone update their next next hop
        if self.previous_hop[0] == self.next_hop_info[0]:
            # New ring - only us and new client
            self.sending_queue.put(NewNextNextHop(self.previous_hop, my_addr))
            self.next_next_hop_info = my_addr
            logger.info('New next next hop: {}'.format(self.next_next_hop_info))
        else:
            # This node is next next hop for the node who has its next hop set as our previous hop
            self.sending_queue.put(NewNextNextHop(my_addr, self.previous_hop))
            # Our next hop is next next hop for the node who has its next hop set as this node
            self.sending_queue.put(NewNextNextHop(self.next_hop_info, my_addr))

    def handle_inner_drawing_event(self, event: InnerDrawingInformationEvent):
        if not self.critical_section:
            self.draw_pixels(event.data['points'], event.data['color'])
            if self.sending_queue:
                self.sending_queue.put(
                    DrawingInformationEvent(self.uuid, NTP_timer.get_timestamp(), event.data['points'],
                                            event.data['color']))
        elif self.critical_section['timestamp'] > event.data['timestamp']:
            self.draw_pixels(event.data['points'], event.data['color'])
            if self.sending_queue:
                self.sending_queue.put(
                    DrawingInformationEvent(self.uuid, NTP_timer.get_timestamp(), event.data['points'],
                                            event.data['color']))
        elif self.critical_section['client_uuid'] == self.uuid:
            self.draw_pixels(event.data['points'], event.data['color'])
            if self.sending_queue:
                self.sending_queue.put(
                    DrawingInformationEvent(self.uuid, NTP_timer.get_timestamp(), event.data['points'],
                                            event.data['color']))

    def draw_pixels(self, points, color):
        try:
            for point in points:
                x, y = point
                self.board_state[x][y] = color
        except IndexError as e:
            self.painting_queue.put(PaintBadBoardSize())
            return
        self.painting_queue.put(PaintDrawing(points, color))

    def handle_drawing_event(self, event: DrawingInformationEvent):
        if event.data['client_uuid'] == self.uuid:
            return
        if not self.critical_section:
            self.draw_pixels(event.data['points'], event.data['color'])
            if self.sending_queue:
                self.sending_queue.put(event)
        elif self.critical_section['timestamp'] > event.data['timestamp']:
            self.draw_pixels(event.data['points'], event.data['color'])
            if self.sending_queue:
                self.sending_queue.put(event)
        elif self.critical_section['client_uuid'] == event.data['client_uuid']:
            self.draw_pixels(event.data['points'], event.data['color'])
            if self.sending_queue:
                self.sending_queue.put(event)

    def clean_old_state(self):
        self.next_hop_info = None
        logger.info('New next hop: {}'.format(self.next_hop_info))
        self.next_next_hop_info = None
        logger.info('New next next hop: {}'.format(self.next_next_hop_info))
        self.previous_hop = None
        logger.info('previous hop: {}'.format(self.previous_hop))
        self.critical_section = None
        self.board_state = [[0 for _ in range(PAINT_WIDTH)] for _ in range(PAINT_HEIGHT)]
        self.sending_queue = None
        if self.message_sender:
            self.message_sender.stop()
        if self.previous_hop_listener:
            self.previous_hop_listener.stop()
        self.last_token = 0
        self.painting_queue.put(PaintBoardOpen())

    def handle_token_pass(self, event: TokenPassEvent):
        # Firstly, increment last_token
        self.last_token = event.data['token'] + 1

        # Secondly, check if critical section was released
        if self.critical_section:
            self.critical_section = None
            self.painting_queue.put(PaintBoardOpen())

        # Thirdly, check if we want to enter critical section
        if self.want_to_enter_critical_section:
            # If yes, then hold token and send info about new board owner
            self.want_to_enter_critical_section = False
            timestamp = NTP_timer.get_timestamp()
            self.critical_section = {
                'timestamp': timestamp,
                'client_uuid': self.uuid
            }
            threading.Timer(_SECONDS_IN_CRITICAL_SECTION,
                            lambda: self.main_queue.put(InnerLeavingCriticalSection())).start()
            self.painting_queue.put(PaintBoardPossessed())
            self.sending_queue.put(EnteredCriticalSectionEvent(timestamp, self.uuid))
        else:
            # If not, then simply pass token
            if self.sending_queue:
                self.sending_queue.put(TokenPassEvent(self.last_token))

    def handle_token_receiver_question(self, event: TokenReceivedQuestionEvent):
        # Check if our last known token is greater than token in the query (token from previous previous hop) + 1.
        try:
            token_event = event.data['token']
        except (json.decoder.JSONDecodeError, KeyError):
            return
        if self.last_token > token_event + 1:
            # If yes, then broken node exited the critical section and we do not have to create new token
            return
        else:
            # If not, then create new token and pass it (and exit critical section)
            token = token_event + 1
            self.sending_queue.put(TokenPassEvent(token))
            self.critical_section = None
            self.painting_queue.put(PaintBoardOpen())

    def handle_entering_critical_section(self, event: EnteredCriticalSectionEvent):
        client_uuid = event.data['client_uuid']
        timestamp = event.data['timestamp']
        if client_uuid == self.uuid:
            return
        self.critical_section = {
            'timestamp': timestamp,
            'client_uuid': client_uuid
        }
        self.painting_queue.put(PaintBoardClosed())
        self.sending_queue.put(event)

    def handle_inner_leave_critical_section(self, event: InnerLeavingCriticalSection):
        self.critical_section = None
        self.painting_queue.put(PaintBoardOpen())
        if self.sending_queue:
            self.sending_queue.put(LeavingCriticalSectionEvent(NTP_timer.get_timestamp(), self.uuid))
            self.sending_queue.put(TokenPassEvent(self.last_token))
        else:
            self.main_queue.put(LeavingCriticalSectionEvent(NTP_timer.get_timestamp(), self.uuid))
            self.main_queue.put(TokenPassEvent(self.last_token))

    def handle_leave_critical_section(self, event: LeavingCriticalSectionEvent):
        client_uuid = event.data['client_uuid']

        if client_uuid == self.uuid:
            # Message was received by everyone in the ring
            return

        if self.critical_section and self.critical_section['client_uuid'] == client_uuid:
            self.painting_queue.put(PaintBoardOpen())
            self.critical_section = None

        self.sending_queue.put(event)

    def handle_new_next_next_hop(self, event: NewNextNextHop):
        destination_next_hop_ip, destination_next_hop_port = event.data['destination_next_hop']

        # Check if destination_next_hop ip address is our next hop ip address
        if destination_next_hop_ip == self.next_hop_info[0]:
            # If yes, then we are receiver of this message
            self.next_next_hop_info = event.data['new_address']
            logger.info('New next next hop: {}'.format(self.next_next_hop_info))
        else:
            self.sending_queue.put(event)

    def handle_control_package_event(self, event: ControlPackageEvent):
        if self.uuid != event.data['uuid']:
            return

    def handle_inner_next_hop_broken(self, event: InnerNextHopBroken):
        next_next_hop_ip, next_next_hop_port = self.next_next_hop_info
        if next_next_hop_ip == utils.get_my_ip_address():
            # If we are the only client left - clean old state
            self.clean_old_state()
            return

        # Firstly, try to reconnect to next_hop
        next_hop_ip, next_hop_port = self.next_hop_info
        try:
            next_hop_sock = socket.create_connection((next_hop_ip, next_hop_port))
            self.sending_queue = queue.Queue()
            self.message_sender = MessageSender(self.main_queue, self.sending_queue, next_hop_sock,
                                                (next_hop_sock.getsockname()[0], next_hop_sock.getsockname()[1]))
            self.message_sender.run()
        except ConnectionRefusedError as e:
            logger.error("Couldn't connect to next_hop: ", e)
            next_next_hop_ip, next_next_hop_port = self.next_next_hop_info
            try:
                next_next_hop_sock = socket.create_connection((next_next_hop_ip, next_next_hop_port))
                self.sending_queue = queue.Queue()
                self.message_sender = MessageSender(self.main_queue, self.sending_queue, next_next_hop_sock,
                                                    (next_next_hop_sock.getsockname()[0],
                                                     next_next_hop_sock.getsockname()[1]))
                self.message_sender.run()
                self.next_hop_info = self.next_next_hop_info
                logger.info('New next hop: {}'.format(self.next_hop_info))
                self.sending_queue.put(TokenReceivedQuestionEvent(self.last_token))
            except Exception as e:
                logger.error(e)

    def handle_inner_want_to_enter_critical_section(self, event: InnerWantToEnterCriticalSection):
        self.want_to_enter_critical_section = True

    def handle_innder_control_package(self, event: InnerControlPackage):
        if self.sending_queue:
            self.sending_queue.put(ControlPackageEvent(self.uuid))
