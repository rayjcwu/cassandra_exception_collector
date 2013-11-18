#!/usr/bin/env python
from csv import excel

import os
import subprocess
from collections import defaultdict
import difflib

PROJECT_ROOT = "/Users/jcwu/repos/cassandra"

class ExceptionInfo:
  def __init__(self, filename, message, version, version_idx):
    self.filename = filename
    self.message = message
    self.version = version
    self.version_idx = version_idx

  def __str__(self):
    return "%s %s %s" % (self.filename, self.message, self.version)

  def __repr__(self):
    return self.__str__()

def get_checkout_list(filename):
  """
  Return a list of versions (tags or branches) to checkout
  """
  f = open(filename)
  result = []
  for line in f.readlines():
    line = line.strip()
    if line.startswith("#"):
      continue
    result.append(line)
  return result


def parse_result(string):
  """
  Return filename and exception from this grep output result
  """
  idx = string.find(":")
  filename = string[:idx]
  message = string[idx + 1:].replace("throw new InvalidRequestException", "")\
                              .replace("throw new org.apache.cassandra.exceptions.InvalidRequestException", "")\
                              .strip()
  return (filename, message)

def collect_exception(**kwargs):
  """
  Collect all exception information, store as a list of ExceptionInfo
  """

  exception_string='new\ .*InvalidRequestException'
  if 'exception_string' in kwargs:
    exception_string = kwargs['exception_string']

  path = kwargs['path']
  version = kwargs['version']
  version_idx = kwargs['version_idx']

  result = subprocess.check_output(["grep", "-r", exception_string, path])
  exception_info_list = []
  for line in result.splitlines():
    (filename, message) = parse_result(line)
    if filename != "":
      exception_info_list.append(ExceptionInfo(filename, message, version, version_idx))
  return exception_info_list

def checkout(to_checkout):
  """
  Checkout to particular versoin
  """
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

def group_by_version(exception_info_list):
  """
  @type exception_info_list: list [ExceptionInfo]
  """
  by_ver_tmp = defaultdict(set)
  for e in exception_info_list:
    by_ver_tmp[e.version].add(e)

  by_ver = {}
  for ver, all_exceptions_in_one_ver in by_ver_tmp.items():
    by_filename = defaultdict(set)
    for excpt in all_exceptions_in_one_ver:
      by_filename[excpt.filename].add(excpt.message)

    by_ver[ver] = by_filename

  return by_ver


if __name__ == '__main__':
  checkout_list = get_checkout_list("list_to_checkout.txt")
  os.chdir(PROJECT_ROOT)
  exception_map = {}

  exception_info_list = []
  for to_checkout_idx in range(len(checkout_list)):
    to_checkout = checkout_list[to_checkout_idx]
    checkout(to_checkout)
    exception_digest = collect_exception(path=os.path.join(PROJECT_ROOT, "src"),
                                         version=to_checkout,
                                         version_idx=to_checkout_idx)
    exception_info_list.extend(exception_digest)

  # group_by_version
  by_version = group_by_version(exception_info_list)
  # print exception_info_list

  for i in range(len(checkout_list) - 1):
    print ""
    print "=== %s -> %s ===" % (checkout_list[i], checkout_list[i+1])
    from_digest = by_version[checkout_list[i]]
    to_digest = by_version[checkout_list[i+1]]
    compare_digest(from_digest, to_digest)