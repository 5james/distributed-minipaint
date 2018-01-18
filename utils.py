import socket
import json
import time

running = True


def get_my_ip_address():
    return socket.gethostbyname(socket.gethostname())


def event_to_message(event):
    message = {'type': event.event_type.value, 'data': event.data}
    message_json = json.dumps(message)
    return message_json.encode('utf-8')
