from unittest.mock import Mock

from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.reasoncodes import ReasonCode

from ew11_analyzer.config import MqttConfig
from ew11_analyzer.sources.mqtt import MqttSource


def test_connect_callback_subscribes_with_paho_reason_code():
    source = MqttSource(MqttConfig(topic="EW11/Pub"))
    source._status = Mock()
    client = Mock()

    source._handle_connect(client, None, None, ReasonCode(PacketTypes.CONNACK), None)

    source._status.assert_called_once_with("connected")
    client.subscribe.assert_called_once_with("EW11/Pub")
