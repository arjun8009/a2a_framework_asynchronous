from a2a_framework.utils.llms import *
from a2a_framework.a2a.AgentCard import AgentCard
from a2a_framework.a2a.Artifact import Artifact
from pydantic import BaseModel
import logging
import uuid
from a2a_framework.a2a.Task import Task
from a2a_framework.a2a.Messages import Messages
from a2a_framework.a2a.AgentState import AgentState
from a2a_framework.a2a.TaskStatus import TaskStatus

class Agent():

    def __init__(self, agent_details:AgentCard, model_name:str, reasoning:bool, base_url:str, schema:BaseModel=None, 
                  tool_definitions:list=None, additional_args:dict=None, 
                 artifacts_req:Artifact = None, system_instruction:str=None, 
                logger=None):
        
        ''' Default agent is defined here. It contains an identity of the agent and assigns an llm to control the agent
        args:
            1. agent_identity : An identification of the agent of type AgentCard
            2. model_name : name of the llm agent will use
            3. schema : A pydantic BaseModel type schema
            5. tool_definitions : A list of tool defintions
            6. additional_args : A dictionary of additional args to disable parallel tool calls 
            7. available_agents : A list of available agents for send_messages 
            8. artifacts_req : A list of data artifacts required
        outputs : 
            1. llm output can be schema, string or tool evalutation results of type string

            
        We are still working on returning raw data. Will be implemented using Artifacts'''

        self.agent_identity = agent_details
        self.model_name = model_name
        self.base_url = base_url
        self.reasoning = reasoning
        self.tool_definitions = tool_definitions
        self.schema = schema
        self.additional_args = additional_args
        self.artifacts_req = artifacts_req
        self.system_instruction = system_instruction
        self.logger_path = logger
        self.logger = logging.getLogger(logger)
    
    def run_agent(self,messages,session_id,parent_id=None):

        '''This actually runs the agent and gives all the outputs including the tools
        
        args:
            1. messages : A list of messages openai style. We dont have the messages in the init bec we want to blank initialise an agent and run it whenever we want
            2. session_id : This is a unique string id it is set up as (agent_calling_this_agent)_(unique_id). We have this because if A1 calls A2 twice with 2 different tasks, 
            the context will be confusing which task is being solved. So Even for mutiple interactions of A1 with A2 there will be a different session_id. 
            3. Parent_id : This is the task parent id. If Task T0 for any agent wants to talk to another agent then a new task Ti will be created and will have a parent_id
        outputs:
            1. output : ouptut of the llm can be string, schema and in a later stage data artifacts'''

        # Check and insert system instruction 
        if self.system_instruction and messages[0]["role"]!="system":
            messages.insert(0,{"role":"system","content":self.system_instruction})

        # This is never called. I am keeping it here for the time being this is old code. But does not break the system
        if self.artifacts_req:
            messages[-1]["content"] = messages[-1]["content"] + f"\n The data artifacts provided to you are : {[i.name for i in self.artifacts_req]} with descriptions {[i.description for i in self.artifacts_req]}"


        self.logger.info(f"Messages sent : {messages}")

        # We run the llm with base_url, messages, tool_definitions, reasoning_params, additional_args indicating if parallet_tool_calls is allowed or not and custom temperature values
        # the provided schema and logger
        output = run_llm(model_name=self.model_name,url=self.base_url,messages=messages,schema=self.schema, reasoning=self.reasoning,tools=self.tool_definitions, logger=self.logger_path)
        
        artifacts = None
        attempts = 0
        # This is just the last message in the interaction. Not the initial query. It is not possible to index the initial query so if need be then ask the llm to provide it as a parameter in a tool
        query = messages[-1]["content"]

        # Agent Loop
        if hasattr(output,"output"):
            
            while(output.output[-1].type=="function_call" and attempts < 50):

                # GPT 5 and reasoning models require reasoning Trace. In a next update will make this line more generalizable to all reasoning models
                if self.model_name.startswith("gpt-5") or self.model_name.startswith("o"):
                    messages.extend([i for i in output.output if i.type=="reasoning"])

                # Get the list of tool calls
                fn_calls = [i for i in output.output if i.type=="function_call"]

                # running of tools without multithreading because redis will handle that. 
                status = self.run_tools(messages,fn_calls,query,parent_id,session_id)

                # Waiting means that some other tasks have been spawned. Most probably a tool call or an agent interaction. Child tasks are just the task_ids of the spawned tasks
                if status["status"] == TaskStatus.WAITING_ON_CHILDREN:
                    return {"status":TaskStatus.WAITING_ON_CHILDREN, "result":None,"child_tasks":status["child_tasks"]} 
                
                attempts = attempts + 1

                # Rerun incase the tool call finishes instantly
                output = run_llm(model_name=self.model_name,url=self.base_url,messages=messages,schema=self.schema, tools=self.tool_definitions, reasoning=self.reasoning, logger=self.logger_path)
        self.logger.info(f"Final output of the agent is : {output}")

        # Mostly here run_llm uses responses.parse. It can handle both  structured and non structured parsing. We check for output text which is the final_output 
        # Then we check if it has a parseable schema, if yes we just add it to a json key
        if hasattr(output,"output_text"):
            AgentState.save(self.agent_identity.agent_name,session_id,[{"role":"assistant","content":output.output_text}],self.logger_path)
            if hasattr(output,"output_parsed") and output.output_parsed and isinstance(output.output_parsed,BaseModel):
                return {"status":TaskStatus.DONE, "result":output.output_text, "schema":output.output_parsed}
            else:
                return {"status":TaskStatus.DONE, "result":output.output_text}


    def create_parent_and_child_task(self,agent_name,tool_name, args, conversation_id,parent_id,sesion_id):

        '''
        This function spawns child tasks for tool calls and agent to agent interactions.
        args:
            1. agent_name : str : Name of the owner agent of the task which is the calling agent. Even in the case of sending message to another agent.
            the calling agent is the owner of the task
            2. args : dict = A dictionary of the tool arguments for the tool_call
            3 conversation_id : str : A unique id containing a global conversation between AN and AM. Conversation is different from agent state. Agent state contains the tool
            calls and responses and everything else. Conversation just contains who asked what to whom and what was the reply. Keeping these 2 spearate helps to summarise the
            context.
            4. parent_id : str The task id of the calling task which is spawning the next task
            5. session_id : str : The id of the session as discussed above
        output:
        task_id : list[str] = A list of spwaned task ids. Spawned but not running
        '''

        self.logger.info(f"Create Parent and Child task with parent id {parent_id}")
        task = Task.create_task(
                            agent_name=agent_name,
                            messages=conversation_id,
                            agentstate=self.agent_identity.agent_name,
                            tool_function=tool_name,
                            tool_args=args,
                            session_id=sesion_id,
                            logger_path=self.logger_path,
                             )
        if parent_id:
            task.parent_id = parent_id
            task.save()
        else:
            task.save()
        return task.task_id

    def check_multiple_similar_targets(self, target,  fn_calls):
        '''
        This is used in specific case. If A1 makes a parallel tool call to A2 twice with 2 queries Q1 and Q2. We need to check it to add a filter.
        The reason is, assume in the global conversation context speaker is A1 and it has 2 queries Q1 and Q2. Now when A2 is called and is run with 
        this context there will be 2 processes running A2 because parallel_tool_calls. So A2 will be running both the queries twice. Now we need a filter
        Something to tell that if A2 is run then filter messages for Q1 and filter messages for Q2. To do all this extra work we need to be sure that A2 is
        called twice. Hence we make the check here

        args :
        target : str = Name of the agent that will be called with multiple tasks
        fn_calls : list[dict] = A list of the tool_calls made by the agent

        output:
        output : bool = True if parallel tool calls are made to the same agent multiple times
        '''

        for call in fn_calls:
            if call.name == "send_message":
                args = json.loads(call.arguments)
                if args["target"] == target:
                    return True
        return False
        
    def run_tools(self,messages,fn_calls,query,parent_id,session_id):

        '''run tools will actually run the llm tool calls. However this functionality is limited to openai tool calling. Will later implement open source tool calling here and
        in run_llms
        
        args:
            1. messages : A list of messages to update
            2. fn_calls : A list of function_call outputs
            3. query: The intial query and later the last message in the list before the agent response
            4. parent_id : str The task id of the calling task which is spawning the next task
            5. session_id : str : The id of the session as discussed above
        
        output:
            status : dict = Always a wait signal is emmited to run the new spawned tasks
        '''
        tasks = []
        for call in fn_calls:

            # we append the calls and load the arguments of the function call

            messages.append(call)
            args = json.loads(call.arguments)
            tool_names = [i["name"] for i in self.tool_definitions]
            
            if call.name in tool_names:

                # We add the query , logger_path, source agent to the args of all the tool_calls in case it is required. Although in later updates query can be the initial_query
                # Will make some changes for that later. But a way around is make an argument called query in your tool and let the llm provide the query if it is very much 
                # required in the tool call
                args["query"] = query
                args["logger_path"] = self.logger_path
                args["source"] = self.agent_identity.agent_name

                if call.name == "send_message":
                    # This is to handle the case where multiple agents are called with the same target. In that case we will create a new conversation id for each call
                    a,b = sorted([args["source"],args["target"]])
                    conversation_id = a + "^" + b
                    if self.check_multiple_similar_targets(args["target"], fn_calls):
                        # As mentioned above we need to filter messages. So in A1->[A2,A2] situation we will filter the context using an id to allot each task to each of the same agent
                        filter_id = str(uuid.uuid4())
                    else:
                        filter_id = "null"
                    conversation = [{"speaker":args["source"],"content":args["task_description"], "filter_messages":filter_id}]

                    # We add it to the tool_args. It is mostly handled internally
                    args["filter_messages"] = filter_id
                    
                    # save the messages to the message store or update existing messages and then save
                    Messages.save(conversation_id,conversation,self.logger_path)
                    args["conversation_id"] = conversation_id
                    session_id_send_message = args["source"] + "_" + str(uuid.uuid4())
                    args["session_id"] = session_id_send_message

                    # check comment of this function to understand how it works
                    child_task_id = self.create_parent_and_child_task(self.agent_identity.agent_name, call.name, args, conversation_id, parent_id,session_id)
                else:
                    # We also provide the session id when we need to load_skills to create a unique skill key. This is again required if 
                    # A1 -> [A2, A2] then suppose A2 want to load some skills which are different for different tasks so this helps
                    if call.name == "load_skill":
                        args["session_id"] = session_id
                    child_task_id = self.create_parent_and_child_task(self.agent_identity.agent_name, call.name, args, "null", parent_id,session_id)

                tasks.append(child_task_id)
                # Here we always tell the agent to wait. We do this because assume the tool_responses are out of order and some llm expects them to be in order. So we respond to wait and then we add the results in order later
                messages.append({"type":"function_call_output", "call_id":call.call_id,"output":"The task has been delivered. It will take a few minutes to respond. Please wait.\
                                 If you have made multiple calls then outputs will come one at a time. Do not make the request again"})

                # We save the Agent State and return the id's of the pending task.
                AgentState.save(self.agent_identity.agent_name,session_id,messages,self.logger_path,replace=True)

        return {"status":TaskStatus.WAITING_ON_CHILDREN, "messages":messages, "child_tasks":tasks}
            

