#!/bin/bash

cleanup() {
    echo "Shutting down RabbitMQ..."
    kill $RABBITMQ_PID
    exit 0
}

trap cleanup SIGINT

CONF_ENV_FILE="/opt/homebrew/etc/rabbitmq/rabbitmq-env.conf" /opt/homebrew/opt/rabbitmq/sbin/rabbitmq-server &
RABBITMQ_PID=$!

sleep 5

/opt/homebrew/sbin/rabbitmqctl enable_feature_flag all

wait $RABBITMQ_PID