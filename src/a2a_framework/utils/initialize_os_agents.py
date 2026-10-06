# First the imports and the keys
import warnings
warnings.filterwarnings("ignore")
from a2a_framework.utils.registry import registry, register
import logging
from a2a_framework.a2a.redis_client import redis_client
from pathlib import Path
import json
import importlib.util
import sys
from a2a_framework.utils.static import *
from a2a_framework.skills.Skill import Skill






class OSAgentsInitializer():
    def __init__(self, config, logging_filename = "log", diff_dir = None, write_mode="w"):
        '''
        This class accepts a dictionary of agent configurations and initializes OS agents accordingly.
        args:
            1. config : str =  A path to the config file in the user space
            2. logging_filename : str = Preffered name of the log file
            3. diff_dir :str = Name of the directory where the log file is stored
            4. write_mode : str = Whether to append or create a new log file. User can choose anything here. But workers will always be mode [a]
                
        '''
        self.write_mode = write_mode
        self.config = config
        self.agent_dict = None
        self.dif_dir = diff_dir
        self.logging_filename = logging_filename
        self.logger_path = str(Path(f"{diff_dir}/{self.logging_filename}.log").resolve())
        # Boilerplate code to make a logger
        if diff_dir is not None:
            self.logger = logging.getLogger(self.logger_path)
            self.logger.setLevel(logging.INFO)
            self.logger.handlers.clear()
            filehandler = logging.FileHandler(self.logger_path,mode=self.write_mode)
            filehandler.setLevel(logging.INFO)
            formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            filehandler.setFormatter(formatter)
            self.logger.addHandler(filehandler)
        else:
            self.logger = logging.getLogger(self.logger_path)
            self.logger.setLevel(logging.INFO)
            self.logger.handlers.clear()
            filehandler = logging.FileHandler(self.logger_path,mode=self.write_mode)
            filehandler.setLevel(logging.INFO)
            formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
            filehandler.setFormatter(formatter)
            self.logger.addHandler(filehandler)
            
        
        # Prevent propagation to root logger
        self.logger.propagate = False

    def read_config(self):
        # Similar boilerplate code to read the config file
        config_dict = None
        self.config = Path(self.config).resolve()
        with open(self.config,"rb") as file:
            config_dict = json.load(file)
        self.agent_dict = config_dict

    def load_module_from_path(self, path: str):
        '''
        This loads the modules from a python file path. Example if prompts.py contains all the prompts, it loads the prompts.py file in the python sys modules to be usable
        args:
            1. path : str = Path of any python file
        output : 
            The imported module
        '''
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"No such file: {path}")

        module_name = path.stem 
        spec = importlib.util.spec_from_file_location(module_name, path)
        module = importlib.util.module_from_spec(spec)

        # Handles dependencies
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        return module
    
    def create_registry(self,config):
        '''
            Takes the config and adds the mapping of var name and var in registry to prevent manual writing. This actually creates the registry which is used
            throughout the codebase and is an important part of the library.
            args:
                1. config : dict = The loaded config file
            output: 
                The created registry.
        '''

        # We import the existing prompts, tools, tool_defs and cards
        from a2a_framework.utils import prompt_templates
        from a2a_framework.utils import tool_definition_templates as tool_definition_templates
        from a2a_framework.utils import tool_templates as tool_templates
        from a2a_framework.utils import card_templates

        # We register the json config in the registry
        register("config",self.config)

        # This is a static file full of constants that we maintain separately see utils.static.py
        OUTPUT_PATH["notify_url_success_or_intermediate"] = config["path_config"].get("notify_url_success_or_intermediate",None)
        OUTPUT_PATH["notify_url_failure"] = config["path_config"].get("notify_url_failure",None)

        # Here we are getting the path of the prompts, tools, tool_defs, cards_def and utitlity functions used by the agent like query_processing or conditional routing functions

        prompt_path  = config["path_config"]["prompts_path"]
        tools_path = config["path_config"].get("tools_path",None)
        tool_defs_path = config["path_config"].get("tool_definitions_path",None)
        cards_path = config["path_config"]["card_templates_path"]
        utility_func_path = config["path_config"].get("utility_path",None)

        # We load all the variables and functions using the load_module function. This returns a python module which is a dict of name and objects
        prompts = self.load_module_from_path(prompt_path)
        tools = self.load_module_from_path(tools_path) if tools_path else None
        tool_definitions = self.load_module_from_path(tool_defs_path) if tool_defs_path else None
        cards = self.load_module_from_path(cards_path)
        utilities = self.load_module_from_path(utility_func_path) if utility_func_path else None


        # We only choose the prompts and cards that are in the config file.
        agent_prompts = [config_item.get("system_instruction") for config_item in config["agent_config"]]
        agent_cards = [config_item.get("agent_details") for config_item in config["agent_config"]]


        # Now we create registry dicts for all the above modules. In some cases like prompts and cards we only register what is in the config.
        # We do not check the tools and utiltites because sometimes an agent may have just skills and not tools. A skill may use specific tools
        # So we take all the tools and when the skills require tools we use only the tools specific for the skill.
        # There maybe an argument here about malicious code injection from a security standpoint. 
        # We may need more inspection of the imports. Coming soon in later updates
        utilities_registry = {
            name:value for name,value in vars(utilities).items()
        } if utilities else {}

        prompts_registry = {
            name: value for name, value in vars(prompts).items()
            if name in agent_prompts
        } if prompts else {}

        prompt_templates_registry = {
                    name: value for name, value in vars(prompt_templates).items()
                    if name in EXISTING_PROMPTS
                } if prompt_templates else {}

        card_templates_registry = {
            name: value for name, value in vars(card_templates).items()
            if name in EXISTING_CARDS
        } if card_templates else {}

        cards_registry = {
            name: value for name, value in vars(cards).items()
            if name in agent_cards
        } if cards else {}

        

        tool_definitions_templates_registry = {
            name: value for name, value in vars(tool_definition_templates).items()
        } if tool_definition_templates else {}

        tools_registry = {
            name: value for name, value in vars(tools).items()
        } if tools else {}

        tool_definitions_registry = {
            name: value for name, value in vars(tool_definitions).items()
            } if tool_definitions else {}
        
        tools_templates_registry = {
                    name: value for name, value in vars(tool_templates).items()
                } if tool_templates else {}
        
        total_dict = {**prompts_registry,**card_templates_registry,**tool_definitions_registry,**tools_registry, 
                      **prompt_templates_registry,**tool_definitions_templates_registry,**tools_templates_registry, **cards_registry, **utilities_registry}

        
        for key,val in total_dict.items():
            register(key,val)



    
    def initialize_agent(self,agentconfig:dict,routing:bool):

        '''Add everything as params using the registry. Except system instruction and available agent dependencies for now. We just parse through the parameters and 
        instantiate the agents
        args:
            1. agentconfig : A dictionary containing the configuration for a single agent
        '''


        

        if agentconfig["agent_name"].lower() == "human":
            return registry["Human"](
                human_details = registry[agentconfig["agent_details"]]
            )
        else:
            if agentconfig.get("type") is not None:
                if agentconfig.get("agent_details",None) is not None:
                    agent_details = agentconfig["agent_details"]
                else:
                    agent_details = EXISTING_CARDS_MAPPING[agentconfig["type"]]
            else:
                agent_details = agentconfig["agent_details"]

            system_instruction = registry.get(agentconfig.get("system_instruction",""),"") if agentconfig.get("type",None) is None else registry.get(agentconfig.get("system_instruction",""),"") + registry[EXISTING_PROMPTS_MAPPING[agentconfig["type"]]]

            if not routing:
                tool_defs = [registry[tool_def] for tool_def in EXISTING_TOOL_DEFS] + [registry[tool_def] for tool_def in agentconfig.get("tool_definitions",[])]
                system_instruction = system_instruction + "\n To communicate, assign tasks talk to other available agents or seek human confirmation given below use the send_message tool. Do not use any other tool. All conversation or questions to user should be done by human_agent and nothing else unless you have the final answer."
            else:
                tool_defs = [registry[tool_def] for tool_def in agentconfig.get("tool_definitions",[])]


            if agentconfig.get("type",None):
                tool_defs = tool_defs + [registry[EXISTING_TOOL_TYPES_DEF_MAPPING[agentconfig["type"]]]]
            if agentconfig.get("skills",None):
                tool_defs = tool_defs + [registry[SKILL_TOOL_DEFS[0]]]
                system_instruction = system_instruction + "\n To load skills use the load_skill tools. You can only load 1 skill at a time. To load another skill call the load_skill again"

            return registry["Agent"](
                agent_details=registry[agent_details] ,
                model_name=agentconfig["model_name"] if agentconfig.get("model_name",None) else "gpt-4o-mini",
                base_url = agentconfig["base_url"] if agentconfig.get("base_url",None) else "",
                reasoning = agentconfig["reasoning"] if agentconfig.get("reasoning",None) else False,
                tool_definitions=tool_defs,
                schema=registry[agentconfig.get("schema",None)] if agentconfig.get("schema",None) is not None else None,
                additional_args=agentconfig.get("additional_args",None),
                system_instruction=system_instruction,
                logger = self.logger_path
            )
    
    def add_agent_dependencies(self,initialized_agents:dict):
        '''Add system instructions and available agent dependencies to initialized agents.
        args:
            1. initialized_agents : A dictionary where keys are agent names and values are initialized agent instances
        '''
        # This is what is happening here.
            # For each agent in the agent config, check if it has available agents.
            # If it does, then used the preinitialized agents to get that instance of the agent and set its system instruction to include the available agents.
            # Available agents can be received from the agent config and we are using the preinitialized agents to get the instance of the agent and its details.
        for agents in self.agent_dict["agent_config"]:
            if agents.get("available_agents",None):
                initialized_agents[agents["agent_name"]].system_instruction = registry[agents.get("system_instruction")] + \
                "\n" + (registry[agents["additional_prompts"]] if agents.get("additional_prompts") else "") + \
                f"""\n <AVAILABLE AGENTS> {[initialized_agents[i].agent_identity for i in agents["available_agents"]]} <AVAILABLE AGENTS>""" 

        for agents in self.agent_dict["agent_config"]:
            register(agents["agent_name"],initialized_agents[agents["agent_name"]])


    def initialize_agent_skills(self,agent_config:dict):

        '''This is specifically for agent skills. Given a skill_config path, we load all the skills and make the skill.md file
        args:
            1. agent_config : dict = The provided agent_config
        output:
            skill.md files '''

        skill_config_path = agent_config["path_config"].get("skills_config_path",None)

        if not skill_config_path:
            self.logger.info("No skills found to initialize")
            return

        skill_config = json.load(open(Path(skill_config_path).resolve(),"rb"))
        # We get the skill path, load the skills from module and then add those skills to the agent prompts. 
        skill_instructions_path = Path(skill_config["path_config"]["instructions_path"]).resolve()
        skill_instruction_module = self.load_module_from_path(skill_instructions_path)
        skill_instructions ={name:value  for name,value in vars(skill_instruction_module).items()}
        skill_defs = skill_config["skills_config"]

        for skill_def in skill_defs:

            skill = Skill.create_skill(skill_name=skill_def["skill_name"],
                               skill_description=skill_def["skill_description"],
                               skill_usage_details= skill_instructions[skill_def["skill_instructions"]],
                               skill_tools = skill_def.get("available_tools",[]))

            agents_using_skill = [i["agent_name"] for i in agent_config["agent_config"] 
                                  if (i.get("skills",None) is not None) and (skill.skill_name in i.get("skills"))]

            for agent in agents_using_skill:
                registry[agent].system_instruction = registry[agent].system_instruction + "\n" + f"SKILL AVAILABLE : skill_name : {skill.skill_name} and description : {skill.skill_description}"

            skill.make_skill_md_file()
            self.logger.info(f"Intialized skill {skill.skill_name} for agents {agents_using_skill}")

                
    
    def initialize_all_agents(self):

        OUTPUT_PATH["success"] = Path(self.dif_dir)/"success.md"
        OUTPUT_PATH["failure"] = Path(self.dif_dir)/"failure.md"
        OUTPUT_PATH["intermediate"] = Path(self.dif_dir)/"intermediate.md"

        initialized_agents = {}
        self.read_config()
        self.create_registry(self.agent_dict)
        for agent_config in self.agent_dict["agent_config"]:
            if self.agent_dict["path_config"]["type_of_architecture"] == "deterministic":
                initialized_agents[agent_config["agent_name"]] = self.initialize_agent(agent_config,True)
            else:
                initialized_agents[agent_config["agent_name"]] = self.initialize_agent(agent_config,False)
            self.logger.info(f"""Agent {agent_config["agent_name"]} Initialised""")
        self.add_agent_dependencies(initialized_agents)
        self.initialize_agent_skills(self.agent_dict)
        # self.initialize_agent_states()


        return self.logger_path
    
    

