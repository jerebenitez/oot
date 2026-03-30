from dataclasses import dataclass
from pathlib import Path
from pydantic import BaseModel


class KernelConfig(BaseModel):
    url: str
    ref: str
    depth: int = 1
    dir: str | Path | None = None


class PatchesConfig(BaseModel):
    url: str
    ref: str
    dir: str | Path | None = None


class Project(BaseModel):
    dir: str | Path
    kernel: KernelConfig
    patches: PatchesConfig


@dataclass
class Context:
    verbose: bool
    config: Project
