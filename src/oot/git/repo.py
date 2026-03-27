from pathlib import Path


class Repo:
    def __init__(self, path: Path):
        self.path = path

    def git(self, *args):
        from .core import git

        return git(self.path, *args)

    def get_origin(self):
        from .inspect import get_origin

        return get_origin(self)
