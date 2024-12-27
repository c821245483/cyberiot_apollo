"""A demonstration 'hub' that connects several devices."""
from __future__ import annotations
import asyncio
import random
import json
import requests
import aiohttp

from homeassistant.core import HomeAssistant


class CyberiotApollo:

    def __init__(self, hass: HomeAssistant, serial_number_name: str) -> None:
        self.serial_number_name = serial_number_name
        self.serial_number = serial_number_name.split("-")[-1]
        self._hass = hass
        # self._host = serial_number_name
        # self._name = serial_number_name
        # self._id = serial_number_name.lower()
        # self.name = serial_number_name
        # self._callbacks = set()
        # self._loop = asyncio.get_event_loop()
        # self._target_position = 100
        # self._current_position = 100
        # self.moving = 0
        # self.uuid_url = "http://{}/register".format(self.serial_number_name)
        # self.sync_url = "http://{}/sync".format(self.serial_number_name)
        # self.data_url = "http://{}/data-ctrl".format(self.serial_number_name)
        self.main_info_url = "http://{}.local/system-info".format(self.serial_number_name)
        self.uuid_url = "http://{}/register"
        self.sync_url = "http://{}/sync"
        self.data_url = "http://{}/data-ctrl"
        # self.main_info_url = "http://{}/system-info"

    async def register_uuid(self, host):
        data = {"user": self.serial_number,
                "password": "cyber2019"}
        json_data = json.dumps(data)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.uuid_url.format(host), data=json_data) as response:
                    if response.status == 200:
                        data = await response.json()
                        res = data.get("uuid", None)
                    else:
                        res = None
        except aiohttp.ClientError as e:
            # raise Exception(self.uuid_url2, e)
            # 处理网络错误
            res = None
        return res

    async def sync_data(self, device_uuid, host):
        data = {"uuid": device_uuid,
                "timestampFrom": 0,
                "timestampTo": 0}
        json_data = json.dumps(data)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.sync_url.format(host), data=json_data) as response:
                    if response.status == 200:
                        res = True
                    else:
                        res = False
        except aiohttp.ClientError as e:
            # 处理网络错误
            res = False
        return res

    async def data_ctrl(self, device_uuid, host):
        data = {"uuid": device_uuid,
                "rtdataEnable": 1,
                "syncEnable": 0,
                "logdataEnable": 0}
        json_data = json.dumps(data)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.data_url.format(host), data=json_data) as response:
                    if response.status == 200:
                        res = True
                    else:
                        res = False
        except aiohttp.ClientError as e:
            # 处理网络错误
            res = False
        return res

    async def check_connection(self) -> bool:
        """Test connectivity to the Dummy hub is OK."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(self.main_info_url) as response:
                    if response.status == 200:
                        res = True
                    else:
                        res = False
        except aiohttp.ClientError as e:
            # 处理网络错误
            res = False
        return res

    @property
    def online(self) -> float:
        """Roller is online."""
        # The dummy roller is offline about 10% of the time. Returns True if online,
        # False if offline.
        return True

    """
    @property
    def position(self):
        return self._current_position

    async def set_position(self, position: int) -> None:
        self._target_position = position

        # Update the moving status, and broadcast the update
        self.moving = position - 50
        await self.publish_updates()

        self._loop.create_task(self.delayed_update())

    async def delayed_update(self) -> None:
        await asyncio.sleep(random.randint(1, 10))
        self.moving = 0
        await self.publish_updates()

    def register_callback(self, callback: Callable[[], None]) -> None:
        self._callbacks.add(callback)

    def remove_callback(self, callback: Callable[[], None]) -> None:
        self._callbacks.discard(callback)

    # In a real implementation, this library would call it's call backs when it was
    # notified of any state changeds for the relevant device.
    async def publish_updates(self) -> None:
        self._current_position = self._target_position
        for callback in self._callbacks:
            callback()
    """


