import logging
import asyncclick as click
import asyncio
import aio_pika


@click.command()
@click.option(
    "-b",
    "--broker",
    type=click.STRING,
    envvar="BROKER",
    default="amqp://guest:guest@rabbitmq/",
    show_default=True,
    required=True,
    help="RabbitMQ message broker connection string",
)
@click.option(
    "-e",
    "--exchange",
    type=click.STRING,
    envvar="Exchange",
    required=True,
    help="Service exchange name.",
)
@click.option(
    "-p",
    "--pattern",
    type=click.STRING,
    default="#",
    required=True,
    help="Routing key pattern.",
)
@click.option(
    "-h",
    "--hash-header",
    type=click.STRING,
    default="org",
    show_default=True,
    required=True,
)
async def consumer(broker, exchange, pattern, hash_header):
    connection = await aio_pika.connect_robust(broker)
    async with connection:
        channel = await connection.channel()

        # Declare source exchange.
        exchange = await channel.declare_exchange(exchange, aio_pika.ExchangeType.TOPIC)

        # Declare consistent hash exchange
        ch_exchange = await channel.declare_exchange(
            f"{exchange}_ch",
            aio_pika.ExchangeType.X_CONSISTENT_HASH,
            arguments={"hash-header": hash_header},
        )
        queue = await channel.declare_queue(auto_delete=True)
        await queue.bind(ch_exchange, routing_key="1")
        await ch_exchange.bind(exchange, routing_key=pattern)

        # Will take no more than 10 messages in advance
        await channel.set_qos(prefetch_count=10)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                async with message.process():
                    print(message.body)

                    if queue.name in message.body.decode():
                        break


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    consumer()