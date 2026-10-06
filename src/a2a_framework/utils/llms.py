from openai import OpenAI
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage,SystemMessage
import json
import warnings
import os
import logging


# We can create hybrid architectures with both openai and whitebox models. 
# Without GPU availability let us limit to 3b-8b models only. 
# In such cases we do not use these models for data analysis or tool usage but as supervisors to coding agents


# This is a utility function to try and parse json response from the llm and validate it using our schema. Should work normally but edge cases will be there
def parse_and_validate(output:str,schema:object):
    '''
    Parse through the llm output and convert it to structured. Used in cases where reasoning models do not support structured output
    args:
    output : str = output of the model
    schema : orginal pydantic schema

    output: parsed schema
    '''
    output = output.replace("`","").replace("json","")
    return schema.model_validate_json(output)

#Function that tries to convert pydantic schema to a json schema automatically and this can be added to the prompt
def convert_pydantic_schema_to_json(schema):
    '''
    Convert pydantic schema to json schema
    args:
    schema: pydantic schema for structured output
    output:
    json schema to be added to the prompt'''
    schema_dumped = {k: v.default for k, v in schema.model_fields.items()}
    return json.dumps(schema_dumped,indent=2)


# Function that  creates compatible prompt formats given an llm instance. messages should be made in default openai api style
def create_compatible_prompt_template(llm_instance,messages:list,isthinking:bool):
    '''Make the messages compatible accross various llm platforms.
    Args:
    llm_instance: The instantiated LLM model
    messages: list of messages in openai style
    
    outputs:
    messages : Now compatible with llm instance'''
    
    # if it is openai instance then return them
    if not isinstance(llm_instance,ChatOllama):
        if isthinking:
            for i,j in enumerate(messages):
                if isinstance(j, dict) and j.get("role") == "system":
                    messages[i]["role"] = "user"
        return messages
    else:
        messages_changed = []
        for i in messages:
            if isinstance(i, dict) and i.get("role") == "system":
                messages_changed.append(SystemMessage(content = i["content"]))
            else:
                messages_changed.append(HumanMessage(content=i["content"]))
        return messages_changed
    

# Function to run an llm instance can be a langchain instance or an openai instance. Will return output in different formats : structured, messages and tools.
# Note tools can only be used for openai llms

def run_llm(model_name: str , url:str, messages: list, schema:object, tools:object, logger:str, reasoning:bool=False,  additional_args={"temperature":0,"max_tokens":2048, "parallel_tool_calls":True}):
    ''' Run the LLM instance with the given prompt.
    Args:
        model name : Name of a model from a choice of approved models current llama3.2, gpt-4 variants and thinking models o1-o3 models
        messages (list): A list of messages to send to the LLM
        schema : A pydantic object
        tools : Tool descriptions will only be applied to openai llms
        args : more args containing temperature and max tokens
    Returns:
        The response from the LLM.
        can be an object in case of structured output
        can be a list of messages in case of tools
        can be a simple response'''
    
    # use default args and add keys of additional args
    default_args = {"temperature":0,"max_tokens":2048, "parallel_tool_calls":False}
    args = {**default_args, **additional_args}

    Logger = logging.getLogger(logger)
    Logger.info(f"parallel tool calls is {args['parallel_tool_calls']} and reasoning is {reasoning}")
    # Check if openai model else checks for ollama models
    # also checks if it is a reasoning model or not. As thinking models do not accept temperature and max_tokens
    
    isthinking = False
    if os.getenv("LLM_API_KEY"):
        api_key = os.getenv("LLM_API_KEY")
    else:
        api_key = os.getenv(model_name)

    llm_instance = OpenAI(base_url=url, api_key=api_key) if url !="" else OpenAI(api_key=api_key)
    isthinking = reasoning
    [tool.update({"strict": None}) for tool in tools]

    # if Ollama make the messages compatible and then call it while checking for schema. Does not support tools
    messages = create_compatible_prompt_template(llm_instance,messages,isthinking)
    
    openai_llm_instance = llm_instance
    llm_args = {
        "model": model_name,
        "input" : messages
    }
    if tools:
        llm_args["tools"] = tools
        llm_args["parallel_tool_calls"] = args["parallel_tool_calls"]

    if isthinking:
        llm_args["reasoning"] = args.get("reasoning", None)

    if schema:
        llm_args["text_format"] = schema

   
    Logger.info(f"Running LLM {model_name} with base_url {url} isthinking {isthinking} messages :{messages} and tools {tools}")
    return openai_llm_instance.responses.parse(**llm_args)
    

