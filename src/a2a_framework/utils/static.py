from pathlib import Path


STATE_PATH = Path.cwd() / "state_store"
WORKER_PATH = Path.cwd()/"worker_store"/"worker.joblib"
ARTIFACT_PATH = Path.cwd() / "artifacts"
MESSAGES_PATH = Path.cwd() / "message_store"
HUMAN_PENDING_TASK = Path.cwd()/"pending_human_task"/"taskid.joblib"

OUTPUT_PATH = {
    "success":None,
    "failure":None,
    "intermediate":None,
    "notify_url_success_or_intermediate" : None,
    "notify_url_failure" : None
}


EXISTING_PROMPTS = ["generic_coding_agent_template"]
SKILL_TOOLS = ["load_skill"]
SKILL_TOOL_DEFS = ["load_skill_definition"]
EXISTING_TOOLS = ["send_message"]
EXISTING_CARDS = ["coding_agent_details","human_agent_card"]
EXISTING_TOOL_DEFS = ["send_message_definitions"]

EXISTING_CARDS_MAPPING = {
    "coding" : "coding_agent_details",
}

EXISTING_TOOL_TYPES_MAPPING = {
    "coding" : "code_executor",
}

EXISTING_TOOL_TYPES_DEF_MAPPING = {
    "coding" : "code_executor_definition",
}

EXISTING_PROMPTS_MAPPING = {
    "coding" : "generic_coding_agent_template",
}

