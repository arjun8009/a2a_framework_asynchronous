import warnings
warnings.filterwarnings("ignore")
from a2a_framework.a2a.Agent import Agent
from a2a_framework.a2a.AgentCard import AgentCard
from a2a_framework.a2a.Artifact import Artifact
from a2a_framework.a2a.AgentState import AgentState

''' This is the registry the singular mapping of all the classes and variables in the Repo. It
    is used to initialise the agents.'''

registry = {
    "Agent":Agent,
    "AgentCard":AgentCard,
    "Artifact":Artifact,
    "AgentState":AgentState,
    "additional_args":{"parallel_tool_calls":False}
}

def register(name:str, obj:object):
    '''This function is used to register a new object in the registry. It is used to add new tools, agents, and other objects to the registry.
    args:
        1. name : The name of the object to be registered
        2. obj : The object to be registered
    '''
    registry[name] = obj

