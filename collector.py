#!/usr/bin/env python
from csv import excel

import os
import subprocess
from collections import defaultdict
import difflib

PROJECT_ROOT = "/Users/jcwu/repos/cassandra"

def get_checkout_list(filename):
  f = open(filename)
  result = []
  for line in f.readlines():
    line = line.strip()
    if line.startswith("#"):
      continue
    result.append(line)
  return result


def parse_result(string):
  idx = string.find(":")
  filename = string[:idx]
  exception = string[idx + 1:].replace("throw new InvalidRequestException", "")\
                              .replace("throw new org.apache.cassandra.exceptions.InvalidRequestException", "")\
                              .strip()
  return (filename, exception)


def collect_exception(path, exception_string='new\ .*InvalidRequestException'):
  result = subprocess.check_output(["grep", "-r", exception_string, path])
  set_dict = defaultdict(set)
  for line in result.splitlines():
    (filename, exception) = parse_result(line)
    if filename != "":
      set_dict[filename].add(exception)
  return set_dict

def checkout(to_checkout):
  print "checkout to ", to_checkout
  subprocess.call(["git", "checkout", to_checkout])

def compare_digest(from_digest, to_digest):

  from_files = set(from_digest.keys())
  to_files = set(to_digest.keys())

  add_files = to_files - from_files
  delete_files = from_files - to_files
  common_files = from_files & to_files

  if len(add_files) > 0:
    # print "files added "
    for f in add_files:
      print f, " (file added)"
      for sig in list(to_digest[f]):
        print "+ %s" % sig

  if len(delete_files) > 0:
    # print "files deleted"
    for f in delete_files:
      print f, " (file deleted)"
      for sig in list(from_digest[f]):
        print "- %s" % sig

  for common_file in common_files:
    file_printed = False
    from_signature = sorted(list(from_digest[common_file]))
    to_signature = sorted(list(to_digest[common_file]))

    diffs = difflib.ndiff(from_signature, to_signature)

    for d in diffs:
      if d.startswith("+") or d.startswith("-"):
        if not file_printed:
          print common_file
          file_printed = True
        print d

if __name__ == '__main__':
  checkout_list = get_checkout_list("list_to_checkout.txt")
  os.chdir(PROJECT_ROOT)
  exception_map = {}

  for to_checkout in checkout_list:
    checkout(to_checkout)
    exception_digest = collect_exception(os.path.join(PROJECT_ROOT, "src"))
    exception_map[to_checkout] = exception_digest

  for i in range(len(checkout_list) - 1):
    print ""
    print "=== %s -> %s ===" % (checkout_list[i], checkout_list[i+1])
    from_digest = exception_map[checkout_list[i]]
    to_digest = exception_map[checkout_list[i+1]]
    compare_digest(from_digest, to_digest)