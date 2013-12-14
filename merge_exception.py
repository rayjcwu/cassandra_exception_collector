#!/usr/bin/env python
import sqlite3


def merge_exception_idx(**kwargs):
    con = kwargs['con']
    cur = kwargs['cur']
    versions = kwargs['versions']
    """
    @type con: sqlite3.Connection
    @type cur: sqlite3.Cursor
    @type versions: list[str]
    """

    # find all exception_idx based on hash_idx
    # in table exception_info, exceptions already groupded by exception message, so their exception_idx will be the same
    exception_idxs = []
    for version in versions:
        cur.execute("SELECT exception_idx FROM raw_exception_info WHERE hash_idx = ?", (version, ))
        r = cur.fetchone()
        if not r or len(r) == 0:
            print "exceptoin %s doesn't exist" % (version)
            continue
        else:
            exception_idxs.append(r[0])

    exception_idxs.sort()

    to_update = [(exception_idxs[-1], idx) for idx in exception_idxs[:-1]]
    if len(to_update) > 0:
        cur.executemany("""
                    UPDATE raw_exception_info
                    SET exception_idx = ?
                    WHERE exception_idx = ?;
                    """, to_update)

        cur.executemany("""
                    UPDATE exception_info
                    SET update_idx = ?
                    WHERE exception_idx = ?;
                    """, to_update)

        con.commit()


def main():
    con = sqlite3.connect("exceptions.db")
    cur = con.cursor()

    filename = "exception_to_merge.txt"
    for line in open(filename).readlines():
        line = line.strip()
        if not line.startswith("#"):
            versions = line.split(" ")
            if len(versions) > 1:
                merge_exception_idx(con=con, cur=cur, versions=versions)

    if cur:
        cur.close()
    if con:
        con.close()

    print "done"


if __name__ == "__main__":
    main()
