from dataclasses import dataclass, field
import yaml
from a2a_framework.utils.registry import registry
from pathlib import Path
import os

@dataclass
class Skill:
    skill_name: str
    skill_description: str
    skill_tools : list[str] = field(default_factory=list)
    skill_usage_details : str = field(default_factory=str)

    def validate_tool_presence(self):
        missing_tools = [tool for tool in self.skill_tools if tool not in registry]
        if missing_tools:
            raise ValueError(f"The following tools are not registered: {', '.join(missing_tools)}")
        
    @classmethod
    def create_skill(cls, skill_name: str, skill_usage_details: str, skill_description: str, skill_tools: list[str]):

        skill = cls(skill_name=skill_name, skill_description=skill_description, skill_tools=skill_tools, skill_usage_details=skill_usage_details)
        skill.validate_tool_presence()
        return skill

    def make_skill_md_file(self, skill_directory: str = "available_skills"):
        path = Path(skill_directory).resolve()
        os.makedirs(path,exist_ok=True)

        skill_file_path = f"{path}/{self.skill_name}.md"
        with open(skill_file_path, "w") as f:
            f.write("---\n")
            f.write(f"name: {self.skill_name}\n")
            f.write(f"description: {self.skill_description}\n")
            f.write(f"available_tools: {','.join(self.skill_tools)}\n")
            f.write("---\n")
            f.write(f"# {self.skill_name}\n")
            f.write(f"# Usage Details\n{self.skill_usage_details}\n")
            f.close()
        return skill_file_path

    @classmethod
    def load_skill_from_md_file(cls, skill_file_path: str):
        with open(skill_file_path, "r", encoding="utf-8") as f:
            content = f.read()
            f.close()
        # Split the content into front matter and body
        front_matter, body = content.split("---\n")[1:3]
        # Parse the front matter using yaml
        skill_meta = yaml.safe_load(front_matter)

        return cls(skill_name=skill_meta["name"], 
                   skill_description=skill_meta["description"], 
                   skill_tools=skill_meta["available_tools"].split(","), 
                   skill_usage_details=body.strip())

    @classmethod
    def register_skill_from_md_file(cls, skill_file_path: str):
        skill = cls.load_skill_from_md_file(skill_file_path)
        skill.validate_tool_presence()
        skill.make_skill_md_file()
        return skill

    @classmethod
    def get_all_registered_skills(cls, skill_directory: str = "available_skills"):
        path = Path(skill_directory).resolve()
        skill_files = list(path.glob("*.md"))
        skills = []
        for skill_file in skill_files:
            skill = cls.load_skill_from_md_file(skill_file)
            skills.append(skill)
        return skills
