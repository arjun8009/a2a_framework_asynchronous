from a2a_framework.a2a.RouterUtils import RouterStatus
import requests
from a2a_framework.utils.static import *
from a2a_framework.a2a.redis_client import redis_client
import logging


def notify_user_and_write_failure(output):
    """Persist a failed output and notify the user.

    Args:
        output: Failure value to write to the failure output file.

    Output:
        RouterStatus.END.
    """
    with open(OUTPUT_PATH["failure"],"w",encoding="utf-8") as file:
        file.write(str(output))
        if OUTPUT_PATH.get("notify_url_failure"):
            requests.post(OUTPUT_PATH["notify_url_failure"], data="Agent Failed Execution check failure.md".encode(encoding='utf-8'))
    return RouterStatus.END

def write_intermediate_output(output):
    """Append an intermediate output to the configured output file.

    Args:
        output: Intermediate value to persist.

    Output:
        None.
    """
    with open(OUTPUT_PATH["intermediate"],"a",encoding="utf-8") as file:
        file.write(str(output) + "\n \n")
        if OUTPUT_PATH.get("notify_url_success_or_intermediate"):
            requests.post(OUTPUT_PATH["notify_url_success_or_intermediate"], data=f"Output : {output}".encode(encoding='utf-8'))
    file.close()


def notify_user_and_write_success(output,logger_path):
    """Persist a successful output when all tasks have completed and notify the user.

    Args:
        output: Successful value to persist.
        logger_path: Logger name used for progress reporting.

    Output:
        RouterStatus.END when no tasks remain; otherwise RouterStatus.RUNNING.
    """
    # Here we check if there are any pending tasks. We do this because if there are 2 tasks or 2 branches of agents running simultaneously we need to wait for the other 
    # branch to end. We use ntfy here but will replace later with user functions
    logger = logging.getLogger(logger_path)
    remaining = redis_client.decr("counter:tasks_remaining")
    logger.info(f"Remaining Tasks in queue : {remaining}")
    if remaining <= 0:
        with open(OUTPUT_PATH["success"],"a",encoding="utf-8") as file:
            file.write(str(output) + "\n \n")
        if OUTPUT_PATH.get("notify_url_success_or_intermediate"):
            requests.post(OUTPUT_PATH.get("notify_url_success_or_intermediate"), data="Agent Execution Success check success.md".encode(encoding='utf-8'))
        return RouterStatus.END
    else:
        write_intermediate_output(output)
        return RouterStatus.RUNNING
