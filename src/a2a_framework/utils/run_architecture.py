from a2a_framework.utils.registry import registry
import uuid
from a2a_framework.a2a.Messages import Messages
from a2a_framework.a2a.Task import Task
from a2a_framework.a2a.TaskStatus import TaskStatus
from a2a_framework.a2a.Routing import Router
from a2a_framework.a2a.RouterUtils import RouterOutput
from time import time
import logging
from pathlib import Path
import json
from a2a_framework.a2a.redis_client import redis_client

HUMAN_PENDING_TASK = Path.cwd()/"pending_human_task"/"taskid.joblib"

def run_routing_architecture(query, config, config_path, logger_path):

    logger = logging.getLogger(logger_path)
    route = config["path_config"]["route"]
    available_agents = [i["agent_name"] for i in config["agent_config"]]
    logger.info(f"Creating Router with router id {str(uuid.uuid4())}")

    output_id = str(uuid.uuid4()) + "_" +  str(time())
    route_output = RouterOutput(
            route_output_id= output_id ,
            agent_name="human_agent",
            output=query,
            schema={},
            logger_path=logger_path,
            raw_output=query,
            artifacts =[]
        )
    
    route = Router.create_route(route_id=str(uuid.uuid4()),
                                config=config_path,
                                available_agents=available_agents,
                                initial_query=query,
                                logger_path=logger_path,
                                route=route)
    
    route.router_outputs.append(output_id)
    route.save()
    route_output.save()
    
    route.run_route("human_agent",start=True)

def run_agent_architecture(query,entry_agent_name,logger_path):
    
    '''Function to run the agent architecture
    args:
        1. query : The query to run the agent architecture 
        2. entry_agent_name : The name of the entry agent
    output:
        The output of the agent architecture
    '''
    logger = logging.getLogger(logger_path)
    args = {"query":query}
    args["source"] = "human_agent"
    args["target"] = entry_agent_name
    args["task_description"] = query
    args["logger_path"] = logger_path
    session_id = "human_agent_" + str(uuid.uuid4())
    args["session_id"] = session_id
    agent = registry[entry_agent_name]
    conversation = [{"speaker":"human_agent","content":query, "filter_messages":"null"}]
    a,b = sorted(["human_agent",agent.agent_identity.agent_name])
    conversation_id = a + "^" + b
    Messages.save(conversation_id,conversation,logger_path)
    logger.info(f"File Path returned by messages is {conversation_id}")
    args["conversation_id"] = conversation_id
    
    logger.info(f"""Creating Root Task with the following args {agent.agent_identity.agent_name},
                conversation id {conversation_id}, agentSate = {agent.agent_identity.agent_name}
                tool function : send_message, tool_args = {args}""")
    task = Task.create_task(
                                agent_name="human_agent",
                                messages=conversation_id,
                                agentstate="human_agent",
                                tool_function="send_message",
                                tool_args=args,
                                session_id=session_id,
                                logger_path=logger_path

                                 )
    task.run_task()

def run_architecture(query,entry_agent_name,logger_path):
    from a2a_framework.utils.registry import registry
    config_path = registry["config"]
    config = Path(config_path).resolve()
    with open(config,"rb") as file:
        config_dict = json.load(file)
    if config_dict["path_config"]["type_of_architecture"] == "deterministic" or config_dict["path_config"]["type_of_architecture"] == "hybrid":
        run_routing_architecture(query,config_dict,config,logger_path)
    else:
        run_agent_architecture(query,entry_agent_name,logger_path)


def run_human_reply(reply:str, task_id : str, approve:bool= True):


    task = Task.load(task_id)
    task.tool_args["human_reply"] = True
    human_reply = json.dumps({"approve":approve, "reply":reply})
    task.result = {"status": TaskStatus.DONE, "result": human_reply, "raw_output":human_reply}
    task.save()
    task.run_task()


