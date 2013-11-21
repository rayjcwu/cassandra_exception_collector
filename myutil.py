import os
import re


def read_file_without_comment(filename):
    """
    read file and return file content line by line as a list
    without comment lines or empty lins
    """
    return [x.strip() for x in open(filename).readlines()
            if not x.strip().startswith("#")
        and len(x.strip()) != 0]


def abs_path_collector(path):
    """
    return all absolute file names for java files under given path
    """
    result = []
    for root, dirs, files in os.walk(path):
        result.extend([os.path.join(root, f) for f in files if f.endswith(".java")])
    return result


def extract_exception_message(filename):
    """
    extract all InvalidRequestException exception message for given file
    """
    lines = open(filename).readlines()
    p1 = re.compile(r'\bthrow\b.*\bnew\b.*\bInvalidRequestException\b')
    results = []
    for i in range(len(lines)):
        line = lines[i].strip()
        if p1.search(line):
            while not line.endswith(";"):
                i += 1
                line += " " + lines[i].strip()
            to_insert = line.replace("throw new InvalidRequestException", "") \
                .replace("throw new org.apache.cassandra.exceptions.InvalidRequestException", "")

            if to_insert.find('"') >= 0:
                results.append(to_insert[1:-2]) # strip (  and  );

    return results


def mygrep(path, exclude_regex=None):
    results = []
    for filename in abs_path_collector(path):
        if exclude_regex and exclude_regex.search(filename):
            print "exclude", filename
            continue
        for message in extract_exception_message(filename):
            results.append((filename, message))

    return results