from enum import Enum


class EventType(Enum):
    NEW_CONNECTION_REQUEST = 0
    NEW_CLIENT_RESPONSE = 1
    NEW_PREVIOUS_HOP_REQUEST = 2
    PREVIOUS_HOP_MESSAGE = 3
    DRAWING_INFORMATION = 4
    ENTERED_CRITICAL_SECTION = 5
    LEAVING_CRITICAL_SECTION = 6
    TOKEN_PASS = 7
    SET_NEW_NEXT_NEXT_HOP = 8
    TOKEN_RECEIVED_QUESTION = 9
    CONTROL_PACKAGE = 10
    NEW_CLIENT_REQUEST = 11


class Event:
    def __init__(self):
        pass


class NewClientResponseEvent(Event):
    def __init__(self, next_hop, next_next_hop, board_state, critical_section_state):
        Event.__init__(self)
        self.data = {
            'next_hop': next_hop,
            'next_next_hop': next_next_hop,
            'board_state': board_state,
            'critical_section_state': critical_section_state
        }
        self.event_type = EventType.NEW_CLIENT_RESPONSE


class DrawingInformationEvent(Event):
    def __init__(self, client_uuid, timestamp, points, color):
        Event.__init__(self)
        self.data = {
            'points': points,
            'color': color,
            'client_uuid': client_uuid,
            'timestamp': timestamp
        }
        self.event_type = EventType.DRAWING_INFORMATION


class EnteredCriticalSectionEvent(Event):
    def __init__(self, timestamp, client_uuid):
        Event.__init__(self)
        self.data = {
            'timestamp': timestamp,
            'client_uuid': client_uuid
        }
        self.event_type = EventType.ENTERED_CRITICAL_SECTION


class LeavingCriticalSectionEvent(Event):
    def __init__(self, timestamp, client_uuid):
        Event.__init__(self)
        self.data = {
            'timestamp': timestamp,
            'client_uuid': client_uuid
        }
        self.event_type = EventType.LEAVING_CRITICAL_SECTION


class TokenPassEvent(Event):
    def __init__(self, token):
        Event.__init__(self)
        self.data = {
            'token': token
        }
        self.event_type = EventType.TOKEN_PASS


class NewNextNextHop(Event):
    def __init__(self, new_address, destination_next_hop):
        Event.__init__(self)
        self.data = {
            'new_address': new_address,
            'destination_next_hop': destination_next_hop
        }
        self.event_type = EventType.SET_NEW_NEXT_NEXT_HOP


class TokenReceivedQuestionEvent(Event):
    def __init__(self, token):
        Event.__init__(self)
        self.data = {
            'token': token
        }
        self.event_type = EventType.TOKEN_RECEIVED_QUESTION


class ControlPackageEvent(Event):
    def __init__(self, uuid):
        Event.__init__(self)
        self.data = {
            'uuid': uuid
        }
        self.event_type = EventType.CONTROL_PACKAGE


class NewClientRequestEvent(Event):
    def __init__(self, address):
        Event.__init__(self)
        self.data = {
            'address': address
        }
        self.event_type = EventType.NEW_CLIENT_REQUEST


#####################################################################################
#                                  Inner events
#####################################################################################
# Inner events are passed withing specific client and not send outside


class InnerNewConnectionEvent(Event):
    def __init__(self, address):
        Event.__init__(self)
        self.data = {
            'address': address
        }


class InnerNewClientRequestEvent(Event):
    def __init__(self, connection, address):
        Event.__init__(self)
        self.data = {
            'connection': connection,
            'address': address
        }


# Event when a new client is connecting to the previous_hop listener socket
class InnerNewPreviousHopRequestEvent(Event):
    def __init__(self, connection, address):
        Event.__init__(self)
        self.data = {
            'connection': connection,
            'address': address
        }


class InnerDrawingInformationEvent(Event):
    def __init__(self, timestamp, points, color):
        Event.__init__(self)
        self.timestamp = timestamp
        self.data = {
            'points': points,
            'color': color,
            'timestamp': timestamp
        }


class InnerWantToEnterCriticalSection(Event):
    def __init__(self):
        Event.__init__(self)


class InnerLeavingCriticalSection(Event):
    def __init__(self):
        Event.__init__(self)


class InnerNextHopBroken(Event):
    def __init__(self):
        Event.__init__(self)


class InnerCloseMainQueue(Event):
    def __init__(self):
        Event.__init__(self)


class InnerControlPackage(Event):
    def __init__(self):
        Event.__init__(self)


#####################################################################################
#                                  Paint Queue Events
#####################################################################################


class PaintQueueEvent(Enum):
    DRAWING = 1
    CONNECTION_FAILED = 2
    BOARD_OPEN = 3
    BOARD_CLOSED = 4
    BOARD_POSSESSED = 5
    BAD_BOARD_SIZE = 6


class PaintEvent:
    def __init__(self):
        self.type = 0


class PaintDrawing(PaintEvent):
    def __init__(self, points, color):
        PaintEvent.__init__(self)
        self.points = points
        self.color = color
        self.type = PaintQueueEvent.DRAWING


class PaintConnectionFail(PaintEvent):
    def __init__(self):
        PaintEvent.__init__(self)
        self.type = PaintQueueEvent.CONNECTION_FAILED


class PaintBoardOpen(PaintEvent):
    def __init__(self):
        PaintEvent.__init__(self)
        self.type = PaintQueueEvent.BOARD_OPEN


class PaintBoardClosed(PaintEvent):
    def __init__(self):
        PaintEvent.__init__(self)
        self.type = PaintQueueEvent.BOARD_CLOSED


class PaintBoardPossessed(PaintEvent):
    def __init__(self):
        PaintEvent.__init__(self)
        self.type = PaintQueueEvent.BOARD_POSSESSED


class PaintBadBoardSize(PaintEvent):
    def __init__(self):
        PaintEvent.__init__(self)
        self.type = PaintQueueEvent.BAD_BOARD_SIZE
