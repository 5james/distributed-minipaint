import NTP_timer
from NewClientListener import *
from NewPreviousHopListener import *
from gui import *
from Model import *

logging.basicConfig(
    # filename="test.log",
    level=logging.DEBUG,
    format="%(asctime)s:%(levelname)s:%(message)s"
)

if __name__ == "__main__":
    main_queue = Queue()
    painter_queue = Queue()

    NTP_timer.set_offset()

    new_client_listener = NewClientListener(main_queue)
    new_client_listener.run()

    new_previous_hop_listener = NewPreviousHopListener(main_queue)
    new_previous_hop_listener.run()

    model = Model(main_queue, painter_queue, new_client_listener, new_previous_hop_listener)
    model.run()

    gui = Paint(main_queue, painter_queue, new_client_listener)
    gui.run()

    model.stop()
    new_client_listener.stop()
    new_previous_hop_listener.stop()
    NTP_timer.NTP_timer.cancel()
