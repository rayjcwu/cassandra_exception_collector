import os
import re


def abs_path_collector(path):
    result = []
    for root, dirs, files in os.walk(path):
        java_files = [file for file in files if file.endswith(".java")]
        if len(java_files) > 0:
            # print "root: ", root
            # print java_files
            for java_file in java_files:
                result.append(os.path.join(root, java_file))
    return result


def extract_exception_message(filename):
    lines = open(filename).readlines()
    p1 = re.compile(r'\bthrow\b.*\bnew\b.*\bInvalidRequestException\b')
    results = []
    for i in range(len(lines)):
        line = lines[i].strip()
        if p1.search(line):
            while not line.endswith(";"):
                i += 1
                line += " " + lines[i].strip()
            to_insert = line.replace("throw new InvalidRequestException", "").replace("throw new org.apache.cassandra.exceptions.InvalidRequestException", "")

            if to_insert.find('"') >= 0:
                results.append(to_insert)

    return results


def mygrep(path):
    results = []
    for filename in abs_path_collector(path):
        for message in extract_exception_message(filename):
            results.append((filename, message))
    return results