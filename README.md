cassandra_exception_collector
=============================

This script uses `git` to collect all `InvalidRequestException` and their message in cassandra source code.

Use `-s` option to specify the root path of Casssandra.

Edit `list_to_checkout.txt` to add tags/branches you are interested in.

It will output exceptions delta history and range information to console and store range information to sqlite database `exceptions.db`.
Check `output.txt` to see how the output looks like.
