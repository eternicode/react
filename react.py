#!/usr/bin/env python

import argparse
import fnmatch
import os
import os.path
import re
import subprocess
import sys
from pyinotify import (
    WatchManager, ProcessEvent, Notifier,
    IN_DELETE, IN_CREATE, IN_CLOSE_WRITE, IN_MOVED_TO
)


class PatternAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        setattr(namespace, self.dest, fnmatch.translate(values))

parser = argparse.ArgumentParser(
    description="Launch a script if specified files change."
)
parser.add_argument(
    "directory", help="the directory which is recursively monitored"
)

group = parser.add_mutually_exclusive_group()
group.add_argument(
    "-r", "--regex",
    required=False,
    default=".*",
    help=(
        "Files only trigger the reaction if their name matches this regular "
        "expression"
    )
)
group.add_argument(
    "-p", "--pattern",
    required=False,
    dest="regex",
    action=PatternAction,
    help=(
        "Files only trigger the reaction if their name matches this shell "
        "pattern"
    )
)

parser.add_argument("script", help="the script that is executed upon reaction")


class Options:
    __slots__ = ["directory", "regex", "script"]

options = Options()
args = parser.parse_args(namespace=options)


class Reload(Exception):
    pass


class Process(ProcessEvent):
    def __init__(self,  options):
        self.regex = re.compile(options.regex)
        self.script = options.script

    def process_IN_CREATE(self, event):
        target = os.path.join(event.path, event.name)
        if os.path.isdir(target):
            raise Reload()

    def process_IN_DELETE(self, event):
        raise Reload()

    def handle(self, event):
        target = os.path.join(event.path, event.name)
        if self.regex.match(target):
            args = self.script.replace("$f", target).split()
            os.system("clear")
            sys.stdout.write("executing script: " + " ".join(args) + "\n")
            subprocess.call(args)
            sys.stdout.write("------------------------\n")
    process_IN_CLOSE_WRITE = handle
    process_IN_MOVED_TO = handle

while True:
    wm = WatchManager()
    process = Process(options)
    notifier = Notifier(wm, process)
    mask = IN_DELETE | IN_CREATE | IN_CLOSE_WRITE | IN_MOVED_TO
    wdd = wm.add_watch(options.directory, mask, rec=True)
    try:
        while True:
            notifier.process_events()
            if notifier.check_events():
                notifier.read_events()
    except Reload:
        notifier.stop()
        pass
    except KeyboardInterrupt:
        notifier.stop()
        break
