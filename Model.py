from gui import PAINT_HEIGHT, PAINT_WIDTH
import queue
from NewClientListener import *
from NewPredecessorListener import *
from MessageSender import *
from PredecessorListener import *
import uuid
import NTP_timer
from DummyMessageSender import *
from criticalsectionleaver import *

logger = logging.getLogger(__name__)


class Model:
    def __init__(self, main_queue, paint_queue, new_client_listener: NewClientListener,
                 new_predecessor_listener: NewPredecessorListener):
        self.running = True
        self.thread = None

        self.main_queue = main_queue
        self.paint_queue = paint_queue
        # self.time_offset = time_offset

        self.sending_queue = None
        self.message_sender = None

        self.new_clients_listener = new_client_listener
        self.new_predecessors_listener = new_predecessor_listener

        self.predecessor_listener = None

        self.next_hop_info = None
        logger.info('New next hop0: {}'.format(self.next_hop_info))
        self.next_next_hop_info = None
        logger.info('New next next hop7: {}'.format(self.next_next_hop_info))
        self.predecessor = None
        logger.info('Predecessor3: {}'.format(self.predecessor))

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
        self.running = False
        self.main_queue.put(InnerCloseMainQueue)
        self.thread.join()

    def model_main(self):
        logger.info('Start model processing')
        while self.running:
            (e) = self.main_queue.get()
            # Handling inner events
            if isinstance(e, InnerNewConnectionEvent):
                self.new_connection_to_node(e)
            elif isinstance(e, InnerNewClientRequestEvent):
                self.handle_new_client_request(e)
            elif isinstance(e, InnerNewPredecessorRequestEvent):
                self.handle_new_predecessor_request(e)
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
            elif isinstance(e, DummyMessageEvent):
                self.handle_dummy_message_event(e)
            elif isinstance(e, InnerNextHopBroken):
                self.handle_inner_next_hop_broken(e)
            elif isinstance(e, InnerWantToEnterCriticalSection):
                self.handle_inner_want_to_enter_critical_section(e)

    def new_connection_to_node(self, event: InnerNewConnectionEvent):
        self.clean_old_state()

        address = event.data['address']
        ip, port = address.split(':')

        # Create new socket to connect to
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        logger.info('Connecting to node: {}:{}'.format(ip, port))
        try:
            sock.connect((ip, int(port)))

            # We send the client request containing our data so anothe rclient could connect as a predecessor
            new_client_request = NewClientRequestEvent(
                (self.new_predecessors_listener.socket.getsockname()[0],
                 self.new_predecessors_listener.socket.getsockname()[1]))
            message = utils.event_to_message(new_client_request, )
            message_size = (len(message)).to_bytes(8, byteorder='big')
            sock.send(message_size)
            sock.send(message)

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
            logger.info('New next hop4: {}'.format(self.next_hop_info))
            if not init_data['next_next_hop']:
                # If there is no next_next_hop init data in the response we are the second client so we set
                # next next hop as our address
                self.next_next_hop_info = (utils.get_my_ip_address(), self.new_predecessors_listener)
                logger.info('New next next hop8: {}'.format(self.next_next_hop_info))
            else:
                # If there are more thant two clients we set the value from the response
                self.next_next_hop_info = init_data['next_next_hop']
                logger.info('New next next hop9: {}'.format(self.next_next_hop_info))

            # We initialize connection to our next hop and we start sending queue
            ip, port = init_data['next_hop']
            sock2 = socket.create_connection((ip, int(port)))
            self.sending_queue = queue.Queue()
            self.message_sender = MessageSender(self.main_queue, self.sending_queue, sock2, (ip, port))
            self.message_sender.run()
            # TODO initialize_board i dummy msg
            self.initialize_board(init_data['board_state'])
            sock.shutdown(1)
            sock.close()

        except Exception as e:
            print('new connection', e)
            sock.shutdown(1)
            sock.close()
            if self.paint_queue:
                self.paint_queue.put(PaintConnectionFail())



        # We start a dummy message sender event which will create dummy messages to detect connection breaks
        self.dummy_message_sender = DummyMessageSender(self.main_queue, self.uuid)
        self.dummy_message_sender.run()

    def initialize_board(self, board_state):
        for counter in range(len(board_state)):
            x, y = board_state[counter]
            self.paint_queue.put(PaintDrawing([(x, y)], 1))
            try:
                self.board_state[x][y] = 1
            except IndexError:
                return

    def handle_new_client_request(self, event: InnerNewClientRequestEvent):
        group_founder = not self.next_hop_info
        # When we detect a new client connecting we want to:
        # 1.Send him the initial data over the connection we already established
        # 2.Connect to him as a predecessor

        # Gather the initial board state (only the coloured spots)
        marked_spots = [(x, y) for x in range(len(self.board_state)) for y in range(len(self.board_state[x])) if
                        self.board_state[x][y]]

        # If we have next hop information we send it, if we do not have we are the first client so we send our
        # information as the first hop information
        if group_founder:
            next_hop = (self.new_predecessors_listener.socket.getsockname()[0],
                        self.new_predecessors_listener.socket.getsockname()[1])
        else:
            next_hop = self.next_hop_info

        # Receive message which contains address of new client's new predecessor listener
        message_size = event.data['connection'].recv(8)
        message_size = int.from_bytes(message_size, byteorder='big')
        message = b''
        while len(message) < message_size:
            packet = event.data['connection'].recv(message_size - len(message))
            if not packet:
                return None
            message += packet
        client_request = json.loads(message.decode('utf-8'))

        # If we are the first client next next hop is None
        response = NewClientResponseEvent(next_hop,
                                          # self.new_predecessors_listener.socket.getsockname()[1],
                                          self.next_next_hop_info,
                                          marked_spots,
                                          )
        message = utils.event_to_message(response)
        message_size = (len(message)).to_bytes(8, byteorder='big')
        event.data['connection'].send(message_size)
        event.data['connection'].send(message)

        try:
            message = event.data['connection'].recv(8)
        except Exception as ex:
            if message == b'':
                # Only case when we have a succesfull read of 0 bytes is when other socket shutdowns normally
                pass
            else:
                logger.error(ex)
                # Client did not initializ correctly so we abort the process
                return

        # If we are not the first client we have to update our next next hop to our previous next hop
        if not group_founder:
            self.next_next_hop_info = self.next_hop_info
            logger.info('New next next hop1: {}'.format(self.next_next_hop_info))
        else:
            # If we are the first client we update our next next hop info to self address
            self.next_next_hop_info = (
                self.new_predecessors_listener.socket.getsockname()[0],
                self.new_predecessors_listener.socket.getsockname()[1])
            logger.info('New next next hop2: {}'.format(self.next_next_hop_info))

        # Then we update our next hop info with the newest client request
        self.next_hop_info = client_request['data']['address']
        logger.info('New next hop5: {}'.format(self.next_hop_info))

        # # We stop current message sender if it exists
        # if self.message_sender:
        #     self.message_sender.stop()

        ip, port = self.next_hop_info
        # We establish a new connection and a new message sender
        connection = socket.create_connection((ip, port), 100)
        self.sending_queue = queue.Queue(maxsize=0)
        self.message_sender = MessageSender(self.main_queue, self.sending_queue, connection, (ip, port))
        self.message_sender.run()
        # TODO TOKEN
        if group_founder and self.last_token != None:
            # If we are the first client we start passing of the token
            self.sending_queue.put(TokenPassEvent(self.last_token))

    def handle_new_predecessor_request(self, event: InnerNewPredecessorRequestEvent):
        # The moment we have a new predecessor this means that the client before our predecessor
        # has a new next next hop address (which is our address) and our predecessor has new next next hop (which is
        # our next hop)

        self.predecessor = event.data['address']
        logger.info('Predecessor1: {}'.format(self.predecessor))
        connection = event.data['connection']
        if self.predecessor_listener:
            self.predecessor_listener.stop()
        self.predecessor_listener = PredecessorListener(self.main_queue, connection, self.predecessor)
        self.predecessor_listener.run()

        self_address = (
            self.new_predecessors_listener.socket.getsockname()[0],
            self.new_predecessors_listener.socket.getsockname()[1])

        # Special case if we have only 2 nodes left
        if self.predecessor[0] == self.next_hop_info[0]:
            self.sending_queue.put(NewNextNextHop(self.predecessor, self_address))
            self.next_next_hop_info = (self.new_predecessors_listener.socket.getsockname()[0],
                                       self.new_predecessors_listener.socket.getsockname()[1])
            logger.info('New next next hop3: {}'.format(self.next_next_hop_info))
        else:
            # We send information to predecessor of our predecessor about his new next next hop address
            self.sending_queue.put(NewNextNextHop(self_address, self.predecessor))
            # We send information to our predecessor about his new next next hop
            self.sending_queue.put(NewNextNextHop(self.next_hop_info, self_address))

    def handle_inner_drawing_event(self, event: InnerDrawingInformationEvent):
        # points = event.data['points']
        # print('INNER')
        # color = event.data['color']
        # self.paint_queue.put(PaintDrawing(points, color))
        # for point in points:
        #     try:
        #         self.board_state[point[0]][point[1]] = color
        #     except IndexError:
        #         return
        # if self.sending_queue:
        #     self.sending_queue.put(
        #         DrawingInformationEvent(self.uuid, NTP_timer.get_timestamp(), points, color))
        def draw_points(event):
            color = event.data['color']
            points = event.data['points']
            try:
                for point in points:
                  x,y = point
                  self.board_state[x][y] = color
            except IndexError as e:
                print('inner drawing', e)
                return

            self.paint_queue.put(PaintDrawing(points, color))
            if (self.sending_queue):
                self.sending_queue.put(
                    DrawingInformationEvent(self.uuid, NTP_timer.get_timestamp(), points, color))

        if not self.critical_section:
            draw_points(event)
        elif self.critical_section['timestamp'] > event.data['timestamp']:
            draw_points(event)
        elif self.critical_section['client_uuid'] == self.uuid:
            draw_points(event)
        elif self.critical_section['client_uuid'] != self.uuid:
            pass

    def handle_drawing_event(self, event: DrawingInformationEvent):
        # data = event.data
        # print('OUTER')
        # if data['client_uuid'] != self.uuid:
        #     points = data['points']
        #     for point in points:
        #         try:
        #             self.board_state[point[0]][point[1]] = data['color']
        #         except IndexError:
        #             pass
        #     self.paint_queue.put(PaintDrawing(points, data['color']))
        #     if self.sending_queue:
        #         self.sending_queue.put(event)
        def draw_point(event):
            points = event.data['points']
            color = event.data['color']
            try:
                for point in points:
                  x,y = point
                  self.board_state[x][y] = color
            except IndexError:
                return

            self.paint_queue.put(PaintDrawing(points, color))
            if self.sending_queue:
                self.sending_queue.put(event)

        if event.data['client_uuid'] == self.uuid:
            return
        if not self.critical_section:
            draw_point(event)
        elif self.critical_section['timestamp'] > event.data['timestamp']:
            draw_point(event)
        elif self.critical_section['client_uuid'] == event.data['client_uuid']:
            draw_point(event)
        elif self.critical_section['client_uuid'] != event.data['client_uuid']:
            pass

    def clean_old_state(self):
        self.next_hop_info = None
        logger.info('New next hop6: {}'.format(self.next_hop_info))
        self.next_next_hop_info = None
        logger.info('New next next hop4: {}'.format(self.next_next_hop_info))
        self.predecessor = None
        logger.info('Predecessor2: {}'.format(self.predecessor))

        self.board_state = [[0 for _ in range(PAINT_WIDTH)] for _ in range(PAINT_HEIGHT)]

    def handle_token_pass(self, event: TokenPassEvent):
        token = event.data['token'] + 1
        self.last_token = token

        if self.critical_section:
            # If we have received the token and the critical section exists we unvalidate critical secion info
            self.critical_section = None
            self.paint_queue.put(PaintBoardOpen())

        if self.want_to_enter_critical_section:
            timestamp = NTP_timer.get_timestamp()
            self.critical_section = {
                'timestamp': timestamp,
                'client_uuid': self.uuid
            }
            # TODO
            leave_critical_section_deamon = CriticalSectionLeaver(self.main_queue)
            leave_critical_section_deamon.start()
            self.want_to_enter_critical_section = False
            self.paint_queue.put(PaintBoardPossessed())
            self.sending_queue.put(EnteredCriticalSectionEvent(timestamp, self.uuid))
        else:
            if self.sending_queue:
                self.sending_queue.put(TokenPassEvent(token))

    def handle_token_receiver_question(self, event: TokenReceivedQuestionEvent):
        # We check weather the last token we received is greater than
        # the token from the request
        # If it is, this means that the disconnected client was not in posession of the token when he disconnected
        # If it was we have to unvalidate critial secion information and send token further

        if self.last_token > event.data['token'] + 1:
            return
        else:
            self.critical_section = None
            self.paint_queue.put(PaintBoardOpen())
            token = event.data['token'] + 1 if event.data['token'] else self.last_token + 1
            self.sending_queue.put(TokenPassEvent(token))

    def handle_entering_critical_section(self, event: EnteredCriticalSectionEvent):
        data = event.data
        if (data['client_uuid']) == self.uuid:
            return
        self.critical_section = {
            'timestamp': data['timestamp'],
            'client_uuid': data['client_uuid']
        }
        self.paint_queue.put(PaintBoardClosed())
        self.sending_queue.put(event)

    def handle_inner_leave_critical_section(self, event: InnerLeavingCriticalSection):
        self.critical_section = None
        self.paint_queue.put(PaintBoardOpen())
        if self.sending_queue:
            self.sending_queue.put(LeavingCriticalSectionEvent(NTP_timer.get_timestamp(), self.uuid))
            self.sending_queue.put(TokenPassEvent(self.last_token))
        else:
            self.main_queue.put(LeavingCriticalSectionEvent(NTP_timer.get_timestamp(), self.uuid))
            self.main_queue.put(TokenPassEvent(self.last_token))

    def handle_leave_critical_section(self, event: LeavingCriticalSectionEvent):
        data = event.data
        if (data['client_uuid']) == self.uuid:
            return

        if self.critical_section and self.critical_section['client_uuid'] == event.data['client_uuid']:
            self.paint_queue.put(PaintBoardOpen())
            self.critical_section = None

        self.sending_queue.put(event)

    def handle_new_next_next_hop(self, event: NewNextNextHop):
        post_destination_ip, _ = event.data['destination_next_hop']
        next_hop_ip, _ = self.next_hop_info

        # We are the recipient of the message
        if post_destination_ip == next_hop_ip:
            self.next_next_hop_info = event.data['new_address']
            logger.info('New next next hop5: {}'.format(self.next_next_hop_info))
        else:
            self.sending_queue.put(event)

    def handle_dummy_message_event(self, event: DummyMessageEvent):
        if self.sending_queue:
            if self.uuid != event.data['uuid']:
                return
            else:
                if self.sending_queue:
                    self.sending_queue.put(event)

    def handle_inner_next_hop_broken(self, event: InnerNextHopBroken):
        # If we detect that the next hop connection is down we want to:
        # 1.Try to reconnect to the client
        # 2.If reconnect fails we want to connect to our next next hop
        # 3.When we succesfully connect to our next next hop we want to send recovery token question
        #   in case that the dead client was holding the token the moment he died

        ip, port = self.next_next_hop_info
        # If we are the only client left we reset the data to the initial state
        if ip == utils.get_my_ip_address():
            self.critical_section = None
            self.next_hop_info = None
            logger.info('New next hop2: {}'.format(self.next_hop_info))
            self.next_next_hop_info = None
            logger.info('New next next hop6: {}'.format(self.next_next_hop_info))
            if self.message_sender:
                self.message_sender.stop()
            self.sending_queue = None
            self.message_sender = None
            self.predecessor = None
            logger.info('Predecessor3: {}'.format(self.predecessor))
            self.last_token = 0
            self.paint_queue.put(PaintBoardOpen())
            return

        def connect_to_next_next_hop(self):
            ip, port = self.next_next_hop_info
            try:
                s = socket.create_connection((ip, port))
                self.sending_queue = queue.Queue()
                self.message_sender = MessageSender(self.main_queue, self.sending_queue, s,
                                                    (s.getsockname()[0], s.getsockname()[1]))
                self.message_sender.run()
                self.next_hop_info = self.next_next_hop_info
                logger.info('New next hop3: {}'.format(self.next_hop_info))
                # After we connect to a new client we have to check whether the dead client wasn't in posession
                # of token
                self.sending_queue.put(TokenReceivedQuestionEvent(self.last_token))
            except Exception as e:
                logger.error(e)

        ip, port = self.next_hop_info
        try:
            s = socket.create_connection((ip, port))
            self.sending_queue = queue.Queue(maxsize=0)
            self.message_sender = MessageSender(self.main_queue, self.sending_queue, s,
                                                (s.getsockname()[0], s.getsockname()[1]))
            self.message_sender.run()
        except ConnectionRefusedError as e:
            logger.error(e)
            connect_to_next_next_hop(self)

    def handle_inner_want_to_enter_critical_section(self, event: InnerWantToEnterCriticalSection):
        self.want_to_enter_critical_section = True
