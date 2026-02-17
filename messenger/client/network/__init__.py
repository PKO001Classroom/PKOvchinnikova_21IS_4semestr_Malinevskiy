"""
Пакет сетевого взаимодействия клиента.
"""

from client.network.websocket_client import MessengerWebSocket, get_websocket_instance, remove_websocket_instance
from client.network.broadcast_client import BroadcastClient, get_broadcast_client

__all__ = [
    'MessengerWebSocket', 'get_websocket_instance', 'remove_websocket_instance',
    'BroadcastClient', 'get_broadcast_client'
]