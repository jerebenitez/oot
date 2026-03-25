import click
import yaml

from config import Project

pass_project = click.make_pass_decorator(Project)


@click.group()
@click.version_option("1.0")
@click.option(
    "--config", "-c", default="./oot.yml", help="Specify a custom config file"
)
def oot(config):
    with open(config) as cfg:
        data = yaml.safe_load(cfg)

    config = Project.model_validate(data)
    print(config)


@oot.command()
def init():
    pass


if __name__ == "__main__":
    oot()
