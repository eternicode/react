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


parser = argparse.ArgumentParser(
    description="Launch a script if specified files change."
)
parser.add_argument(
    "directory", help="the directory which is recursively monitored"
)

parser.add_argument(
    "-i", "--include",
    dest="include_pattern", action="append",
    help=(
        "Only trigger the reaction if the triggering file's full path matches "
        "this shell pattern"
    )
)
parser.add_argument(
    "-e", "--exclude",
    dest="exclude_pattern", action="append",
    help=(
        "Do not trigger the reaction if the triggering file's full path "
        "matches this shell pattern"
    )
)
parser.add_argument(
    "-r", "--include-regex",
    action="append",
    help=(
        "Only trigger the reaction if the triggering file's full path matches "
        "this regular expression"
    )
)
parser.add_argument(
    "-x", "--exclude-regex",
    action="append",
    help=(
        "Do not trigger the reaction if the triggering file's full path "
        "matches this regular expression"
    )
)

parser.add_argument("script", help="the script that is executed upon reaction")


class Options:
    __slots__ = [action.dest for action in parser._actions]

options = Options()
args = parser.parse_args(namespace=options)


class Reload(Exception):
    pass


class Process(ProcessEvent):
    def __init__(self,  options):
        options.include = []
        if options.include_pattern:
            options.include += [
                re.compile(fnmatch.translate(include))
                for include in options.include_pattern
            ]
        if options.include_regex:
            options.include += map(re.compile, options.include)

        options.exclude = []
        if options.exclude_pattern:
            options.exclude += [
                re.compile(fnmatch.translate(exclude))
                for exclude in options.exclude_pattern
            ]
        if options.exclude_regex:
            options.exclude += map(re.compile, options.exclude)

        self.o = options

    def process_IN_CREATE(self, event):
        target = os.path.join(event.path, event.name)
        if os.path.isdir(target):
            raise Reload()

    def process_IN_DELETE(self, event):
        raise Reload()

    def handle(self, event):
        target = os.path.join(event.path, event.name)
        handle = True
        if self.o.include:
            handle &= any(
                include.search(target) for include in self.o.include
            )
        if self.o.exclude:
            handle &= not any(
                exclude.search(target) for exclude in self.o.exclude
            )
        if handle:
            args = self.o.script.replace("$f", target).split()
            print "executing script: " + " ".join(args)
            subprocess.call(args)
            print "------------------------"
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
