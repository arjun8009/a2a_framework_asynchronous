import json
from a2a_framework.a2a.redis_client import redis_client
from dataclasses import dataclass
import logging

@dataclass
class Messages():
    '''Messages as described earlier in AgentState is a global conversation / context between two agents stored as 
    {"speaker":"agent", "content": "content"}. Between 2 agents speaker is the person requesting something or answering a previous question
    This is mostly done to compress the agent's own internal monologue with queries, tools and tool outputs. if an agent let say A1 is invoked
    more than once, in the second time its own context is replaced by the messages followed by the state.
    
    id : str =  The conversation id stored as A1^A2
    messages : list[dict] = A list of messages'''
    messages : list[dict]
    id : str


    @classmethod
    def load(cls,key:str,logger_path:str):
        logger = logging.getLogger(logger_path)
        # We load messages just like states. we get the key and get all entries associated with the key. This is again atomic
        # Becasue a key is very simple. We can reuse this accross user queries. Thus persisting the context accross conversations
        raw_entries = redis_client.lrange(key, 0, -1)
        entries = [json.loads(e) for e in raw_entries]
        logger.info(f"Loading messages {entries} with key : {key}")
        return cls(
            id=key,
            messages=entries,
        )
    
    @classmethod
    def save(cls,key:str,message:list[dict],logger_path:str):
        logger = logging.getLogger(logger_path)
        logger.info(f"Saving messages : {message} with key {key}")
        if not message:
            return
        # We save messages just like states. we get the key and just do a rpush. This is again atomic
        key = f"{key}"
        serialized = [json.dumps(e) for e in message]
        redis_client.rpush(key, *serialized)

    
    def render_for(self, self_id: str, filter_messages:str):
        '''Render the speaker-tagged log into role-tagged messages
        from the point of view of `self_id`.

        self_id speaks -> "assistant"
        anyone else     -> "user"
        '''
        rendered = []
        for m in self.messages:
            role = "assistant" if m["speaker"] == self_id else "user"
            content = m["content"]
            rendered.append({"role": role, "content": content, "filter_messages": m.get("filter_messages", "null")})
        
        if filter_messages != "null" and filter_messages != None:
            rendered = [m for m in rendered if m.get("filter_messages", "null") == filter_messages]

        rendered = [{"role": m["role"], "content": m["content"]} for m in rendered]

        return rendered