import logging
from a2a_framework.a2a.TaskStatus import TaskStatus
from a2a_framework.utils.static import *
import os
import json

def wrap_tool_output(tool_function, tool_args, logger_path):
    """
    Wraps a tool function to handle exceptions and return a standardized output.
    Expects tools to return two ouputs : (output,artifacts)
    output : str
    artifacts : list[obj]
    """

    from a2a_framework.utils.registry import registry as TOOL_REGISTRY

    logger = logging.getLogger(logger_path)
    logger.info(f"current state of registry {TOOL_REGISTRY.keys()}")
    tool_fn = TOOL_REGISTRY.get(tool_function)
    if tool_fn is None:
        raise ValueError(f"Unknown tool: {tool_function}")
    else:
        result = None
        try:
            if tool_function == "send_message" and tool_args["target"] == "human_agent":
                 return {"status":TaskStatus.WAITING_ON_HUMAN,"result":tool_args["task_description"] }

            tool_result = tool_fn(**tool_args)

            output = tool_result.output
            artifacts = tool_result.artifacts

            logger.info(f"Tool {tool_function} executed here is the output {output} with pid {os.getpid()} ")

            result_on_success = f""" Tool {tool_function} executed_successfully with args source : {tool_args["source"]} target:{tool_args["target"]} task_description {tool_args["task_description"]}."""  if tool_function =="send_message" else f""" Tool {tool_function} executed_successfully with args {tool_args}""" 

            logger.info(f"Tool {tool_function} executed here is the output {output} with pid {os.getpid()} ")

            if isinstance(output,dict) and  output.get("status",None) and output["status"] == TaskStatus.WAITING_ON_CHILDREN:
                    return {"status": TaskStatus.WAITING_ON_CHILDREN, "result": None, "child_tasks":output["child_tasks"]}
            
            elif artifacts is not None and isinstance(artifacts,list) and len(artifacts) > 0:
                result = result_on_success +   f" Output :{output} .Artifacts generated: {[artifact.name for artifact in artifacts]} and descriptions {[artifact.description for artifact in artifacts]}"
                if isinstance(output,dict) and output.get("schema",None):
                    return {"status": TaskStatus.DONE, "result": result, "schema":output["schema"], "raw_output":json.dumps(output["result"]), "artifacts":[artifact.name for artifact in artifacts]}
                else:
                    return {"status": TaskStatus.DONE, "result": result, "raw_output":json.dumps(output)}
            else:
                result = result_on_success + f"Output: {output}"
                if isinstance(output,dict) and output.get("schema",None):
                    return {"status": TaskStatus.DONE, "result": result, "schema":output["schema"], "raw_output":json.dumps(output["result"])}
                else:
                    return {"status": TaskStatus.DONE, "result": result, "raw_output":json.dumps(output)}
        
        except Exception as e:
            logger.error("ERROR IN TOOL WRAPPER EXECUTION", exc_info=True)
            return {"status": TaskStatus.FAILED, "result": str(e)}


def wrap_condition_function(condition_name:str, available_outputs:list[object],  logger_path : str):

    from a2a_framework.utils.registry import registry as TOOL_REGISTRY
    logger = logging.getLogger(logger_path)
    logger.info(f"Executing conditional routing : {condition_name} with available_outputs {available_outputs}")
    args = {}
    args["available_outputs"] = available_outputs
    condition_func = TOOL_REGISTRY.get(condition_name,None)
    if condition_func:
        # assume output will give the agent name
        output = TOOL_REGISTRY[condition_name](**args)
    else:
        logger.error(f"No condition named {condition_name} found",exc_info=True)
        output = "END"
    return output


def wrap_output_processing_function(agent_name : str, function_name : str, available_outputs : list[object] , logger_path : str):

    from a2a_framework.utils.registry import registry as TOOL_REGISTRY
    logger = logging.getLogger(logger_path)
    logger.info(f"Deterministic Routing : Running ouput processing function {function_name} \
                with args {available_outputs} ")
    output_function = TOOL_REGISTRY.get(function_name,None)
    args = {"available_outputs":available_outputs, "agent_name":agent_name}
    if output_function:
        output = output_function(**args)
        return output
    else:
        logger.error(f"No function named {function_name} found in registry")
        return output