### Agentic Communication Library

This is an open source library for Agent creation and Task creation. Below are its uses and advantages

* This system can create and instantiate a multi-agentic platform given a set of tools, prompts and agent ideas.
* The user needs to create an idea of an application and a multi-agentic architecture
* The user would need to design a set of prompts and tools that the agents can use
* Finally the user would just need to provide a json file containing the name of the prompts, tools and agent specifications

### Working Principle

This library uses a task execution lifecycle. Every agent interation between different agents and tools are designed as a Task
A task has the following lifecycle states

* Pending
* Running
* Done
* Failed
* Waiting on Children
* Waiting on Human

At any point a task executing a tool can be in one of the above 6 states. This tool supports asynchronous execution using Redis so a worker takes on the job when the main process encounters a long task.

### Example Trajectories
User : perform Task A

Task (T0 : root task) -> send_message(human, A1) -> run(A1) -> Task (T1 : Child Task,  Parent : T0) -> send_message(A1, A2) -> run(A2) -> Task (T2 : Child Task, Parent: T1) -> tool
      1.  Pending                                               Pending                                                                    Pending
      2.  Running                                               Running                                                                    Running
      3.  Waiting on Child                                      Waiting on Child                                                           Done
      4.  Child T1 Notified parent Running                      child T2 notified parent : Running                                         notify_parent()
      5.  Done                                                  Done
      6.  notify_human()                                        notify_parent()

### usage 

* create a filename for prompts (needs to be a .py file) with variable assigned to prompt for each agent.
* create a filename for tools (needs to be a .py file).
* create a tool definitions files (needs to be a .py) file with OpenAI style tool definitions.
* Create some cards for the agents in a .py file refer to a2a.AgentCard. These help for better agent communication.

##### Json creation

The Json will have 2 fields. Example given below.
* path_config mentions the path to the prompts tools, tool_defs and agent cards
* agent_config : defines the agents with available_agents indication what agents "host agent" can communicate with. If it is a single agent then single route orchestration else
  llm decided multiple route orchestration

```json
{   "path_config" : {
            "tools_path" : "tools.py",
            "prompts_path":"prompts.py",
            "tool_definitions_path": "tool_defs.py",
            "card_templates_path":"cards.py"
    
    },
    "agent_config" :  [{
            "agent_name": "host_agent",
            "version": "1.0.0",
            "agent_details":"host_agent_card",
            "model_name":"openai/gpt-4.1",
            "reasoning":false,
            "base_url" : "https://openrouter.ai/api/v1",
            "tools":["send_message","generate_metadata_for_all_artifacts"],
            "tool_definitions":["send_message_definitions","metadata_all_artifacts"],
            "additional_args":{"parallel_tool_calls":false},
            "system_instruction":"host_prompt_template_for_osm",
            "available_agents":["planning_agent","address_agent","named_area_agent","buildings_agent","water_network_agent","land_features_agent","land_use_features_agent","plotting_agent","human_agent"]
        }]
}
```
#### Python Usage

Finally the usage is simple and shown below.

```python
from a2a_framework.utils.run_architecture import run_agent_architecture, run_human_reply
from a2a_framework.utils.initialise import initialize

logger_path = initialize("agent_frameworks/a2a_async_test_1.json","a2a_test_log-1","a2a_test_logs",
           "C:/Users/ab1574/OneDrive - University of Exeter/Desktop/Ordnance_Survey/osvenv/Scripts/python.exe")

run_agent_architecture("Find all short buildings in Exeter which are less than 2 floors", "host_agent", logger_path)
```

* In initialise you provide a path for the log file and output files and a path for the json so args are
  * json path
  * log file dir
  * log file name
* output or failure shown in output.md and failure.md in the log file dir.

