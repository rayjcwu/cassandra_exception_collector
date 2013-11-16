cassandra_exception_collector
=============================

This script uses `git` and `grep` to collect all `InvalidRequestException` and their status in cassandra source code.

Need to edit `PROJECT_ROOT` in `collector.py` to point to the path containing cassandra source code.

Edit `list_to_checkout.txt` to add tags/branches you are interested in.

You could find a sample output in `output.txt`.
