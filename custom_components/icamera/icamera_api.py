from aiohttp import ClientResponse, ClientSession
import aiohttp

import urllib.parse

DEFAULT_THRESHHOLD = 20
DEFAULT_SENSITIVITY = 6


class ICameraMotionWindow:
    def __init__(self, window_num: int) -> None:
        self._window_num = window_num
        self._name = ""
        self._x = 0
        self._y = 0
        self._x2 = 0
        self._y2 = 0
        self._threshold = DEFAULT_THRESHHOLD
        self._sensitivity = DEFAULT_SENSITIVITY
        self._is_on = False

    def set_name(self, name: str):
        self._name = name

    def set_coordinates(self, x: int, y: int, x2: int, y2: int):
        self._x = x
        self._y = y
        self._x2 = x2
        self._y2 = y2

    def set_coordinates_from_string(self, coordinates: str):
        pos1 = coordinates.find(",")
        pos2 = coordinates.find(",", pos1 + 1)
        pos3 = coordinates.find(",", pos2 + 1)
        if pos1 >= 0 and pos2 >= 0 and pos3 >= 0:
            x = int(coordinates[0:pos1])
            y = int(coordinates[pos1 + 1 : pos2])
            x2 = int(coordinates[pos2 + 1 : pos3])
            y2 = int(coordinates[pos3 + 1 :])
            self.set_coordinates(x, y, x2, y2)

    def set_threshold(self, threshold: int = DEFAULT_THRESHHOLD):
        """Set motion threshold - 0-255"""
        self._threshold = threshold

    def set_sensitivity(self, sensitivity: int = DEFAULT_SENSITIVITY):
        """Set motion sensitivity - 0-10"""

    def set_is_on(self, on: bool):
        self._is_on = on

    @property
    def window_num(self) -> int:
        return self._window_num

    @property
    def name(self) -> str:
        return self._name

    @property
    def coordinates(self) -> str:
        return f"{self._x},{self._y},{self._x2},{self._y2}"

    @property
    def threshold(self) -> int:
        """Threshold (0-255)"""
        return self._threshold

    @property
    def sensitivity(self) -> int:
        """sensitivity (0-10)"""
        return self._sensitivity

    @property
    def is_on(self) -> bool:
        return self._is_on


class ICameraApi:
    """API class for ICamera IP camera"""

    def __init__(
        self,
        hostname: str,
        httpport: int,
        rtspport: int,
        username: str,
        password: str,
        streamtype: str = "RTSP",
    ) -> None:
        self._hostname = hostname
        self._httpport = httpport
        self._rtspport = rtspport
        self._username = username
        self._password = password
        self._stream_type = streamtype
        self._motion_callback_url = ""
        self._send_email_on_motion = False
        self._motion_windows = [
            ICameraMotionWindow(1),
            ICameraMotionWindow(2),
            ICameraMotionWindow(3),
            ICameraMotionWindow(4),
        ]
        self._is_motion_detection_enabled = False
        self._unauthorized_callback = None
        self._update_callbacks: list = []

    @property
    def is_motion_detection_enabled(self) -> bool:
        return self._is_motion_detection_enabled

    @property
    def config_url(self) -> str:
        return f"http://{self._hostname}:{self._httpport}"

    @property
    def send_email_on_motion(self) -> bool:
        return self._send_email_on_motion

    @property
    def motion_callback_url(self) -> str:
        return self._motion_callback_url

    def subscribe_to_updates(self, callback):
        self._update_callbacks.append(callback)

    def set_unathorized_callback(self, callback):
        """Define function to be called whenever camera returns a 401 unauthorized response"""
        self._unauthorized_callback = callback

    def __unauthorized(self):
        if self._unauthorized_callback is not None:
            self._unauthorized_callback()

    def get_motion_window(self, window_num: int) -> ICameraMotionWindow:
        return self._motion_windows[window_num - 1]

    def auth(self):
        return aiohttp.BasicAuth(self._username, self._password)

    async def stream_source(self) -> str:
        """Return the source of the stream."""
        if self._stream_type == "RTSP":
            return f"rtsp://{self._hostname}:{str(self._rtspport)}/img/media.sav"
        else:
            return (
                "http://"
                + self._hostname
                + ":"
                + str(self._httpport)
                + "/img/video.mjpeg"
            )

    async def async_camera_image(
        self, session: ClientSession, width=None, height=None
    ) -> bytes:
        """Return bytes of camera image."""
        response = await self.async_get_camera_response(session, "/img/snapshot.cgi")

        if response.status != 200:
            return None
        else:
            return await response.read()

    async def async_set_motion_callback_url(
        self, session: ClientSession, url: str
    ) -> bool:
        callback_url = urllib.parse.quote(url, safe="'")
        response = await self.async_send_camera_command(
            session,
            f"/adm/set_group.cgi?group=HTTP_NOTIFY&http_notify=1&http_url={callback_url}",
        )
        if response:
            self._motion_callback_url = url
        return response

    async def async_set_email_on_motion(
        self, session: ClientSession, email_flag: bool
    ) -> bool:
        on_string = "0"
        if email_flag:
            on_string = "1"
        response = await self.async_send_camera_command(
            session,
            f"/adm/set_group.cgi?group=EVENT&event_interval=0&event_mt=email:{on_string}",
        )
        if response:
            self._send_email_on_motion = email_flag

    async def async_send_camera_command(self, session: ClientSession, path: str):
        response = await self.async_get_camera_response(session, path)
        if response.status == 200:
            return True
        else:
            return False

    async def async_get_camera_response(
        self, session: ClientSession, path: str
    ) -> ClientResponse:
        hostaddress = f"http://{self._hostname}:{str(self._httpport)}{path}"

        response = await session.get(hostaddress, auth=self.auth())
        if response.status == 401:
            self.__unauthorized()
        return response

    async def async_is_connection_valid(self, session: ClientSession):
        return self.async_send_camera_command(session, "/adm/log.cgi")

    async def async_set_motion_window_active(
        self, session: ClientSession, window_num: int, flag: bool
    ):
        on_string = "0"
        if flag:
            on_string = "1"
        response = await self.async_send_camera_command(
            session,
            f"/adm/set_group.cgi?group=MOTION&md_switch{window_num}={on_string}",
        )
        if response:
            self._motion_windows[window_num - 1].set_is_on(flag)

    async def async_set_motion_detection_active(
        self, session: ClientSession, flag: bool
    ):
        on_string = "0"
        if flag:
            on_string = "1"
        response = await self.async_send_camera_command(
            session,
            f"/adm/set_group.cgi?group=EVENT&event_trigger={on_string}",
        )
        if response:
            self._is_motion_detection_enabled = flag

    async def async_set_motion_window_coordinates(
        self,
        session: ClientSession,
        window_num: int,
        x: int,
        y: int,
        x2: int,
        y2: int,
    ):
        response = await self.async_send_camera_command(
            session,
            f"/adm/set_group.cgi?group=MOTION&md_window{window_num}={x},{y},{x2},{y2}",
        )
        if response:
            self._motion_windows[window_num - 1].set_coordinates(x, y, x2, y2)

    async def async_set_motion_window_name(
        self, session: ClientSession, window_num: int, name: str
    ):
        response = await self.async_send_camera_command(
            session,
            f"/adm/set_group.cgi?group=MOTION&md_name{window_num}={urllib.parse.quote(name,safe='')}",
        )
        if response:
            self._motion_windows[window_num - 1].set_name(name)

    async def async_set_motion_window_threshold(
        self, session: ClientSession, window_num: int, threshold: int
    ):
        """Set motion window threshold (0-255)"""
        response = await self.async_send_camera_command(
            session,
            f"/adm/set_group.cgi?group=MOTION&md_threshold{window_num}={threshold}",
        )
        if response:
            self._motion_windows[window_num - 1].set_threshhold(threshold)

    async def async_set_motion_window_sensitivity(
        self, session: ClientSession, window_num: int, sensitivity: int
    ):
        """Set motion window sensitivity (0-10)"""
        response = await self.async_send_camera_command(
            session,
            f"/adm/set_group.cgi?group=MOTION&md_sensitivity{window_num}={sensitivity}",
        )
        if response:
            self._motion_windows[window_num - 1].set_sensitivity(sensitivity)

    async def async_update_camera_parameters(self, session: ClientSession):
        """Query camera for parameter values"""

        # TODO: limit requests to 1 per 3 seconds

        event_response = self.async_get_camera_response(
            session, "/adm/get_group.cgi?group=EVENT"
        )  # for alarm (event_trigger & event_mt)
        motion_response = self.async_get_camera_response(
            session, "/adm/get_group.cgi?group=MOTION"
        )  # for alarm (event_trigger & event_mt)
        notify_response = self.async_get_camera_response(
            session, "/adm/get_group.cgi?group=HTTP_NOTIFY"
        )  # for alarm (event_trigger & event_mt)

        response = await event_response
        if response.status == 200:
            self.__process_response_text(await response.text())

        response = await motion_response
        if response.status == 200:
            self.__process_response_text(await response.text())

        response = await notify_response
        if response.status == 200:
            self.__process_response_text(await response.text())

    async def async_check_log_for_motion_event(self, session: ClientSession) -> bool:
        """Returns true if the most recent log entry in the camera indicates motion (use this for confirming motion events fired by async_set_motion_callback_url"""
        response = await self.async_get_camera_response(session, "/adm/log.cgi")

        if response.status == 200:
            return await self.__process_response_text(await response.text()) == "motion"

    def __get_line(self, text: str, start_pos: int) -> str:
        eol_char = ""
        if text.find("\r") >= 0:
            eol_char = "\r"
        elif text.find("\n") >= 0:
            eol_char = "\n"
        else:
            return text[start_pos:]

        text = text[start_pos:]
        return text[0 : text.find(eol_char)]

    def __process_response_text(self, body: str) -> str:
        startOfLine = 0
        pos = body.find("<title>")
        if pos >= 0:
            startOfLine = pos

        first_line = self.__get_line(body, startOfLine)

        if first_line.find("log.cgi") >= 0:
            dateAndTime = first_line.substring(0, 20)
            if body.find(
                f"{dateAndTime}DEAMON: /usr/local/bin/stream_server"
            ):  # I think this indicates a "motion detected" line
                return "motion"
            else:
                return ""

        pos = body.find("event_mt=")
        eventMTLine = ""
        if pos >= 0:
            eventMTLine = self.__get_line(body, pos)

        if body.find("event_trigger=0") >= 0 or eventMTLine.find("httpn:0") >= 0:
            self._is_motion_detection_enabled = False
        elif (
            body.find("event_trigger=1") >= 0 and body.find("httpn:1") >= 0
        ):  # is this right?  Copied from ST device handler
            self._is_motion_detection_enabled = True

        if body.find("http_notify=0") >= 0:
            self._motion_callback_url = ""
        elif body.find("http_notify=1") >= 0:
            pos = body.find("http_url=")
            if pos >= 0:
                self._motion_callback_url = self.__get_line(body, pos + 9)

        pos = eventMTLine.find("email:")
        if pos >= 0:
            send_email_on_motion = eventMTLine[pos + 6 : pos + 7]
            if send_email_on_motion == "1":
                self._send_email_on_motion = True
            else:
                self._send_email_on_motion = False

        # if(body.find("event_interval=")) eventInterval = getLine(body, body.indexOf("event_interval=") + 15)
        for i in range(1, 4):  # loop 1-4
            pos = body.find(f"md_switch{i}=")
            if pos >= 0:
                switch_string = self.__get_line(body, pos + 11)
                switch_val = False
                if switch_string == "1":
                    switch_val = True
                self._motion_windows[i - 1].set_is_on(switch_val)

            pos = body.find(f"md_name{i}=")
            if pos >= 0:
                self._motion_windows[i - 1].set_name(self.__get_line(body, pos + 9))

            pos = body.find(f"md_window{i}=")
            if pos >= 0:
                self._motion_windows[i - 1].set_coordinates_from_string(
                    self.__get_line(body, pos + 11)
                )

            pos = body.find(f"md_sensitivity{i}=")
            if pos >= 0:
                self._motion_windows[i - 1].set_sensitivity(
                    self.__get_line(body, pos + 16)
                )

            pos = body.find(f"md_threshold{i}=")
            if pos >= 0:
                self._motion_windows[i - 1].set_threshold(
                    self.__get_line(body, pos + 14)
                )

        for callback in self._update_callbacks:
            callback()

        return ""
