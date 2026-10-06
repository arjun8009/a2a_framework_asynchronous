from a2a_framework.a2a.Task import Task
from a2a_framework.a2a.Messages import Messages
import json
import uuid
import logging
from dataclasses import dataclass,field,asdict
from a2a_framework.a2a.redis_client import redis_client
from a2a_framework.utils.tool_wrapper import wrap_condition_function, wrap_output_processing_function
from a2a_framework.a2a.RouterUtils import RouterOutput, RouterStatus
from time import time

class Condition:
    '''
    Condition is a single function that defines which next agent should be invoked in a deterministic route based on the agent's output
    Basically if A1 runs and then using the output of A1 or other resources a function is invoked which will return the name of the next 
    agent.
    args:
        1. condition_id : str =  A unique id for a condition just a uuid
        2. condition_func : str = Name of the condition function
        3. available_outputs : list[objects] = A list of Router Outputs  
    '''
    condition_id : str
    condition_func : str
    available_outputs : list[object]
    logger_path : str

    def __init__(self, condition_id, condition_func, available_outputs, logger_path):
        self.condition_id = condition_id
        self.condition_func = condition_func
        self.available_outputs = available_outputs
        self.logger_path = logger_path

    def execute_condition(self):
        # takes the name of the condition function, available outputs and executes it. More about this in run_architecture.py
        next_agent = wrap_condition_function(self.condition_func, self.available_outputs,self.logger_path)
        return next_agent



    


@dataclass
class Router:
    '''
    This is the main component of router management system. It manages deterministic routing between agents 
    args
    1. router_id : str =  A unique uuid for the router
    2. config : str = A string name of the json containing the agentconfig
    3. initial_query : str = The first query sent by the agent incase it is required
    4. router_status : RouterStatus = Either Running or Ending. We did not include more because it includes parts of Task management system and it has more states
    5. router_tracked_tasks : list[str] = A list of tasks running on this router instance
    6. router_outputs : list[str] = A list of id's for RouterOutputs
    7. route : list[str] = A list of agents on this route. Updated as the route is completed
    '''
    route_id : str
    available_agents : list[str]
    initial_query : str
    config : str
    logger_path : str
    router_status : RouterStatus = RouterStatus.RUNNING
    router_tracked_branches : list[str] = field(default_factory=list)
    parent : str = field(default_factory=str)
    router_outputs : list[str] = field(default_factory=list)
    route : list[str] =  field(default_factory=list)
    completed_route : list[str] = field(default_factory=list)


    @classmethod
    def create_route(cls, route_id:str, config:str, available_agents:list[str], route:list[str], initial_query : str, logger_path : str,  parent:str = ""):
        '''
        create a determinsitic route by initializing the route. args are similar to the router output
        '''
        return cls(
            route_id = route_id,
            available_agents = available_agents,
            route = route,
            config=config,
            initial_query = initial_query,
            logger_path = logger_path,
            parent = parent
        )


    def _key(self) -> str:
        return f"route:{self.route_id}"
    
    def save(self):
        # Save the router similar to saving the tasks.
        logger = logging.getLogger(self.logger_path)
        data = asdict(self)
        logger.info(f"Saving route {data} ")
        data["config"] = str(self.config)
        data["route"] = json.dumps(self.route)
        data["router_tracked_branches"] = json.dumps(self.router_tracked_branches)
        data["router_outputs"] = json.dumps(self.router_outputs)
        data["logger_path"] = str(self.logger_path)
        data["available_agents"] = json.dumps(self.available_agents)
        data["completed_route"] = json.dumps(self.completed_route)
        redis_client.hset(self._key(), mapping=data)

    @classmethod
    def load(cls,route_id:str):
        # Load a task similar to task.load
        route_data = redis_client.hgetall(f"route:{route_id}")
        route = cls(
            route_id = route_data["route_id"],
            config = route_data["config"],
            route = json.loads(route_data["route"]),
            initial_query = route_data["initial_query"],
            logger_path = route_data["logger_path"],
            available_agents = json.loads(route_data["available_agents"]),
            router_tracked_branches = json.loads(route_data["router_tracked_branches"]),
            router_outputs = json.loads(route_data["router_outputs"]),
            parent = route_data["parent"],
            completed_route = json.loads(route_data["completed_route"])
        )
        return route

    def set_end(self):
        self.router_status = RouterStatus.END

    def load_config(self):
        with open(self.config,"rb") as file:
            agent_config = json.load(file)
        return agent_config["agent_config"]
    


    def create_route_task(self, query:str, src:str, target:str):
        '''
        For a specific route, the router creates a new task by sending a message from a source to a target. src is the human for the 1st agent in the route 
        args :
            query : str =  What query to execute
            src : str = The name of the source agent
            target : str = The name of the target agent
        output :
            task : Task = The created task
        '''
        logger = logging.getLogger(self.logger_path)
        args = {"query":query}
        args["source"] = src
        args["target"] = target
        args["task_description"] = query
        args["logger_path"] = self.logger_path
        args["session_id"] = self.route_id#src + "_" + str(uuid.uuid4())

        a,b = sorted([src,target])
        conversation_id = a + "^" + b

        if src == "human_agent" and len(self.completed_route )>=2 and self.completed_route[-2] == target  :
            # Because the source is the human_agent which means that the human feedback has already been added to the context. We do not want to overlap that hence a placeholder message here.
            # We still do create a conversation incase it is the first contact situation like human -> first agent in route.
            # This condition will trigger only when the source is human and it is not the first item in the route
            conversation = [{"speaker":src,"content":f"context is {query}. Using this context answer the user query just prior to this." , "filter_messages":"null"}]
            args["use_conversation_or_state"] = "state"
        else:
            conversation = [{"speaker":src,"content":query, "filter_messages":"null"}]

        Messages.save(conversation_id,conversation,self.logger_path)
        
        logger.info(f"File Path returned by messages is {conversation_id}")
        args["conversation_id"] = conversation_id
         
        
        logger.info(f"""Creating Root Task with the following args {src},
                    conversation id {conversation_id}, agentSate = {src}
                    tool function : send_message, tool_args = {args}""")
        task = Task.create_task(
                                    agent_name=src,
                                    messages=conversation_id,
                                    agentstate=src,
                                    tool_function="send_message",
                                    tool_args=args,
                                    logger_path=self.logger_path,
                                    router_id=self.route_id,
                                    session_id= self.route_id #src + "_" + str(uuid.uuid4())
                                )
        return task
        
    """def generate_start_task(self):
        ''' This function executes the router's first agent in the route'''
        logger = logging.getLogger(self.logger_path)
        logger.info(f"Deterministic Routing : Current agent : human_agent Next agent : {self.route[0]}")
        current_agent = self.route[0]
        if isinstance(current_agent,str) and current_agent.startswith("loop"):
            self.parse_loop(current_agent,"human_agent")
            logger.info(f"The loop route has been updated and is now {self.route}")
            current_agent = self.route[0]
            
        if current_agent == "END":
            return RouterStatus.END
        agent_config = self.load_config()
        current_agent_config = [i for i in agent_config if i["agent_name"] == current_agent][0]
        available_outputs = RouterOutput.load_all()
        query = self.initial_query if not current_agent_config.get("query_processing", None) else wrap_output_processing_function(current_agent_config["agent_name"],current_agent_config["query_processing"],available_outputs,self.logger_path)
        task = self.create_route_task(query,"human_agent",current_agent)
        self.completed_route.append(self.route.pop(0))
        self.save()
        return [task] """



    def get_next_from_condition(self,next:str):

        '''
        This function provides the next agent from a condition. Given the name of the condition it loads the 
        '''

        available_outputs = [RouterOutput.load(i) for i in self.router_outputs]
        condition = Condition(
                        condition_id=str(uuid.uuid4()),
                        condition_func=next,
                        available_outputs=available_outputs,
                        logger_path=self.logger_path
                )
        next_agent = condition.execute_condition()
        return next_agent

    def resolve_branches(self,next_agent:list[str]):

        '''This parses the route. So finds all the brances that will run parallely
        and finally stops at the merging agent which is next
        args :
            next_agent : list[str] = The initial detected branch
        output :
            all branches and the merge'''
        branches = [next_agent]
        remaining = []
        for next in self.route[self.route.index(next_agent) + 1 :]:

            if isinstance(next,list):
                branches.append(next)
            else:
                remaining.extend(self.route[self.route.index(next):])
                break
        return  branches + [remaining]


    def parse_loop(self, loop_condition:str, current_agent:str):
        '''
        This function is made to parse agent and human loops added in the route like loop(A1,A2,num_trials). The functionality is described below
        (A) human in loop without adding agent and human before
        Route : [A1,loop(A2,human), A3,END]
            -> [A1] -> [loop(A2,human),A3,END] -> loop detected default runs = 3 -> [A2,human,loop(A2,human,2),A3,END]
            -> [A2] -> [human,loop(A2,human,2),A3,END] -> [human] -> [loop(A2,human,2),A3,END] -> human_reject -> [A2,human,loop(A2,human,1),A3,END]
            -> [A2] -> [human,loop(A2,human,1),A3,END] -> [human] -> [loop(A2,human,1),A3,END] -> human_accept -> [A3] -> [END]
            OR
            ->[A2] -> [human,loop(A2,human,2),A3,END] -> [human] -> [loop(A2,human,2),A3,END] -> human_reject -> [loop(A2,human,1),A3,END]
            ->[A2] -> [human,loop(A2,human,1),A3,END] -> [human] -> [loop(A2,human,1),A3,END] -> human_reject -> [loop(A2,human,0),A3,END]
            -> [A2] -> [human,loop(A2,human,0),A3,END] -> [human] -> [loop(A2,human,0),A3,END] -> human_reject -> [A3] -> [END]

        (B) Agent loop 
        Route : [A1,loop(A2,A3),A4,END]
            -> [A1] -> [loop(A2,A3,3), A4,END] -> [A2,A3,loop(A2,A3,2),A4,END] -> [A2] -> [A3,loop(A2,A3,2),A4,END] -> [A3] -> [A2,A3,loop(A2,A3,1),A4,END]
            -> [A2] -> [A3,loop(A2,A3,1),A4,END] -> [A3] -> [A2,A3,loop(A2,A3,0),A4,END] -> [A2] -> [A3] -> [loop(A2,A3,0) no execution [A4] -> [END] 

        (C) human in the loop but apparently human first then agent (don't know why but need to handle)
        Route : [A1, loop(human,A2), A3, END)
        -> [A1] -> [human,A2,loop(human,A2,2),A3,END] -> [human] (no approval here) -> [A2,loop(human,A2),A3,END] -> [A2] -> [human,A2,loop(human,A2,1),A3,END]

        (D) Edge case [A1, human, loop(A2,human), END] = In this case if the human output contains approve=True it will skil the loop
            -> To solve this we need a way to understand if the loop is a new loop which is unexecuted. Hence we are now adding loop_rerun. So once a 
            loop(A1,human,3) is parsed from next time it will be loop_rerun(A1,human,2) hence we check if current_agent=="human" and loop_condition == "loop_rerun"
            so now even if in the first instance we have a human before the loop, we will not skip the loop but only skip if human is before a loop_rerun and human tells
            to skip
        '''
        logger = logging.getLogger(self.logger_path)
        try:
            logger.info(f"loop detected and thus parsing looping argument {loop_condition}")
            parse_args = loop_condition.split("(")[1].split(")")[0].split(",")
            logger.info(f"loop parsing led to these arguments {parse_args}")
            if len(parse_args) == 3:
                source_agent, target_agent, frequency = parse_args
                frequency = int(frequency)
            else:
                source_agent, target_agent = parse_args
                frequency = 3
            available_outputs = [RouterOutput.load(i) for i in self.router_outputs] # Maybe consider using the last human output in the branch rather than all outputs bec of multiple branching

            last_human_output = None

            if current_agent == "human_agent" and loop_condition.startswith("loop_rerun"):
                logger.info(f"Current agent is human so checking for approval or rejection in the loop")
                human_outputs = [i for i in available_outputs if i.agent_name.startswith("human_agent")]
                last_human_output = human_outputs[-1]

                logger.info(f"Loaded last human output {last_human_output}")
                
            logger.info("Resolving loop")
            if frequency == 0 or (last_human_output and json.loads(last_human_output.raw_output)["approve"]==True):
                self.completed_route.append(self.route.pop(0))
                self.save()
                return
            else:
                self.route.pop(0)
                self.route.insert(0,source_agent)
                self.route.insert(1,target_agent)
                self.route.insert(2, f"loop_rerun({source_agent},{target_agent},{frequency-1})")
                self.save()
                return
            

        except Exception as e:
            logger.error("Failure in parsing loop condition} ",exc_info=True)
            self.completed_route.append(self.route.pop(0))
            self.save()
            return 


    def get_next_from_config_or_conditions(self, current_agent:str):

        '''
        This functions uses the config to check if there is a next agent or
        if there is a condition. Then it executes the condition to get the next agent.
        '''

        next_agent = self.route[0]
        logger = logging.getLogger(self.logger_path)

        if next_agent.startswith("loop"):
            _ = self.parse_loop(next_agent,current_agent)
            logger.info(f"The loop route has been updated and is now {self.route}")
            next_agent = self.route[0]

        if isinstance(next_agent,list):
            # It is a list so a branch is detected, hence we need to find all the branches and also find the agent where the combination merges
            return self.resolve_branches(next_agent)
        else:
            return self.get_next_from_condition(next_agent) if self.check_for_agent_or_condition(next_agent) == "condition" else next_agent
        

    def check_for_agent_or_condition(self, agent_or_condition):
        if agent_or_condition in self.available_agents or agent_or_condition == "END":
            return "agent"
        else:
            return "condition"




    def generate_next_task(self, current_agent:str):
        ''' This is the main function to generate the next task for the Router
        args : 
            1. current_agent : str = Name of the current agent in the execution flow
        output :
            It finds the next agent in the route either by listing all the agents in the route or finding the next_agent based on condition
        '''

        logger = logging.getLogger(self.logger_path)
        # We load the agent config because it contains the route information

        # This is basically the function which decides if the next item in the route is a list of agents or conditions
        next_agents = self.get_next_from_config_or_conditions(current_agent)
        logger.info(f"Received next agents from config or conditions {next_agents}")
        agent_config = self.load_config()

        # if there are multiple next agents but only 1 is end the remove the end and create tasks for the other agents. If there is only 1 END then end the route
        if isinstance(next_agents,str) and next_agents == "END" :
            logger.info(f"No agent in next agent ending")
            self.router_status = RouterStatus.END
            self.completed_route.append("END")
            self.save()
            return RouterStatus.END
        # If there is only 1 agent then make the task for that 1 agent and run it
        elif isinstance(next_agents,str) and next_agents!="END" :
            logger.info(f"1 agent in next agent {next_agents}")
            next_agent_config = [i for i in agent_config if i["agent_name"]==next_agents][0]
            # We give all the router outputs in the router pool
            available_outputs = RouterOutput.load_all()
            # If the agent needs more context or needs  more query processing capabilities then we can execute the function
            
            task_query = available_outputs[-1].raw_output \
            if not next_agent_config.get("query_processing", None) \
            else wrap_output_processing_function(next_agent_config["agent_name"],next_agent_config["query_processing"],available_outputs,self.logger_path)

            task = self.create_route_task(task_query, current_agent, next_agents)
            self.completed_route.append(self.route.pop(0))
            self.save()
            return [task]
        else:
            # In case there are multiple agents we shift to a branch, where we create multiple routes for each branch. For each new route we create a task and then return those tasks
            logger.info(f"Branching detecting creating multiple routes and now taking from routing pool")
            tasks = []
            branches = next_agents[:-1]
            remaining = next_agents[-1]
            self.route = remaining
            self.save()
            for branch in branches:
                next_agent_config = [i for i in agent_config if i["agent_name"]==branch[0]][0]
                id = str(uuid.uuid4())
                available_outputs = RouterOutput.load_all()
                task_query = available_outputs[-1].raw_output if not next_agent_config.get("query_processing", None) else wrap_output_processing_function(next_agent_config["agent_name"],next_agent_config["query_processing"],available_outputs,self.logger_path)
                new_router = Router.create_route(
                    route_id=id,
                    available_agents=self.available_agents,
                    route=branch,
                    parent=self.route_id,
                    config=self.config,
                    initial_query=task_query,
                    logger_path=self.logger_path,
                )
                new_router.router_outputs = [i.route_output_id for i in available_outputs]
                new_router.save()
                self.router_tracked_branches.append(new_router.route_id)
                self.save()
                task = new_router.create_route_task(query=task_query, src=current_agent, target=new_router.route[0])
                new_router.completed_route.append(new_router.route.pop(0))
                new_router.save()
                tasks.append(task)
            return tasks

    def notify_main_branch(self):

        logger = logging.getLogger(self.logger_path)
        logger.info(f"Notifying main branch of completion with branch id {self.route_id}")
        while True:
            with redis_client.pipeline() as pipe:
                pipe.watch(f"route:{self.parent}")
                branches_json = pipe.hget(f"route:{self.parent}", "router_tracked_branches")
                branches = json.loads(branches_json) if branches_json else []
                if self.route_id in branches:
                    branches.remove(self.route_id)
                    logger.info(f"Branch {self.route_id} is completed and removed from parent {self.parent}")
                pipe.multi()
                pipe.hset(f"route:{self.parent}", "router_tracked_branches", json.dumps(branches))
                pipe.execute()
                break
        main_branch  = Router.load(f"{self.parent}")
        if len(main_branch.router_tracked_branches) == 0:
            logger.info(f"Main Branch {self.parent} is resuming with next {main_branch.route}")
            task_or_end = main_branch.generate_start_task()
            return task_or_end
        else:
            return RouterStatus.RUNNING


    def run_route(self, current_agent, output="", start = False):

        if output!="":
            output_id = str(uuid.uuid4()) + "_" +  str(time())
            # We use the router output to save the schema and other objects generated in the route. This is not needed in free-autonomous workflows because agents can use tools to
            # check what outputs are available and can be used.
            route_output = RouterOutput(
                route_output_id= output_id ,
                agent_name=current_agent,
                output=output["result"],
                schema=output["schema"] if output.get("schema",None) else {},
                logger_path=self.logger_path,
                raw_output=output["raw_output"],
                artifacts = output.get("artifacts",[])
            )
            route_output.save()
            self.router_outputs.append(output_id)
            self.save()
            


        
        task_or_end = self.generate_next_task(current_agent)

        if isinstance(task_or_end,RouterStatus) and task_or_end == RouterStatus.END:

            if self.parent !="":
                task_or_end = self.notify_main_branch()
                if isinstance(task_or_end,RouterStatus):
                    return task_or_end
                else:
                    [task.run_task() for task in task_or_end]
                    return RouterStatus.RUNNING

            else:
                return RouterStatus.END
        else:
            [task.run_task() for task in task_or_end]
            return RouterStatus.RUNNING
