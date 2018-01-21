from tkinter import *
import tkinter.font
import tkinter.messagebox
from queue import *
from NewClientListener import *
import NTP_timer
import re
from Event import *

PAINT_WIDTH = 250
PAINT_HEIGHT = 250


def line(x0, y0, x1, y1):
    """Bresenham's line algorithm"""
    points_in_line = []
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    x, y = x0, y0
    sx = -1 if x0 > x1 else 1
    sy = -1 if y0 > y1 else 1
    if dx > dy:
        err = dx / 2.0
        while x != x1:
            points_in_line.append((x, y))
            err -= dy
            if err < 0:
                y += sy
                err += dx
            x += sx
    else:
        err = dy / 2.0
        while y != y1:
            points_in_line.append((x, y))
            err -= dx
            if err < 0:
                x += sx
                err += dy
            y += sy
    points_in_line.append((x, y))
    return points_in_line


class Paint:
    # Tracks whether left mouse is down
    left_but = "up"

    # x and y positions for drawing with pencil
    x_pos, y_pos = None, None

    # Tracks x & y when the mouse is clicked and released
    x1_line_pt, y1_line_pt, x2_line_pt, y2_line_pt = None, None, None, None

    # ---------- CATCH MOUSE UP ----------

    def left_but_down(self, event=None):
        self.left_but = "down"

        # Set x & y when mouse is clicked
        self.x1_line_pt = event.x
        self.y1_line_pt = event.y

    def left_but_up(self, event=None):
        self.left_but = "up"

        # Reset the line
        self.x_pos = None
        self.y_pos = None

        # Set x & y when mouse is released
        self.x2_line_pt = event.x
        self.y2_line_pt = event.y

    def motion(self, event=None):
        if event is not None and self.left_but == 'down':
            color = 0 if self.drawing_color == 'white' else 1

            # Make sure x and y have a value
            if self.x_pos is not None and self.y_pos is not None:
                # event.widget.create_line(self.x_pos, self.y_pos, event.x, event.y)
                # self.painting_queue.put((event, self.x_pos, self.y_pos))  #

                points = line(self.x_pos, self.y_pos, event.x, event.y)
                # self.painting_queue.put(points)
                self.main_queue.put(InnerDrawingInformationEvent(NTP_timer.get_timestamp(), points, color))

            self.x_pos = event.x
            self.y_pos = event.y
            # print("x = " + str(event.x) + "\ty = " + str(event.y))

    def __init__(self, main_queue: Queue, paint_queue: Queue, new_client_listener: NewClientListener):
        self.running = True
        self.drawing_color = 'black'

        self.main_queue = main_queue
        self.paint_queue = paint_queue
        new_client_listener = new_client_listener
        ip = new_client_listener.socket.getsockname()[0]
        port = new_client_listener.socket.getsockname()[1]

        self.tk = tkinter.Tk()
        self.tk.protocol('WM_DELETE_WINDOW', self.on_closing)

        self.drawing_area = Canvas(self.tk, width=PAINT_WIDTH, height=PAINT_HEIGHT, background='white')
        self.drawing_area.grid(row=0, column=1, sticky="n")

        self.drawing_area.bind("<Motion>", self.motion)
        self.drawing_area.bind("<ButtonPress-1>", self.left_but_down)
        self.drawing_area.bind("<ButtonRelease-1>", self.left_but_up)

        frame_left_panel = Frame(self.tk)
        frame_left_panel.grid(row=0, column=0, sticky="n")

        self.labelConnectionInfo = Label(frame_left_panel, text="My address:")
        self.labelConnectionInfo.grid(row=0, column=0, sticky="nw")
        self.labelConnectionMyAddress = Label(frame_left_panel, text="{}:{}".format(ip, port))
        self.labelConnectionMyAddress.grid(row=0, column=1, sticky="ne")
        self.labelConnectionInfo2 = Label(frame_left_panel, text="Connect:")
        self.labelConnectionInfo2.grid(row=1, column=0, sticky="nw")
        self.entryConnectionAddress = StringVar()
        self.entryConnectionAddress.set('192.168.43.87:8899')
        self.entryConnection = Entry(frame_left_panel, textvariable=self.entryConnectionAddress)
        self.entryConnection.grid(row=1, column=1, sticky='ne')
        self.buttonConnection = Button(frame_left_panel, text='Connect', command=self.new_connection)
        self.buttonConnection.grid(row=2, column=1, sticky='ne')
        self.labelBoardStateInfo = Label(frame_left_panel, text="Board state :")
        self.labelBoardStateInfo.grid(row=3, column=0, sticky="nw")
        self.boardState = StringVar()
        self.boardState.set('Board Open')
        self.labelBoardState = Label(frame_left_panel, textvariable=self.boardState)
        self.labelBoardState.grid(row=3, column=1, sticky="nw")
        self.buttonEnterCriticalSection = Button(frame_left_panel, text='Possess board',
                                                 command=self.handle_enter_to_critical_section)
        self.buttonEnterCriticalSection.grid(row=4, sticky='n')
        self.labelColorInfo = Label(frame_left_panel, text='Current color:')
        self.labelColorInfo.grid(row=5, column=0, sticky='nw')
        self.buttonColorString = StringVar()
        self.buttonColorString.set('black')
        self.buttonChangeColor = Button(frame_left_panel, textvariable=self.buttonColorString,
                                        command=self.handle_change_color)
        self.buttonChangeColor.grid(row=5, column=1, sticky='nw')

    def on_closing(self):
        # global running
        self.running = False

    def getrda(self):
        return self.drawing_area

    def run(self):
        # while self.running:
        #     self.make_mouse_events()
        #     while not self.painting_queue.empty():
        #         points = self.painting_queue.get()
        #         for point in points:
        #             self.drawing_area.create_rectangle((point[0], point[1]) * 2, outline='black')
        while self.running:
            self.make_mouse_events()
            while not self.paint_queue.empty():
                e = self.paint_queue.get()
                if isinstance(e, PaintEvent):
                    if e.type == PaintQueueEvent.DRAWING:
                        points = e.points
                        color = 'white' if e.color == 0 else 'black'
                        for point in points:
                            self.drawing_area.create_rectangle((point[0], point[1]) * 2, outline=color)
                    elif e.type == PaintQueueEvent.BOARD_CLOSED:
                        self.boardState.set("Board closed")
                    elif e.type == PaintQueueEvent.BOARD_OPEN:
                        self.boardState.set("Board open")
                    elif e.type == PaintQueueEvent.BOARD_POSSESSED:
                        self.boardState.set("Board possessed")
                    elif e.type == PaintQueueEvent.CONNECTION_FAILED:
                        tkinter.messagebox.showinfo("Bad host address", "At given address there is no host.")
                    elif e.type == PaintQueueEvent.BAD_BOARD_SIZE:
                        pass
                        # Because of canvas behaviour must omit this one
                        # tkinter.messagebox.showinfo("Error",
                        #                             "Board initialized with bad size!\nThe program will not stop"
                        #                             " running but it is advisably for you to restart it with proper"
                        #                             " board size.")
                        ## return
                    else:
                        raise Exception('Wrong event type in painting queue.')
                else:
                    raise Exception('Wrong event type in painting queue.')

    def make_mouse_events(self):
        if self.running:
            self.tk.update_idletasks()
            self.tk.update()

    def handle_enter_to_critical_section(self):
        self.main_queue.put(InnerWantToEnterCriticalSection())

    def handle_change_color(self):
        if self.buttonColorString.get() == 'black':
            self.buttonColorString.set('white')
            self.drawing_color = 'white'
        else:

            self.buttonColorString.set('black')
            self.drawing_color = 'black'

    def new_connection(self):
        self.drawing_area.delete('all')
        address = self.entryConnectionAddress.get()
        match = re.findall(r'[0-9]+(?:\.[0-9]+){3}:[0-9]+', address)
        if len(match) != 1:
            tkinter.messagebox.showinfo("Bad host address",
                                        "Address given is bad. It should be IPv4:PORT.\nExample: 127.0.0.1:8080")
        else:
            self.main_queue.put(InnerNewConnectionEvent(self.entryConnectionAddress.get()))


if __name__ == "__main__":
    import queue
    import NewClientListener

    q = queue.Queue()
    p = Paint(q, queue.Queue(), NewClientListener.NewClientListener(q))
    p.run()
