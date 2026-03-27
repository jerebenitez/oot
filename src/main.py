import os
import click
import yaml

from config import Project
import commands

pass_project = click.make_pass_decorator(Project)


@click.group()
@click.version_option("1.0")
@click.pass_context
@click.option(
    "--config",
    "-c",
    default="./oot.yml",
    help="Specify a custom config file",
    type=click.Path(),
)
def oot(ctx, config):
    with open(config) as cfg:
        data = yaml.safe_load(cfg)

    cfg = Project.model_validate(data)
    cfg.patches.dir = (
        cfg.patches.dir
        if cfg.patches.dir is not None
        else os.path.join(cfg.dir, "patches")
    )
    cfg.kernel.dir = (
        cfg.kernel.dir
        if cfg.kernel.dir is not None
        else os.path.join(cfg.dir, "kernel")
    )

    ctx.obj = cfg


@oot.command()
@pass_project
def fetch(project):
    commands.fetch(project)


@oot.command()
@pass_project
def path(project):
    commands.path(project)


@oot.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    )
)
@click.pass_context
@pass_project
def git(project, ctx):
    commands.git(project, ctx.args)


if __name__ == "__main__":
    oot()
