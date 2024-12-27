"""Platform for sensor integration."""
import aiohttp
import asyncio
import logging
import struct

from homeassistant.components.sensor import (
    SensorDeviceClass,
)
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ApolloConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        config_entry: ApolloConfigEntry,
        async_add_entities: AddEntitiesCallback) -> None:
    """设置传感器平台"""
    apollo = config_entry.runtime_data
    host = config_entry.data["host"]
    sensor_title = config_entry.title
    if "004623000015" in sensor_title:
        uuid = await apollo.register_uuid(host)
        if uuid:
            data_ctrl_res = await apollo.data_ctrl(uuid, host)
            if data_ctrl_res:
                sensor_manager = WebSocketSensorManager(hass, async_add_entities, apollo, uuid, host)
                hass.loop.create_task(sensor_manager.start())


class WebSocketSensorManager:
    """管理 WebSocket 连接和传感器的类"""

    def __init__(self, hass, async_add_entities, apollo, uuid, host):
        self.hass = hass
        self.async_add_entities = async_add_entities
        self.sensors = {}  # 保存已经创建的传感器
        self.apollo = apollo
        self.websocket_url = "ws://{}/ws/interface?uuid={}"
        self.max_subdev_num = 3  # 假设最大子设备数量为10，你可以根据实际修改
        self.uuid = uuid
        self.host = host

    async def start(self):
        """启动 WebSocket 客户端"""
        # url = self.websocket_url.format(self.apollo.serial_number_name, self.uuid)
        url = self.websocket_url.format(self.host, self.uuid)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.ws_connect(url) as ws:
                    _LOGGER.info("WebSocket connection established")
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.BINARY:
                            await self.handle_message(msg.data)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            _LOGGER.error("WebSocket error: %s", msg.data)
        except Exception as e:
            _LOGGER.error("WebSocket connection failed: %s", e)

    async def handle_message(self, data):
        """处理 WebSocket 消息"""
        # 解析完整数据
        analysis_device_data = self.analysis_data(data)
        if analysis_device_data:
            device_datas = {"main": analysis_device_data["sampleDataWsPayload"]["mainChData"],
                            "sub": analysis_device_data["sampleDataWsPayload"]["subDevChData"]}

            for device_type, device_data in device_datas.items():
                if device_type == "main":
                    self.add_sensor(device_data, device_type)
                else:
                    for ind, sub_data in enumerate(device_data):
                        for ch_ind, ch_data in enumerate(sub_data["chDatas"]):
                            sub_ch_name = device_type + "_" + str(ind) + "-channel_" + str(ch_ind + 1)
                            self.add_sensor(ch_data, sub_ch_name)

    def add_sensor(self, data, device_type):
        for key, value in data.items():
            sensor_name = f"{device_type}-{key}"
            if sensor_name not in self.sensors:
                # 如果尚未创建对应的传感器，则创建
                new_sensor = BatterySensor(self.apollo, sensor_name)
                self.sensors[sensor_name] = new_sensor
                self.async_add_entities([new_sensor])
            # 更新传感器状态
            self.sensors[sensor_name].update_state(value)

    def analysis_data(self, data):
        offset = 0  # 偏移量
        # 解析 apolloWsPkgHead
        apollo_ws_pkg_head_format = "<IIII"  # version, crc, type, length
        apollo_ws_pkg_head_size = struct.calcsize(apollo_ws_pkg_head_format)
        version, crc, type_, length = struct.unpack_from(apollo_ws_pkg_head_format, data, offset)
        offset += apollo_ws_pkg_head_size
        if type_ != 2:
            return None
        apolloWsPkgHead = {
            "version": version,
            "crc": crc,
            "type": type_,
            "length": length,
        }

        # 解析 sampleDataWsPayload
        sample_data_ws_payload_format = "<IB"  # timeStamp, subDevNum
        sample_data_ws_payload_size = struct.calcsize(sample_data_ws_payload_format)
        timeStamp, subDevNum = struct.unpack_from(sample_data_ws_payload_format, data, offset)
        subDevNum = 2
        offset += sample_data_ws_payload_size

        # 解析 mainChData
        main_ch_data_format = "<iI"  # Power, Energy
        main_ch_data_size = struct.calcsize(main_ch_data_format)
        main_power, main_energy = struct.unpack_from(main_ch_data_format, data, offset)
        offset += main_ch_data_size

        mainChData = {
            "Power": main_power,
            "Energy": main_energy,
        }

        # 解析 subDevChData
        subDevChData = []
        for _ in range(1, subDevNum):
            # 解析子设备编号
            sub_dev_number_format = "<B"  # number
            sub_dev_number_size = struct.calcsize(sub_dev_number_format)
            number = struct.unpack_from(sub_dev_number_format, data, offset)[0]
            offset += sub_dev_number_size

            # 解析 10 个 chDatas
            ch_data_format = "<iI"  # Power, Energy
            ch_data_size = struct.calcsize(ch_data_format)
            chDatas = []
            for _ in range(10):  # 每个子设备有 10 个数据对
                power, energy = struct.unpack_from(ch_data_format, data, offset)
                offset += ch_data_size
                chDatas.append({
                    "Power": power,
                    "Energy": energy,
                })

            subDevChData.append({
                "number": number,
                "chDatas": chDatas,
            })

        sampleDataWsPayload = {
            "timeStamp": timeStamp,
            "subDevNum": subDevNum,
            "mainChData": mainChData,
            "subDevChData": subDevChData,
        }

        # 返回解析结果
        res = {
            "apolloWsPkgHead": apolloWsPkgHead,
            "sampleDataWsPayload": sampleDataWsPayload,
        }
        return res


class BatterySensor(Entity):
    """Representation of a Sensor."""

    device_class = SensorDeviceClass.POWER

    _attr_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, apollo, sensor_name):
        """Initialize the sensor."""
        # super().__init__(apollo)
        self._sensor_name = sensor_name
        self._state = None
        self._apollo = apollo

    @property
    def device_info(self):
        """Return information to link this entity with the correct device."""
        return {"identifiers": {(DOMAIN, self._apollo.serial_number_name)},
                "name": self._apollo.serial_number_name,
                "manufacturer": "Cyberiot",
                "model": "Apollo Device"}

    @property
    def unique_id(self):
        """返回唯一标识符"""
        return f"{self._apollo.serial_number_name}_{self._sensor_name}"

    @property
    def name(self):
        """返回传感器的名称"""
        return self._sensor_name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    def update_state(self, value):
        """更新传感器状态"""
        # if not self._initialized:
        #     _LOGGER.error("Cannot update state: Sensor %s is not initialized", self._attr_name)
        #     return
        self._state = value
        self.async_write_ha_state()
