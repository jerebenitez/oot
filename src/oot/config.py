from pydantic import BaseModel


class KernelConfig(BaseModel):
    url: str
    ref: str
    depth: int = 1
    dir: str | None = None


class PatchesConfig(BaseModel):
    url: str
    ref: str
    dir: str | None = None


class Project(BaseModel):
    dir: str
    kernel: KernelConfig
    patches: PatchesConfig
