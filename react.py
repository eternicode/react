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
from time import time


parser = argparse.ArgumentParser(
    description="Launch a script if specified files change."
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
parser.add_argument(
    "-I", "--replace-str",
    default="{}",
    help=(
        "Replace occurrences of REPLACE_STR in COMMAND with the triggering "
        "file's full path.  Default: {}"
    )
)
parser.add_argument(
    "-L", "--limit",
    type=int,
    help="Rate-limit calls to COMMAND to one every LIMIT seconds"
)
parser.add_argument(
    "-q", "--quiet",
    action="store_true", help="Suppress standard output"
)
parser.add_argument(
    "directory", help="The directory which is recursively monitored"
)
parser.add_argument("command", help="Command to execute upon reaction")


class Options:
    __slots__ = (
        [action.dest for action in parser._actions] +
        ['include', 'exclude']
    )

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
        self.trigger_timestamp = 0

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
            ts = time()
            if self.o.limit and ts - self.trigger_timestamp < self.o.limit:
                return
            self.trigger_timestamp = ts

            args = self.o.command.replace(self.o.replace_str, target).split()
            if self.o.quiet:
                subprocess.call(args, stdout=subprocess.PIPE)
            else:
                print("executing script: " + " ".join(args))
                subprocess.call(args)
                print("------------------------")
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
