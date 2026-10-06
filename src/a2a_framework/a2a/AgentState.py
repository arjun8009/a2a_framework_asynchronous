import time
import json
from a2a_framework.a2a.redis_client import redis_client
from dataclasses import dataclass,field
import logging

@dataclass
class AgentState:

    '''
    This Agentstate class stores the internal context of the agent itself. That is the message history containing the system instructions, query, tool calls and responses.
    It grows as the agent interacts and is organized as redis hashes. Whenever Agent say A1 runs a hash key called A1_<agent name which invoked A1>_uuid is made.
    We do this because if N agents parallely interact with A1 there will be simultaneous N interactions which can cause concurrency issues and also confuse the llm.
    Hence when another agent say An calls A1 we make a key An_uuid and add it to A1 like A1_An_uuid. If An interacts again then we make A1_An_uuid_1. 

    For questions related to what if An refers to some old context and calls A1, then the conversation history between A1 and An are always added. So state becomes
    A1-An conversation + A1 state. Now conversations are global and contain speaker A1 response An and speaker An response A1. So a global context is always given. 
    We do not use the agent state much except for making the LLM respond to tool calls. 

    How it actually happens is 

    An (agent n) calls A1 conversation A1^An is created with speaker A1 and query Q1, AgentState A1_An_uuid is also made. AgentState gets updated with tool_calls and tool_responses,
    then final answer is added to A1_An_uuid and A1^An conversation with speaker An. Now An calls A1 again so A1^An conversation is added  to the context for past interactions and
    AgentState is now A1_An_uuid_1 (new blank agentstate with updated past conversations)    
    '''
    id: str
    messages : dict[list[dict]]
    updated_time : str = field(default_factory=str)

    @classmethod
    def save(cls,key:str,perspective:str,message:list[dict],logger_path:str, replace:bool=False):
        
        logger = logging.getLogger(logger_path)
        logger.info(f"Saving state {message} with key {key} and perspective {perspective} ")
        if not message:
            return
        # We make a key with the agent perspective and the agent name
        key = f"state:{key}:perspective:{perspective}"
        # Then simply push it to redis. This is atomic so no two processes can access it at the same time and cause concurrency issues.
        serialized = [json.dumps(e)  if isinstance(e,dict) else e.model_dump_json() for e in message]
        if replace:
            with redis_client.pipeline() as pipe:
                pipe.multi()
                pipe.delete(key)
                if serialized:
                    pipe.rpush(key, *serialized)
                pipe.execute()
        else:
            redis_client.rpush(key, *serialized)
        

    @classmethod
    def load_state(cls,id: str, perspective:str,logger_path):
        logger = logging.getLogger(logger_path)
        logger.info(f"Loading State with key {id} and perspective {perspective}")
        # Loading is simple when provided with the key, it loads all the json entry in sequence. It is done by redis see redis documentation for more info
        entries_key = f"state:{id}:perspective:{perspective}"

        raw_entries = redis_client.lrange(entries_key, 0, -1)
        entries = [json.loads(e) for e in raw_entries]


        return cls(
            id=id,
            messages=entries,
            updated_time = str(time.time())
        )