from dataclasses import dataclass
from pathlib import Path
from pydantic import BaseModel


class RepoConfig(BaseModel):
    url: str
    ref: str
    depth: int = 1
    dir: str | Path | None = None


class Project(BaseModel):
    dir: str | Path
    kernel: RepoConfig
    patches: RepoConfig


@dataclass
class Context:
    verbose: bool
    config: Project
