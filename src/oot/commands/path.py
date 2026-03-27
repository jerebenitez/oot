from oot.config import Project


def path(cfg: Project, target: str):
    if target == "patches":
        print(f"{cfg.patches.dir}")
    elif target == "kernel":
        print(f"{cfg.kernel.dir}")
    else:
        raise Exception(
            f"Unrecognized option: {target}\nValid options are: patches, kernel"
        )
