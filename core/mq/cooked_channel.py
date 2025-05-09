from typing import Callable, Generic, TypeVar

import zlib
import pickle

from pika import DeliveryMode
from pika.spec import BasicProperties
from pika.adapters.blocking_connection import BlockingChannel

from lib.mq.cooked_mq import CookedMQ

Task = TypeVar('Task')

CookedConsumeAckFn = Callable[[None], None]
CookedConsumeCallbackFn = Callable[[Task, CookedConsumeAckFn, CookedConsumeAckFn], None]

class CookedChannel(Generic[Task]):
    mq: CookedMQ
    queue: str
    fanout: bool
    channel: BlockingChannel

    def __init__(self, mq: CookedMQ, queue: str, purge: bool = False, fanout: bool = False):
        self.mq = mq
        self.queue = queue
        self.purge = purge
        self.fanout = fanout

        self.channel = mq._channel(queue)

        if mq.leader and purge:
            # Producer only
            self.channel.queue_purge(queue=queue)
        else:
            # Consumer only
            self.channel.basic_qos(prefetch_count=1)

    def send(self, body: Task):
        data = zlib.compress(pickle.dumps(body))

        self.channel.basic_publish(
            exchange=('' if not self.fanout else 'amq.fanout'),
            routing_key=self.queue,
            body=data,
            properties=BasicProperties(
                delivery_mode=DeliveryMode.Persistent
            ),
            mandatory=True
        )

    def consume(self):
        for method, properties, body in self.channel.consume(queue=self.queue, auto_ack=False):
            task: Task = pickle.loads(zlib.decompress(body))

            ack = lambda: self.channel.basic_ack(delivery_tag=method.delivery_tag)
            nack = lambda: self.channel.basic_nack(delivery_tag=method.delivery_tag)

            yield task, ack, nack
        
        self.channel.cancel()
