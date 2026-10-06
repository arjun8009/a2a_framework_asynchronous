import uuid
import json
from a2a_framework.utils.tool_wrapper import wrap_tool_output
import joblib
from dataclasses import dataclass,field,asdict
from a2a_framework.a2a.redis_client import redis_client
import logging
import subprocess
from a2a_framework.a2a.TaskStatus import TaskStatus
from a2a_framework.utils.static import *
from a2a_framework.a2a.notify import *
from a2a_framework.a2a.RouterUtils import RouterStatus
from a2a_framework.a2a.AgentState import AgentState
from a2a_framework.a2a.Messages import Messages
import redis





def route_or_completion(task, output):
    """Route a task result or write it as a completed user result.

    Args:
        task: Task whose router and logging configuration should be used.
        output: Tool output containing the raw result to route or persist.

    Output:
        RouterStatus indicating whether routing has ended or is still running.
    """
    # This is executed when we have the final output of a task which is a root task and we need to check if the process is completed or not
    # We need this becasue Routing system creates tasks without parent id and handles things differently see Routing.py
    # So we check is there a  underlying router_id if not then we write the success message.
    # If there is a router then we let the Router handle the routing
    from a2a_framework.a2a.Routing import Router
    logger = logging.getLogger(task.logger_path)
    logger.info(f"Routing or completion for task {task.task_id} and agent {task.agent_name} with router id {task.router_id} and output {output}")
    if task.router_id == "":
        return notify_user_and_write_success(output["raw_output"],task.logger_path)
    router = Router.load(task.router_id)
    
    router_output = router.run_route(task.tool_args["target"],output)
    if router_output == RouterStatus.END:
        return notify_user_and_write_success(output["raw_output"],task.logger_path)
    else:
        write_intermediate_output(output["raw_output"])
        return RouterStatus.RUNNING
    




@dataclass
class Task():
    """Manage the lifecycle of a task and coordinate its completion. It is the core part of the task management system

    Args:
        agent_name: Name of the agent executing the task or the task owner.
        history: Conversation id specifically in the format A1^A2.
        agentState: The state id as discussed in AgentState.py basically in A1_A2_uuid.
        task_id: Unique identifier for the task.
        parent_id: Identifier of the parent task, if any.
        tool_function: Name of the tool function to execute.
        tool_args: Arguments passed to the tool function.
        logger_path: Logger name used by the task.
        session_id: Identifier of the task session.
        status: Current task status.
        pending_children: Child task identifiers awaiting completion.
        result: Results produced by the task.
        router_id: Identifier of the router handling the task, if any.

    Output:
        A Task instance representing one executable task.
    """
    agent_name: str
    history : str
    agentState : str
    task_id : str
    parent_id :  str
    tool_function : str
    tool_args : dict
    logger_path : str
    session_id : str
    status : TaskStatus = TaskStatus.PENDING
    pending_children : list[str] =  field(default_factory=list)
    result : list[dict] = field(default_factory=list)
    router_id : str = ""




    @classmethod
    def create_task(cls, agent_name, messages, agentstate,tool_function,tool_args,logger_path,session_id,parent_id="", router_id=""):
        """This class method creates a task and then saves the task. it also increases the counter for the remaining task.

        Args:
            agent_name: Name of the agent executing the task.
            messages: Conversation id.
            agentstate: State id.
            tool_function: Name of the tool function to execute.
            tool_args: Arguments passed to the tool function.
            logger_path: Logger name used by the task.
            session_id: Identifier of the task session.
            parent_id: Optional parent task identifier.
            router_id: Optional router identifier.

        Output:
            The newly created and persisted Task instance.
        """
        task = cls(
            agent_name = agent_name,
            history = messages,
            task_id = str(uuid.uuid4()),
            agentState = agentstate,
            parent_id = parent_id,
            tool_function = tool_function,
            tool_args = tool_args,
            logger_path = logger_path,
            router_id=router_id,
            session_id = session_id
        )
        Logger = logging.getLogger(logger_path)
        Logger.info(f"Created task {task.task_id} for agent {agent_name} with parent_id {parent_id} and tool_function {tool_function}")
        task.save()
        redis_client.incr("counter:tasks_remaining")

        return task

    def _key(self) -> str:
        """Return the Redis key for this task.

        Args:
            None.

        Output:
            Redis key string for the task.
        """
        return f"task:{self.task_id}"

    def save(self) -> None:
        """Serialize and persist this task in Redis. We use a hset to store the class as a dictionary. Note : There are no objects here just a dictionary of strings


        Args:
            None.

        Output:
            None.
        """

        data = asdict(self)
        Logger = logging.getLogger(self.logger_path)
        Logger.info(f"Saved task {self.task_id} for agent {self.agent_name} with status {self.status} and arguments {data}")
        data["status"] = self.status.value
        data["result"] = json.dumps(self.result) if self.result is not None else ""
        data["pending_children"] = json.dumps(self.pending_children)
        data["tool_args"] = json.dumps(self.tool_args)
        
        redis_client.hset(self._key(), mapping=data)

    @classmethod
    def load(cls,task_id:str):
        """Load a task from Redis by identifier.

        Args:
            task_id: Identifier of the task to load.

        Output:
            Task instance reconstructed from Redis.
        """
        data = redis_client.hgetall(f"task:{task_id}")
        Logger = logging.getLogger(data["logger_path"])
        Logger.info(f"Loaded task {task_id} for agent {data['agent_name']} with status {data['status']}")
        
        if not data:
            raise KeyError(f"Task {task_id} not found")
        return cls(
            task_id=data["task_id"],
            agent_name=data["agent_name"],
            status=TaskStatus(data["status"]),
            parent_id=data["parent_id"],
            pending_children=json.loads(data["pending_children"]),
            history=data["history"],
            agentState = data["agentState"],
            result=json.loads(data["result"]) if data["result"] else [],
            tool_function = data["tool_function"],
            tool_args=json.loads(data.get("tool_args") or "{}"),
            logger_path = data["logger_path"],
            router_id = data["router_id"],
            session_id = data["session_id"]
        )
        
    
    def mark_running(self) -> None:
        """Set the task status to running and persist it.

        Args:
            None.

        Output:
            None.
        """
        self.status = TaskStatus.RUNNING
        Logger = logging.getLogger(self.logger_path)
        Logger.info(f"Task {self.task_id} for agent {self.agent_name} is now running")

        self.save()

    def mark_waiting(self) -> None:  ## Check 
        """Set the task status to waiting for child tasks and persist it.

        Args:
            None.

        Output:
            None.
        """
        self.status = TaskStatus.WAITING_ON_CHILDREN
        Logger = logging.getLogger(self.logger_path)
        Logger.info(f"Task {self.task_id} for agent {self.agent_name} is now waiting on children")
        self.save()

    def mark_waiting_human(self,query) -> None:  ## Check 
        """Set the task status to waiting for human input and persist it.

        Args:
            None.

        Output:
            None.
        """
        self.status = TaskStatus.WAITING_ON_HUMAN
        Logger = logging.getLogger(self.logger_path)
        Logger.info(f"Task {self.task_id} for agent {self.agent_name} is now waiting on human with task id {self.task_id}")
        self.save()
        write_intermediate_output(f"Task {self.task_id} for agent {self.agent_name} is now waiting on human with task id {self.task_id}. Please answer the following query {query}")

    def mark_done(self, result: str) -> None:
        """Mark the task done, persist its result, and notify its parent.

        Args:
            result: Tool result containing the task result value.

        Output:
            Parent-completion output, or None when the task has a parent.
        """
        # Here we handle as task when it is complete. 
        # We mark it as completed
        self.status = TaskStatus.DONE
        # Decrease a task from the counter
        _ = redis_client.decr("counter:tasks_remaining")
        Logger = logging.getLogger(self.logger_path)
        Logger.info(f"Task {self.task_id} for agent {self.agent_name} is now done")
        # Add the result to the task result
        self.result = result["result"]
        # We save the state of the owner agent of the task. Now this varies. If an agent say A1 makes a tool call then the child task
        # T1 is owned by A1 and A1's state is updated with the tool call. But if agent A1 makes a call to another agent A2
        # Then the child task T1 is still owned by A1 even if A2 is being invoked. An we update A1's context with A2's output. 
        # This is because in Agent.py the final response of A2 is taken and A2's state is updated. Here we update the state of the 
        # invoking agent.
        AgentState.save(self.agent_name,self.session_id,[{"role":"user","content":self.result}],self.logger_path)
        self.save()
        # Finally we call the on_complete function. By now all agent states are updated with the result. For a tool call A1's state is updated with the tool output
        # For a send_message call A1 and A2 both states are updated. A2's state is updated with its final response and A1's state is updated with A2's final response.
        result = self._on_complete(result)
        return result

    def _notify_parent(self, failed: bool = False) -> None:
        """Remove this task from its parent's pending children and resume the parent.

        Args:
            failed: Whether the child completed unsuccessfully.

        Output:
            None.
        """
        Logger = logging.getLogger(self.logger_path)
        # The entire while loop is to make it compliant to parallel processing. All it does it when a task is completed it loads the parent id
        # Remove the task id from the parent's children tracking ids. if the parent has no more child tasks then it means that all the pending child tasks are
        # now completed and it reruns the parent to generate a reply
        while True:
            with redis_client.pipeline() as pipe:
                try:
                    pipe.watch(f"task:{self.parent_id}")
                    children_json = pipe.hget(f"task:{self.parent_id}", "pending_children")
                    children = json.loads(children_json) if children_json else []
                    Logger.info(f"Retrieving pending children for task {self.parent_id}: {children}")
                    if self.task_id in children:
                        children.remove(self.task_id)
                    Logger.info(f"Updated pending children for task {self.parent_id}: {children}")
                    pipe.multi()
                    pipe.hset(f"task:{self.parent_id}", "pending_children", json.dumps(children))
                    pipe.execute()   # raises WatchError if key changed since watch()
                    Logger.info(f"Successfully updated pending children for task {self.parent_id} after child {self.task_id} completed and is now breaking out of the loop")
                    break
                except redis.WatchError:
                    Logger.info(f"Retrying pop of child {self.task_id} on parent {self.parent_id} due to concurrent write")
                    continue

        parent = Task.load(self.parent_id)
        if len(parent.pending_children) == 0:
            Logger.info(f"All children of parent task {parent.task_id} for agent {parent.agent_name} have completed. Now re running parent")
            parent._on_children_resolved()

    def _on_children_resolved(self) -> None:
        """Resume this task after all child tasks have completed.

        Args:
            None.

        Output:
            None.
        """
        # This is executed when the parent has no pending child tasks. That is all its tool calls are completed. We re-enque the task 
        # We set conversation and state flag to force the agent to use it's state context rather than the conversation to provide it 
        # access to it's tool call. The else block is never run so will be removed later.
        Logger = logging.getLogger(self.logger_path)
        Logger.info(f"All children of task {self.task_id} for agent {self.agent_name} have completed. Now re running task with status {self.status}")
        if self.tool_function == "send_message" and self.status != TaskStatus.DONE:
            self.tool_args["use_conversation_or_state"] = "state"
            Logger.info("setting conversation or state to state to initiate reply")
            self.save()
            self.run_task()   # re-enqueue self — execute() runs run_agent_turn again
        else:
            self.run_task()

    def _on_complete(self, result: dict) -> None:
        """Notify the parent task or return the root task result.

        Args:
            result: Completed task result.

        Output:
            The result for a root task; otherwise None after notifying the parent.
        """
        # We now notify parent if there is a parent task
        Logger = logging.getLogger(self.logger_path)
        if self.parent_id !="":
            Logger.info(f"Task {self.task_id} for agent {self.agent_name} is notifying parent task {self.parent_id}")
            self._notify_parent()
            return None
        else:
            Logger.info(f"Task {self.task_id} for agent {self.agent_name} is a root task with no parent calling entry agent for final resolution or continuation ")
            return result
    
    def run_task(self) -> None:
        """Add this task identifier to the tool execution queue.

        Args:
            None.

        Output:
            None.
        """
        Logger = logging.getLogger(self.logger_path)
        Logger.info(f"Task {self.task_id} for agent {self.agent_name} is now being enqueued for execution")
        redis_client.rpush("queue:tool_execution", self.task_id)


    def execute(self) -> None:
        """Execute the task tool and handle its lifecycle transitions.

        Args:
            None.

        Output:
            None. Results and status changes are persisted as side effects.
        """
        # We set the task to running
        self.mark_running()
        Logger = logging.getLogger(self.logger_path)
        final_output = None
        child_tasks = []

        # We add some extra arguments, that is the parent_id fo later use in tool_templates.py
        if self.tool_function == "send_message" and self.tool_args.get("human_reply",None) is None:
            self.tool_args["parent_id"] = self.task_id
            self.save()

        # This is for human in the loop implementation. When the Task is waiting for human. Everything suspends, so we save the human response and mark it done
        if self.tool_args.get("human_reply",None) is not None:
            Messages.save(self.tool_args["conversation_id"],[{"speaker":"human_agent","content":self.result["result"], 
                                                              "filter_messages": self.tool_args.get("filter_messages", "null")}],self.logger_path)
            
            final_output = self.mark_done(self.result)

        Logger.info(f"Task {self.task_id} for agent {self.agent_name} is now executing tool function {self.tool_function} with arguments {self.tool_args}")

        try:
            # Finally if there is no human reply. We execute the tool and check the status. Based on the status some decisions are made. 
            # 1. For new child tasks we just store the id and then run them at the end
            # 2. For Human approval we acknowledge it and suspend things
            # 3. For final outputs we mark it done
            # 4. For failures we end the process. Will add retry functionality later
            output = wrap_tool_output(self.tool_function, self.tool_args, self.logger_path)
            Logger.info(f"Output received by tool wrapper in task execute {output}")

            if output["status"] == TaskStatus.WAITING_ON_CHILDREN:
                if output.get("child_tasks",None) is not None and len(output.get("child_tasks")) > 0:
                    self.pending_children.extend(output.get("child_tasks"))
                    child_tasks.extend(output.get("child_tasks"))
                self.mark_waiting()

            elif output["status"] == TaskStatus.WAITING_ON_HUMAN:
                self.mark_waiting_human(output["result"])
            

            if output["status"] == TaskStatus.DONE:
                # We save the messages in global context
                if self.tool_function == "send_message":
                    Messages.save(self.tool_args["conversation_id"],[{"speaker":self.tool_args["target"],"content":output["result"]
                                                                      ,"filter_messages": self.tool_args.get("filter_messages", "null")}],self.logger_path)
                    
                final_output = self.mark_done(output)
            self.save()


            if output["status"] == TaskStatus.FAILED:
                Logger.info("TASK FAIL ENDING WORKER")
                pids = joblib.load(WORKER_PATH)
                status = notify_user_and_write_failure(output)
                redis_client.flushdb()
                for pid in pids:
                    subprocess.run(["taskkill", "/PID", str(pid), "/F"])


            if final_output is not None:
                # If the final output is received then END then check if it is actually completed or some task are running in parallel
                # This is done by route_or_completion function
                Logger.info(f"Final output of the task {self.task_id} and agent {self.agent_name} is : {final_output}")

                if self.parent_id == "" :
                    # Killing the process worker

                    pids = joblib.load(WORKER_PATH)
                    status = route_or_completion(self,final_output)
                    if status == RouterStatus.END:
                        Logger.info("Final Output of the framework completed worker shutting down")
                        for pid in pids:
                            subprocess.run(["taskkill", "/PID", str(pid), "/F"])


            if  len(child_tasks) > 0:
                Logger.info(f"Child tasks created by task {self.task_id} for agent {self.agent_name} are : {child_tasks}")
                for child_task in child_tasks:
                    Task.load(child_task).run_task()
                child_tasks = []

        except Exception as e:
            Logger.error(e,exc_info=True)
            Logger.info("ERROR in the framework completed worker shutting down")
            notify_user_and_write_failure(e)
            pids = joblib.load(WORKER_PATH)
            for pid in pids:
                subprocess.run(["taskkill", "/PID", str(pid), "/F"])