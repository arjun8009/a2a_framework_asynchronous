import redis

# Just initializing the redis client here. May need to add a remote host too later
redis_client = redis.Redis(
    host="localhost",
    port=6379,
    socket_keepalive=True,
    decode_responses=True,
    retry_on_error=[redis.exceptions.ConnectionError, redis.exceptions.TimeoutError],

)