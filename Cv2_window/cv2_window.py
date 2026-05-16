import cv2
import numpy as np
import threading
from typing import Callable, Optional, Any
import time
import logging
import tkinter

try:
    import log #only a colorful logger
    logger = log.Logger("CV2Window_model")
    logger.setLevel(logging.INFO)
except ImportError:
    logger = logging.getLogger("CV2Window_model")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.warning("'log' module not found, using default logger")

class CV2Window:
    """
    A thread-safe OpenCV window display class.
    Supports multi-threaded image updates, custom mouse/keyboard event handling, 
    automatic scaling, and centered display.
    """
    def __init__(self, pic: np.ndarray, name: str, fps: int = 24, auto_scale: float = 0.8, auto_copy: bool = False):
        """
        Initialize CV2Window.
        You should use "show()" to start the window display, use "update()" to update the image, 
        and "close()" to close the window.
        You could use "self.args: dict[name,value]" to store or get additional information.
        If image may be modified, please set "auto_copy" to True.

        :param pic: Initial image to display (numpy array).
        :param name: Window name.
        :param fps: Refresh frame rate.
        :param auto_scale: Maximum ratio of screen occupied by the window (0.0 - 1.0). 
                           If 0, automatic scaling is disabled.
        :param auto_copy: If True, a copy of the image is made for each update.
        """
        ROOT = tkinter.Tk()
        self.screen_width = ROOT.winfo_screenwidth()
        self.screen_height = ROOT.winfo_screenheight()
        ROOT.destroy()
        self.auto_copy = auto_copy
        self._pic = pic.copy() if auto_copy else pic
        self.name = name
        self.fps = max(1, fps)
        self.auto_scale = max(0, min(1.0, auto_scale))
        self.args: dict = {}

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._pic_lock = threading.Lock()
        self._close_event = threading.Event()
        
        self._mouse_actions: dict[int, Callable[[int, int, int, int, Any], None]] = {
            cv2.EVENT_LBUTTONUP: self._on_l_up,
            cv2.EVENT_LBUTTONDOWN: self._on_l_down,
            cv2.EVENT_RBUTTONUP: self._on_r_up,
            cv2.EVENT_RBUTTONDOWN: self._on_r_down,
            cv2.EVENT_MBUTTONDOWN: self._on_m_down,
            cv2.EVENT_MBUTTONUP: self._on_m_up,
            cv2.EVENT_MOUSEWHEEL: self._on_scroll,
            cv2.EVENT_LBUTTONDBLCLK: self._on_double_l_click,
            cv2.EVENT_RBUTTONDBLCLK: self._on_double_r_click,
            cv2.EVENT_MOUSEMOVE: self._on_drag,
        }
        
        self._board_event_handler: Callable[[int], None] = self._default_board_event
        self._mouse_event_handler: Callable[[int, int, int, int, Any], None] = self._mouse_callback
        self._show_callback = lambda: None

    def show(self):
        """
        Start window display in a background thread. Ignored if already running.
        """
        if self._running:
            logger.warning(f"Window '{self.name}' is already running.")
            return

        self._close_event.clear()
        self._running = True
        self._thread = threading.Thread(target=self._display_, daemon=True, name=f"CV2Window-{self.name}")
        self._thread.start()
        logger.info(f"Window '{self.name}' started.")

    def close(self):
        """
        Close the window and stop the background thread.
        """
        if not self._running:
            return
            
        self._running = False
        self._close_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                logger.warning(f"Thread for window '{self.name}' did not terminate gracefully.")
        try:
            cv2.destroyWindow(self.name)
        except cv2.error as e:
            if e.code != -27:
                logger.error(f"Error destroying window: {e}")

        self._thread = None
        logger.info(f"Window '{self.name}' closed.")

    def update(self, pic: np.ndarray):
        """
        Thread-safely update the image displayed in the window.
        
        :param pic: New image data.
        """
        if pic is None or not isinstance(pic, np.ndarray):
            logger.warning("Invalid image provided to update().")
            return
            
        with self._pic_lock:
            self._pic = pic.copy() if self.auto_copy else pic

    def change_mouse_event(self, event: int, function: Callable[[int, int, int, int, Any], None]):
        """
        Change the callback function for a specific mouse event.
        
        :param event: OpenCV mouse event constant (e.g., cv2.EVENT_LBUTTONDOWN).
        :param function: Callback function with signature func(event, x, y, flags, param).
        """
        if event in self._mouse_actions:
            self._mouse_actions[event] = function
        else:
            logger.warning(f"Event {event} is not supported or recognized.")

    def change_board_event(self, function: Callable[[int], None]):
        """
        Set custom keyboard event handling logic.
        Note: This function is called in every loop iteration with the current key value (int).
        Do not call cv2.waitKey inside this function, as it is handled by the underlying loop.
        
        :param function: Callback function receiving the key value (int), defaults: `lambda key: logger.debug(f"Key pressed: {key}")`
        """
        self._board_event_handler = function

    def set_mouse_callback(self, function: Callable[[int, int, int, int, Any], None]):
        """
        Set custom mouse event handling logic.
        Note: This function is called in every loop iteration with the current mouse event.
        Defaults: 
        `def function(event, x, y, flags, param):
            if event in self._mouse_actions:
                try:
                    self._mouse_actions[event](event, x, y, flags, param)
                except Exception as e:
                    logger.error(f"Error in mouse event handler for event {event}: {e}")`

        :param function: Callback function with signature func(event, x, y, flags, param).
        """
        self._mouse_event_handler = function

    def set_show_callback(self, function: Callable[[], None]):
        """
        Add a callback function to be executed when the window is shown.
        This function is called before each frame refresh.
        
        :param function: Callback function, defaults: `lambda: None`
        """
        self._show_callback = function

    def _display_(self):
        """
        Main loop of the background thread, responsible for creating the window, 
        handling events, and refreshing the image.
        """
        try:
            cv2.namedWindow(self.name, cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
            cv2.setMouseCallback(self.name,self._mouse_event_handler)
            self._adjust_window_initial_state()
            time.sleep(0.1)
            frame_time = 1.0 / self.fps
            last_time = time.time()
            while self._running and not self._close_event.is_set():
                start_time = time.time()
                wait_time = max(0, frame_time - (start_time - last_time))
                time.sleep(wait_time) #Generally, it doesn't need to be too precise.
                last_time = start_time
                if cv2.getWindowProperty(self.name, cv2.WND_PROP_VISIBLE) < 1:
                    break
                key = cv2.pollKey() & 0xFF
                if key != 255:
                    try:
                        self._board_event_handler(key)
                    except Exception as e:
                        logger.exception(f"Error in keyboard event handler for window '{self.name}': {e}")
                try:
                    self._show_callback()
                except Exception as e:
                    logger.exception(f"Error in show callback for window '{self.name}': {e}")

                # Display
                with self._pic_lock:
                    current_pic = self._pic.copy() if self.auto_copy else self._pic
                if current_pic is not None and current_pic.size > 0:
                    cv2.imshow(self.name, current_pic)
        
        except Exception as e:
            logger.exception(f"Error in display loop for window '{self.name}': {e}", exc_info=True)

    def _adjust_window_initial_state(self):
        """
        Adjust the initial size and position of the window based on screen dimensions 
        and auto_scale setting.
        """
        try:
            h, w = self._pic.shape[:2]
            scale_w = (self.screen_width * self.auto_scale) / w
            scale_h = (self.screen_height * self.auto_scale) / h
            scale = min(scale_w, scale_h, 1.0)

            display_w = int(w * scale) if self.auto_scale > 0 else w
            display_h = int(h * scale) if self.auto_scale > 0 else h

            pos_x = max(0, (self.screen_width - display_w) // 2)
            pos_y = max(0, (self.screen_height - display_h) // 2)
            
            cv2.resizeWindow(self.name, display_w, display_h)
            cv2.moveWindow(self.name, pos_x, pos_y)
            
        except Exception as e:
            logger.warning(f"Skip, could not adjust window position/size automatically: {e}")

    def _mouse_callback(self, event: int, x: int, y: int, flags: int, param: Any):
        """
        Unified entry point for OpenCV mouse events.
        """
        if event in self._mouse_actions:
            try:
                self._mouse_actions[event](event, x, y, flags, param)
            except Exception as e:
                logger.error(f"Error in mouse event handler for event {event}: {e}")
    def _default_board_event(self, key: int):
        """Default keyboard event handler"""
        if key == 27: # ESC
            logger.debug("ESC pressed, closing window.")
            #self.close()
            self._inner_close()
        else:
            logger.debug(f"Key pressed: {key}")

    def _inner_close(self):
        self._running = False
        self._close_event.set()
        try:
            cv2.destroyWindow(self.name)
        except Exception as e:
            logger.warning(f"Error while closing window: {e}.")
    def _on_l_up(self, event, x, y, flags, param):
        logger.debug(f"Left Button Up: ({x}, {y})")

    def _on_l_down(self, event, x, y, flags, param):
        logger.debug(f"Left Button Down: ({x}, {y})")

    def _on_r_up(self, event, x, y, flags, param):
        logger.debug(f"Right Button Up: ({x}, {y})")

    def _on_r_down(self, event, x, y, flags, param):
        logger.debug(f"Right Button Down: ({x}, {y})")

    def _on_m_down(self, event, x, y, flags, param):
        logger.debug(f"Middle Button Down: ({x}, {y})")

    def _on_m_up(self, event, x, y, flags, param):
        logger.debug(f"Middle Button Up: ({x}, {y})")

    def _on_scroll(self, event, x, y, flags, param):
        direction = "Up" if flags > 0 else "Down"
        logger.debug(f"Scroll {direction}: ({x}, {y})")

    def _on_double_l_click(self, event, x, y, flags, param):
        logger.debug(f"Left Double Click: ({x}, {y})")

    def _on_double_r_click(self, event, x, y, flags, param):
        logger.debug(f"Right Double Click: ({x}, {y})")

    def _on_drag(self, event, x, y, flags, param):
        if flags & cv2.EVENT_FLAG_LBUTTON:
            logger.debug(f"Left Drag: ({x}, {y})")
        elif flags & cv2.EVENT_FLAG_RBUTTON:
            logger.debug(f"Right Drag: ({x}, {y})")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    pic = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(pic, "Image 1", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
    pic_2 = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.putText(pic_2, "Image 2", (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    def new_board_event(key):
        logger.info(f"Key pressed: {key}")
        if key == ord(' '):
            print("Space bar pressed!")
        elif key == 27:
            print("ESC pressed via custom handler!")

    # Test 1: Single window usage (Original test)
    with CV2Window(pic, "Test Window", fps=30, auto_scale=0.5) as cv2_window:
        cv2_window.change_board_event(new_board_event)
        cv2_window.show()
        for i in range(15):
            time.sleep(0.1)
            if i % 2 == 0:
                cv2_window.update(pic_2)
            else:
                cv2_window.update(pic)
    print("Application finished single window test.")

    # Test 2: Multi-window usage
    print("Starting multi-window test...")
    win1_img = np.ones((400, 400, 3), dtype=np.uint8) * 255  # White background
    cv2.putText(win1_img, "Window 1", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

    win2_img = np.ones((400, 400, 3), dtype=np.uint8) * 0  # Black background
    cv2.putText(win2_img, "Window 2", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

    window1 = CV2Window(win1_img, "Multi-Test Win 1", fps=2, auto_scale=0.4)
    window2 = CV2Window(win2_img, "Multi-Test Win 2", fps=24, auto_scale=0.4)

    try:
        start_time = time.time()

        def update_img(CV2Window:CV2Window,base_img):
            current_time = time.time()
            time_struct = time.localtime(current_time)
            milliseconds = int((current_time % 1) * 1000)
            timestamp = time.strftime("%H:%M:%S", time_struct) + f".{milliseconds:03d}"
            if CV2Window.args.get("last_time", 0) == 0:
                CV2Window.args["last_time"] = time.time()
                return
            current_time = time.time()
            last_time = CV2Window.args.get("last_time", current_time)
            dt = current_time - last_time
            if dt <= 0:
                return
            fps_val = 1.0 / dt
            CV2Window.args["fps"] = fps_val
            CV2Window.args["last_time"] = current_time
            img = base_img.copy()
            cv2.putText(img, timestamp, (50, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            fps_text = f"FPS: {fps_val:.2f}"
            cv2.putText(img, fps_text, (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            CV2Window.update(img)
        def get_fps_windows1():
            update_img(window1,win1_img)
        def get_fps_windows2():
            update_img(window2,win2_img)

        window1.set_show_callback(get_fps_windows1)
        window2.set_show_callback(get_fps_windows2)

        window1.show()
        window2.show()

        for i in range(1000):
            if not window1._running and not window2._running:
                break
            time.sleep(1) # Run for 10 seconds
        print("Multi-window test finished. Closing windows...")
    except Exception as e:
        logger.error(f"Error during multi-window test: {e}")
    finally:
        window1.close()
        window2.close()
    print("All tests completed.")
