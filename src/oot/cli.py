import logging
import os
from pathlib import Path

import click
import yaml

import oot.commands as commands
from oot.config import Project

logger = logging.getLogger("oot")
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
@click.option("--verbose", "-v", count=True)
def cli(ctx, config, verbose):
    level = logging.WARNING

    if verbose == 1:
        level = logging.INFO
    if verbose == 2:
        level = logging.DEBUG

    logging.basicConfig(level=level, format="%(message)s%")

    default_path = Path("./oot.yml")
    config_path = Path(config)

    if not config_path.exists():
        if config_path == default_path:
            raise click.ClickException(
                "No config file found.\n"
                "Expected default at ./oot.yml\n\n"
                "Use --config to specify a custom file."
            )
        else:
            raise click.ClickException(f"Config file not found: {config_path}")

    try:
        with open(config) as cfg:
            data = yaml.safe_load(cfg)
    except Exception as e:
        raise click.ClickException(f"Failed to read config: {e}")

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


@cli.command()
@click.option(
    "--force",
    "-f",
    is_flag=True,
    # TODO: improve this message
    help="clone repos to specified directories, even if they're not empty",
)
@pass_project
def fetch(project, force):
    try:
        commands.fetch(project, force)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command()
@click.argument("target")
@pass_project
def path(project, target):
    try:
        commands.path(project, target)
    except Exception as e:
        raise click.ClickException(str(e))


@cli.command(
    context_settings=dict(
        ignore_unknown_options=True,
        allow_extra_args=True,
    )
)
@click.pass_context
@pass_project
def git(project, ctx):
    commands.git(project, ctx.args)
