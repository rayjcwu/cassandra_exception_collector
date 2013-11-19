#!/usr/bin/env python

import os
import subprocess
from collections import defaultdict
import difflib
import hashlib

import sqlite3
import argparse

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
      print filename

    print "  %s: %s " % (range_dict[k], k[1])

def hash_tuple(iterable):
  h = hashlib.sha1()
  for t in iterable:
    h.update(t)
  return h.hexdigest()

def remove_prefix(filename, prefix):
  return filename.replace(prefix, "")

def store_raw(**kwargs):
  con=kwargs['con']
  cur=kwargs['cur']
  exception_info_list=kwargs['exception_info_list']
  path_prefix=kwargs['path_prefix']

  cur.execute("""
              CREATE TABLE IF NOT EXISTS exception_info (
                exception_idx INT PRIMARY KEY,
                filename TEXT,
                message TEXT,
                start_version_idx INT,
                start_version TEXT,
                end_version_idx INT,
                end_version TEXT
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

  cur.execute("DELETE FROM raw_exception_info;")  # to avoid duplicate insertion
  con.commit()

  raw_insert = [
        (hash_tuple((remove_prefix(e.filename, path_prefix), e.version, e.message)),  # hash_idx
         remove_prefix(filename=e.filename, prefix=path_prefix),                      # filename
         e.version_idx,                                                               # version_idx
         e.version,                                                                   # version
         e.message)
        for e in exception_info_list]

  cur.executemany("""
                  INSERT INTO raw_exception_info (hash_idx, filename, version_idx, version, message)
                  VALUES(?, ?, ?, ?, ?);
                  """, raw_insert)
  con.commit()

def get_exception_id(**kwargs):
  con         = kwargs['con']
  cur         = kwargs['cur']
  version_idx = kwargs['version_idx']
  version     = kwargs['version']
  filename    = kwargs['filename']
  message     = kwargs['message']

  cur.execute("""
              SELECT exception_idx,
                     start_version_idx,
                     start_version,
                     end_version_idx,
                     end_version
              FROM exception_info
              WHERE filename = ?
              AND message = ?;
              """, (filename, message))
  r = cur.fetchall()
  if len(r) == 0:
    cur.execute("""
                INSERT INTO exception_info (
                    exception_idx,
                    filename,
                    message,
                    start_version_idx,
                    start_version,
                    end_version_idx,
                    end_version)
                VALUES (last_insert_rowid() + 1, ?, ?, ?, ?, ?, ?);
                """, (filename, message, version_idx, version, version_idx, version))
    con.commit()
    cur.execute("""
              SELECT exception_idx
              FROM exception_info
              WHERE filename = ?
              AND message = ?;
              """, (filename, message))

    rr = cur.fetchone()
    return rr[0]
  else:
    # update version range
    exception_idx     = r[0][0]
    start_version_idx = r[0][1]
    start_version     = r[0][2]
    end_version_idx   = r[0][3]
    end_version       = r[0][4]

    # print r

    if version_idx < start_version_idx:
      start_version_idx = version_idx
      start_version = version

    if version_idx > end_version_idx:
      end_version_idx = version_idx
      end_version = version

    # print end_version_idx, end_version
    cur.execute("""
                UPDATE exception_info
                SET start_version_idx = ?,
                    start_version     = ?,
                    end_version_idx   = ?,
                    end_version       = ?
                WHERE exception_idx   = ?;
                """, (start_version_idx,
                      start_version,
                      end_version_idx,
                      end_version,
                      exception_idx))
    con.commit()
    return exception_idx

def update_exception_idx(**kwargs):
  con = kwargs['con']
  cur = kwargs['cur']

  cur.execute("""
              SELECT hash_idx, filename, version_idx, version, message
              FROM raw_exception_info
              ORDER BY version_idx, filename, message;
              """)
  for result in cur.fetchall():
    hash_idx    = result[0]
    filename    = result[1]
    version_idx = result[2]
    version     = result[3]
    message     = result[4]

    e_idx = get_exception_id(con=con, cur=cur,
                             version_idx=version_idx,
                             version=version,
                             filename=filename,
                             message=message)
    cur.execute("""
                UPDATE raw_exception_info
                SET exception_idx = ?
                WHERE hash_idx = ?;
                """, (e_idx, hash_idx))

  con.commit()

def store_sqlite3(absolute_database_path, exception_info_list):
  """
  @type exception_info_list: list [ExceptionInfo]
  """
  con = None
  cur = None
  filename_prefix = os.path.join(os.path.join(os.getcwd(), 'src'), 'java') + os.sep
  print "source code root path:", filename_prefix

  try:
    con = sqlite3.connect(absolute_database_path)
    cur = con.cursor()

    # store raw exception info
    store_raw(con=con, cur=cur, exception_info_list=exception_info_list, path_prefix=filename_prefix)
    update_exception_idx(con=con, cur=cur)

  except sqlite3.Error, e:
    print "Sqlite3 Error %s" % e.args[0]

  finally:
    if cur:
      cur.close()
    if con:
      con.close()

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("-s", "--srcpath", help="absolute root path of Cassandra source code", default="/Users/jcwu/repos/cassandra")
  parser.add_argument("-l", "--listfile", help="list of versions to checkout", default="list_to_checkout.txt")

  args = parser.parse_args()

  try:
    checkout_list = get_checkout_list(args.listfile)
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
                                         version_idx=to_checkout_idx)
      exception_info_list.extend(exception_digest)

    print_version_evolution(exception_info_list)
    print_exception_range(exception_info_list)

    store_sqlite3(absolute_database_path, exception_info_list)
  except Exception, e:
    print e.message
    parser.print_help()