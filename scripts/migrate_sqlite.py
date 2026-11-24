"""Import a verified old SQLite snapshot into an empty cloud workspace."""
import argparse
import sqlite3
from pathlib import Path
from src.database import connect, initialize_database

TABLES = ('applications','planner_tasks','candidate_profile','mentor_messages','roadmap_steps')

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot', type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    with sqlite3.connect(args.snapshot.resolve().as_uri() + '?mode=ro', uri=True) as old:
        if old.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
            raise SystemExit('SQLite integrity check failed')
        data = {}
        for table in TABLES:
            if not old.execute('SELECT 1 FROM sqlite_master WHERE type=? AND name=?', ('table',table)).fetchone():
                continue
            cur = old.execute(f'SELECT * FROM {table}')
            data[table] = ([d[0] for d in cur.description], cur.fetchall())
            print(table, len(data[table][1]))
    if not args.apply:
        print('Preview only. Use --apply to import.')
        return
    if not any(rows for _,rows in data.values()):
        raise SystemExit('Snapshot has no records; choose an older backup.')
    initialize_database()
    from psycopg import sql
    with connect() as con:
        for table in (*TABLES, 'workspace_state'):
            con.execute(sql.SQL('LOCK TABLE {} IN ACCESS EXCLUSIVE MODE').format(sql.Identifier(table)))
            if con.execute(sql.SQL('SELECT 1 FROM {} LIMIT 1').format(sql.Identifier(table))).fetchone():
                raise RuntimeError('Destination is not empty; import cancelled without changing records.')
        for table,(cols,rows) in data.items():
            if not rows: continue
            query = sql.SQL('INSERT INTO {} ({}) VALUES ({})').format(sql.Identifier(table),sql.SQL(',').join(map(sql.Identifier,cols)),sql.SQL(',').join(sql.Placeholder() for _ in cols))
            con.cursor().executemany(query,rows)
            if table != 'candidate_profile':
                con.execute('SELECT setval(pg_get_serial_sequence(%s, %s), %s, true)', ('placementpilot.'+table,'id',max(row[cols.index('id')] for row in rows)))
    print('Import committed successfully.')

if __name__ == '__main__': main()
