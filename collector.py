#!/usr/bin/env python

import os
import subprocess
from collections import defaultdict, OrderedDict
import difflib
import hashlib
import sqlite3
import argparse
import myutil
import re

class Range:
  def __init__(self, version, version_idx):
    self.start_version_idx = version_idx
    self.start_version = version
    self.end_version_idx = version_idx
    self.end_version = version

  def update(self, version, version_idx):
    if version_idx < self.start_version_idx:
      self.start_version = version
      self.start_version_idx = version_idx

    if version_idx > self.end_version_idx:
      self.end_version = version
      self.end_version_idx = version_idx

  def __str__(self):
    return "%s => %s" % (self.start_version, self.end_version)

  __repr__ = __str__

class ExceptionInfo:
  def __init__(self, filename, message, version, version_idx):
    self.filename = filename
    self.message = message
    self.version = version
    self.version_idx = version_idx

  def __str__(self):
    return "%s %s %s" % (self.filename, self.message, self.version)

  __repr__ = __str__


def collect_exception(**kwargs):
  """
  Collect all exception information, store as a list of ExceptionInfo
  """
  path = kwargs['path']
  version = kwargs['version']
  version_idx = kwargs['version_idx']
  exclude_pattern = kwargs['exclude_pattern']

  path_prefix = os.path.join(path, "java") + os.sep

  exception_info_list = []
  for filename, message in myutil.mygrep(path, exclude_regex=exclude_pattern):
    if filename != "":
      exception_info_list.append(ExceptionInfo(filename.replace(path_prefix, ""), message, version, version_idx))
  return exception_info_list


def checkout(to_checkout):
  """
  Checkout to particular versoin
  """
  # print "checkout to ", to_checkout
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


def print_version_evolution(exception_info_list):
  # group_by_version
  by_version = group_by_version(exception_info_list)
  for i in range(len(checkout_list) - 1):
    print ""
    print "=== %s -> %s ===" % (checkout_list[i], checkout_list[i + 1])
    from_digest = by_version[checkout_list[i]]
    to_digest = by_version[checkout_list[i + 1]]
    compare_digest(from_digest, to_digest)


def print_exception_range(exception_info_list):
  """
  @type exception_info_list: list [ExceptionInfo]
  """
  range_dict = {}
  for e in exception_info_list:
    dict_key = (e.filename, e.message)
    if dict_key in range_dict:
      range_dict[dict_key].update(e.version, e.version_idx)
    else:
      range_dict[dict_key] = Range(e.version, e.version_idx)

  filename = ""
  for k in sorted(list(range_dict.keys())):
    if k[0] != filename:
      filename = k[0]
      print ""
      print filename

    print "  %s: %s " % (range_dict[k], k[1])


def hash_tuple(iterable):
  h = hashlib.sha1()
  for t in iterable:
    h.update(t)
  return h.hexdigest()


def reset_tables(**kwargs):
  con=kwargs['con']
  cur=kwargs['cur']

  cur.execute("DROP TABLE IF EXISTS raw_exception_info;")
  con.commit()
  cur.execute("DROP TABLE IF EXISTS exception_info;")
  con.commit()
  cur.execute("""
              CREATE TABLE IF NOT EXISTS exception_info (
                exception_idx INT PRIMARY KEY,
                filename TEXT,
                message TEXT,
                start_version_idx INT,
                start_version TEXT,
                end_version_idx INT,
                end_version TEXT,
                update_idx INT
              );
              """)
  con.commit()
  cur.execute("""
              CREATE TABLE IF NOT EXISTS raw_exception_info (
                hash_idx TEXT,
                filename TEXT,
                version_idx INT,
                version TEXT,
                message TEXT,
                exception_idx INT,
                FOREIGN KEY(exception_idx) REFERENCES exception_info(exception_idx) ON UPDATE CASCADE ON DELETE CASCADE
              );
              """)
  con.commit()


def store_raw(**kwargs):
  con=kwargs['con']
  cur=kwargs['cur']
  exception_info_list=kwargs['exception_info_list']

  raw_insert = [
        (hash_tuple((e.filename, e.version, e.message)),  # hash_idx
         e.filename,                                    # filename
         e.version_idx,                                 # version_idx
         e.version,                                     # version
         e.message)
        for e in exception_info_list]

  cur.executemany("""
                  INSERT INTO raw_exception_info (hash_idx, filename, version_idx, version, message)
                  VALUES(?, ?, ?, ?, ?);
                  """, raw_insert)
  con.commit()


def build_version_range(exception_info_list):
  """
  @type exception_info_list: list [ExceptionInfo]
  """
  od = OrderedDict()

  for e in exception_info_list:
    key = (e.filename, e.message)

    if key in od:
      od.get(key).update(e.version, e.version_idx)
    else:
      od[key] = Range(e.version, e.version_idx)

  return od


def store_version_range(**kwargs):
  con = kwargs['con']
  cur = kwargs['cur']
  version_range_map = kwargs['version_range_map']
  """
  @type version_range_map: dict[(filename, message), Range]
  """

  exception_idx_map = {}
  i = 0
  for key, value in version_range_map.items():
    i += 1
    exception_idx_map[key] = i

  exception_info_batch = [
    (exception_idx_map[k],  # exception_idx
     k[0],                  # filename
     k[1],                  # message
     v.start_version_idx,
     v.start_version,
     v.end_version_idx,
     v.end_version)
    for k, v in version_range_map.items()]

  cur.executemany("""
                  INSERT INTO exception_info
                  (exception_idx,
                   filename,
                   message,
                   start_version_idx,
                   start_version,
                   end_version_idx,
                   end_version) VALUES (?, ?, ?, ?, ?, ?, ?);
                  """, exception_info_batch)
  con.commit()

  raw_exception_info_label = [(v, k[0], k[1]) for k, v in exception_idx_map.items()]
  cur.executemany("""
                  UPDATE raw_exception_info
                  SET exception_idx = ?
                  WHERE filename = ? AND message = ?;
                  """, raw_exception_info_label)
  con.commit()

def store_sqlite3(absolute_database_path, exception_info_list):
  """
  @type exception_info_list: list [ExceptionInfo]
  """
  con = None
  cur = None

  try:
    con = sqlite3.connect(absolute_database_path)
    cur = con.cursor()

    reset_tables(con=con, cur=cur)
    store_raw(con=con, cur=cur, exception_info_list=exception_info_list)
    filename_message_version_range_map = build_version_range(exception_info_list)
    store_version_range(con=con, cur=cur, version_range_map=filename_message_version_range_map)

  except sqlite3.Error, e:
    print "Sqlite3 Error %s" % e.args[0]

  finally:
    if cur:
      cur.close()
    if con:
      con.close()


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("-s", "--srcpath", help="absolute root path of Cassandra source code", default="/home/jcwu/repos/cassandra")
  parser.add_argument("-l", "--listfile", help="list of versions to checkout", default="list_to_checkout.txt")
  parser.add_argument("-f", "--excludefile", help="list of pattern to be excluded", default="files_to_exclude.txt")

  args = parser.parse_args()

  try:
    exclude_pattern = None
    checkout_list = myutil.read_file_without_comment(args.listfile)
    exclude_list = myutil.read_file_without_comment(args.excludefile)
    if len(exclude_list) != 0:
        exclude_pattern = re.compile("|".join(["\\b" + p + "\\b" for p in exclude_list]))
    absolute_database_path = os.path.join(os.getcwd(), 'exceptions.db')

    project_root = args.srcpath
    os.chdir(project_root)
    exception_map = {}

    exception_info_list = []
    for to_checkout_idx in range(len(checkout_list)):
      to_checkout = checkout_list[to_checkout_idx]
      checkout(to_checkout)
      exception_digest = collect_exception(path=os.path.join(project_root, "src"),
                                           version=to_checkout,
                                           version_idx=to_checkout_idx,
                                           exclude_pattern=exclude_pattern)
      exception_info_list.extend(exception_digest)

    print_version_evolution(exception_info_list)
    print_exception_range(exception_info_list)

    store_sqlite3(absolute_database_path, exception_info_list)
  except Exception, e:
    print e.message
    parser.print_help()