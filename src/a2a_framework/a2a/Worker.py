import argparse
import logging
import time
import redis
from a2a_framework.a2a.redis_client import redis_client as r
from a2a_framework.a2a.Task import Task
from a2a_framework.utils.initialize_os_agents import OSAgentsInitializer



def initialise_worker(config,filename, dir):
    logger_path = OSAgentsInitializer(config=config, logging_filename=filename,diff_dir=dir,write_mode="a").initialize_all_agents()
    
    logger = logging.getLogger(logger_path)
    logger.info("Initialised config and registry in worker")
    return logger



def tool_worker_loop(logger,worker="1"):

    logger.info(f"Starting tool worker loop for worker {worker}")
    while True:
        try:
            result = r.blpop("queue:tool_execution", timeout=5)
            if result is None:
                continue

            _, task_id = result
            logger.info(f"Worker {worker} executing task {task_id}")
            Task.load(task_id).execute()
    
        except (redis.exceptions.ConnectionError, redis.exceptions.TimeoutError) as e:
            logger.info(f"Redis hiccup, retrying: {e}")
            time.sleep(1)

        except Exception as e:
            logger.error(e,exc_info=True)



if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--log-file", required=True)
    parser.add_argument("--dir", required=True)
    parser.add_argument("--worker", required=False)

    args = parser.parse_args()
    logger = initialise_worker(args.config,args.log_file,args.dir)
    if hasattr(args,"worker") and args.worker:
        tool_worker_loop(logger,worker=args.worker)
    else:
        tool_worker_loop(logger)