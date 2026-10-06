from pydantic import BaseModel

class AgentCard(BaseModel):
        
        '''Default class description to define the definition of an agent. This is like the visiting card that an agent can use to communicate with other agents'''
        
        # A proper sensible agent name

        agent_name : str
        
        # A brief description of what the agent does
        agent_description : str

        # A list of capabilities, inluding information about state transitions
        capabilities : list[str]

        # A list of input modes 
        input_modes: list[str]

        # A list of output modes
        output_modes:list[str]