#!/usr/bin/python3

import click

from .telegram import launch_telegram


@click.group()
def sauron(*args, **kwargs):
    pass

@sauron.command()
@click.argument('filename', type=click.Path(exists=True))
def telegram(filename):
    launch_telegram(filename)


