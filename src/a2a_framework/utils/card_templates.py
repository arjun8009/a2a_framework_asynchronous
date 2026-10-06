from a2a_framework.a2a.AgentCard import AgentCard

# Basic Card templates for exisiting agents. Card Templates help other agents to understand the capabilities of other agents
# capabilities should be detailed to show what is possible when using the particular agent 

coding_agent_details = AgentCard(agent_name="coding_agent",
                                    agent_description="It is a useful agent that can perform data analysis on a given data set and provide insights",
                                    capabilities=["Given a dataset, it can perform various data analysis tasks like summarization, statistical analysis, visualization etc."
                                                  "Cannot search for point in 1 artifact using another."],
                                    input_modes=["task in str with the filenames provided to analyse data"],
                                    output_modes=["str","list out outputs including summaries, artifacts like plots and data files and their name and description"])

human_agent_card = AgentCard(agent_name="human_agent",
                                agent_description="A human agent that can be queried for help when there is ambiguity in the user query",
                                capabilities=["Can help resolve ambiguities in user queries",
                                            "Can provide clarifications on spatial conditions"],
                                input_modes=["query : str containing the ambiguity or clarification needed"],
                                output_modes=["string containing the human response"])