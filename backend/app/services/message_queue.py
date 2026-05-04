import aio_pika
from app.core.config import settings
import logging
import json
from typing import Optional, Callable
import asyncio

logger = logging.getLogger(__name__)


class MessageQueueService:
    def __init__(self):
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.connected = False
    
    async def connect(self):
        """Initialize RabbitMQ connection"""
        try:
            self.connection = await aio_pika.connect_robust(
                settings.RABBITMQ_URI,
                client_properties={"connection_name": "knowledge_platform"}
            )
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=10)
            self.connected = True
            logger.info(f"Connected to RabbitMQ at {settings.RABBITMQ_URI}")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise
    
    async def close(self):
        """Close RabbitMQ connection"""
        if self.connection:
            await self.connection.close()
            self.connected = False
            logger.info("RabbitMQ connection closed")
    
    async def declare_queue(self, queue_name: str, durable: bool = True):
        """Declare a queue"""
        if not self.connected:
            raise RuntimeError("RabbitMQ not connected")
        
        queue = await self.channel.declare_queue(queue_name, durable=durable)
        logger.info(f"Queue declared: {queue_name}")
        return queue
    
    async def publish_message(self, queue_name: str, message: dict, routing_key: str = ""):
        """Publish a message to queue"""
        if not self.connected:
            raise RuntimeError("RabbitMQ not connected")
        
        queue = await self.declare_queue(queue_name)
        
        body = json.dumps(message).encode()
        msg = aio_pika.Message(
            body=body,
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            content_type="application/json"
        )
        
        await self.channel.default_exchange.publish(msg, routing_key=routing_key or queue_name)
        logger.debug(f"Message published to {queue_name}: {message}")
    
    async def consume_messages(self, queue_name: str, callback: Callable, auto_ack: bool = False):
        """Consume messages from queue"""
        if not self.connected:
            raise RuntimeError("RabbitMQ not connected")
        
        queue = await self.declare_queue(queue_name)
        
        async def process_message(message: aio_pika.IncomingMessage):
            async with message.process():
                try:
                    body = json.loads(message.body.decode())
                    await callback(body)
                    logger.debug(f"Processed message from {queue_name}: {body}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    if not auto_ack:
                        await message.nack(requeue=True)
        
        await queue.consume(process_message)
        logger.info(f"Consuming messages from {queue_name}")


# Global message queue service instance
mq_service = MessageQueueService()