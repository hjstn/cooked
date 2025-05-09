import pika
from pika.adapters.blocking_connection import BlockingChannel

class CookedMQ:
    params: pika.ConnectionParameters
    leader: bool = False

    connection: pika.BlockingConnection = None

    def __init__(self, params: pika.ConnectionParameters, leader=False):
        self.params = params
        self.leader = leader

        self.connection = pika.BlockingConnection(params)
    
    def __del__(self):
        if self.connection:
            self.connection.close()

    def _channel(self, queue: str) -> BlockingChannel:
        channel = self.connection.channel()
        channel.queue_declare(queue=queue)

        return channel