## Agentic Communication Library : Version 0.0.1

This is a python library that helps any user create an agentic system with minimum effort and without focusing on the intricasies of creating llm instances, handling tool calls, 
managing messages and llm states and routing information between different agents.

User provide  :

* A basic blueprint of their desired agentic architecture by filling up a json template
* A set of prompts that indicate the behaviour of the agents
* **OPTIONAL** : A set of tools that the agent may use, like access to specific databases or models or processing functions
* **OPTIONAL** : A set of schemas that the user may want the agents to use

Using this information and the blueprint template the agentic communication library :

* Compiles the prompts and the tools 
* Parses the blueprint
* Intitialises agents with required context
* Returns an endpoint that the users can use to run their architecture

The Aim of this library is :
* To help developers make complex multi-agent architectures without learning the syntax of the of various different agentic SDLC packages which require understanding the working of the library to use it.
* The presence of abstraction helps developers to focus only on the domain specific nature of the problem, and the overall idea of the architecture rather than coding the architecture itself.
* The library intentionally does not employ LLM's to write user tools and prompts itself to give users better control and more involvement in the development process.

## Get Started

Given an idea of a multi-agentic platform the following steps can be followed to use the library

* Decide on the type of architecture : Will it be a free flow system where agents decide which agents to communicate or a strict information flow system where agents are executed in a predefined manner.

* Write the prompts and the tools that will provide agents with their behaviour and utitities
* Fill out the complete blueprint
* Use the library to compile and run the architecture 

### Deciding the type of architecture

This library supports two types of agentic architectures :
* **Agentic** : This type of architecture gives autonomy to the agents. So given a problem, different agents communicate and assign tasks to other agents to solve a problem.
* **Deterministic** : This type of architecture involves a controlled information flow between different agents as pre-planned by the user (Agent 1 -> Agent 2 ... Agent N).
* **Hybrid** : A combination of both

### Example JSON
```json
{   "path_config" : {
            "prompts_path":"prompts.py",
            "card_templates_path":"cards.py",
            "utility_path":"utilities.py",
            "type_of_architecture" : "deterministic",
            "tools_path":"tools.py",
            "tool_definitions_path":"tool_defs.py",
            "notify_url_success_or_intermediate" : "<URL_TO_NOTIFY>",
            "notify_url_failure" : "<URL_TO_NOTIFY>",
            "key":"<YOUR_API_KEY>",
            "route" : ["query_intent_agent","database_choice_agent","END"]
       },
    "agent_config" :  [{
            "agent_name": "query_intent_agent",
            "version": "1.0.0",
            "agent_details":"query_intent_agent_card",
            "model_name":"openai/gpt-4.1",
            "reasoning":false,
            "base_url" : "https://openrouter.ai/api/v1",
            "additional_args":{"parallel_tool_calls":false},
            "system_instruction":"query_intent_prompt",
            "schema":"QueryIntentSchema"
        },
        {
            "agent_name":"database_choice_agent",
            "version":"1.0.0",
            "agent_details":"database_choice_agent_card",
            "model_name":"openai/gpt-4o",
            "reasoning":false,
            "base_url" : "https://openrouter.ai/api/v1",
            "system_instruction":"database_choice_prompt",
            "query_processing":"process_database_output",
            "additional_args":{"parallel_tool_calls":false},
            "schema":"DatabaseSchema"
        },
        {
            "agent_name":"human_agent",
            "version":"1.0.0",
            "agent_details":"human_agent_card",
            "tools":[],
            "tool_definitions":[]
        }]

        }
```

### Running the config

```python
from a2a_framework.utils.run_architecture import run_architecture,run_human_reply
from a2a_framework.utils.initialise import initialize

logger_path = initialize(r"<JSON_PATH>","<LOG_FILE_NAME>","<OUTPUT_DIR>", 1,
           "<virtual environment path>")
```


