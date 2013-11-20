cassandra_exception_collector
=============================

This script uses `git` to collect all `InvalidRequestException` and their message in cassandra source code.

Use `-s` option to specify the root path of Casssandra.

Edit `list_to_checkout.txt` to add tags/branches you are interested in.

It will output exceptions delta history and range information to console and store range information to sqlite database `exceptions.db`.
Check `output.txt` to see how the output looks like.

# Schema 

There are two tables in sqlite3 database. 

| Table | Column | Description |
| ----- | ------ | ----------- |
| raw_exception_info | hash_idx | calculated by (`filename`, `message`, `version`) |
| | filename | |
| | message | |
| | version_idx | #-th in `list_to_checkout.txt`. Only for comparison reason. |
| | version | string of the version |
| | exception_idx | this points to the unique index of Cassandra `InvalidRequestException` |
| exception_info | exception_idx | a unique index for Cassandra `InvalidRequestException` |
| | filename | | 
| | message | |
| | start_version_idx | |
| | start_version | this exception exists since this version |
| | end_version_idx | | 
| | end_version | this exception ends at this version. after you run `merge_exception.py`, this value will not be updated. |
| | update_idx | after you run `merge_exception.py`, this will point to the updated version of this exception | 
