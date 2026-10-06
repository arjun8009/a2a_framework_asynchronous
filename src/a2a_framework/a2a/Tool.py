
from a2a_framework.a2a.Artifact import Artifact


class ToolResult:
    output : str|dict|list
    artifacts : list[Artifact]

    def __init__(self, output:str|dict|list, artifacts : list[Artifact]):
        self.output = output
        self.artifacts = artifacts
