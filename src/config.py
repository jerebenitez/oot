from pydantic import BaseModel


class KernelConfig(BaseModel):
    url: str
    ref: str
    dir: str = "kernel"


class PatchesConfig(BaseModel):
    url: str
    ref: str
    dir: str = "patches"


class Project(BaseModel):
    dir: str
    kernel: KernelConfig
    patches: PatchesConfig
