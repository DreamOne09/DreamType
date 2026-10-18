"""Inspect account storage or explicitly prepare one offline schema step.

No server stop/start, configuration change, billing activation or automatic rollback.
Run from the candidate checkout, with an explicit installation --root.
"""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from billing_migration import TABLES as BILLING, validate_billing_schema, _require_offline, prepare_storage
from notification_migration import validate_notifications, prepare_notifications
from signin_migration import TABLES as SIGNIN, validate_signin, prepare_signin
from reauth_migration import TABLES as REAUTH, validate_reauth, prepare_reauth

STEPS={4:(9,prepare_storage),9:(10,prepare_notifications),10:(11,prepare_signin),11:(12,prepare_reauth)}
BASE={'users','sessions','jobs','results','audit','reset_codes','receipts','pending_audio','deletions'}


def inspect(root):
    root=Path(root).resolve();work=root/'work';database=work/'beta/accounts.sqlite3'
    # Do not accidentally write backups or keys outside the selected installation.
    for relative in ('work','work/beta','work/beta/accounts.sqlite3','work/backups',
                     'work/beta/admin.key','work/beta/billing.key','work/local-voice.key',
                     'work/backup-recovery.key','work/maintenance.lock'):
        if not (root/relative).resolve().is_relative_to(root):raise ValueError('Installation path escapes the selected root.')
    if not database.is_file():raise ValueError('Existing account database required; no installation was created.')
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True,timeout=1)) as db:
        db.execute('PRAGMA query_only=ON');db.execute('BEGIN')
        version=db.execute('PRAGMA user_version').fetchone()[0]
        if version not in (*STEPS,12):raise ValueError('Unsupported schema; do not attempt an in-place downgrade.')
        if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall():raise ValueError('Database integrity check failed.')
        tables={r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not BASE<=tables:raise ValueError('Incomplete base account storage.')
        future=set()
        if version<9:future.update(BILLING)
        if version<10:future.add('play_notifications')
        if version<11:future.update(SIGNIN)
        if version<12:future.update(REAUTH)
        if future&tables:raise ValueError('Partial or unexpected future schema tables; investigate before migration.')
        if version>=9:validate_billing_schema(db)
        if version>=10:validate_notifications(db)
        if version>=11:validate_signin(db)
        if version>=12:validate_reauth(db)
        counts={
            'active_jobs':db.execute("SELECT count(*) FROM jobs WHERE state IN ('queued','running')").fetchone()[0],
            'pending_audio':db.execute('SELECT count(*) FROM pending_audio').fetchone()[0],
            'unconfirmed_receipts':db.execute('SELECT count(*) FROM receipts WHERE confirmed=0').fetchone()[0],
        }
        paid=version>=9 and bool(db.execute('SELECT 1 FROM billing_mode WHERE required=1').fetchone())
    blockers=[name for name,count in counts.items() if count]
    if any(not p.is_file() for p in (work/'beta/admin.key',work/'local-voice.key')):blockers.append('backup_host_keys_missing')
    try:_require_offline(root)
    except ValueError:blockers.append('gateway_running')
    return {'version':version,'next_version':STEPS[version][0] if version in STEPS else None,
            'counts':counts,'billing_policy_required':paid,'blockers':blockers,
            'preflight_passed':version in STEPS and not blockers,'offline_confirmation_required':True,
            'scope':'read-only preflight; each migration rechecks under its write lock'}


def prepare(root,expected,target,*,offline_confirmed=False):
    if offline_confirmed is not True:raise ValueError('Confirm the host service and automatic restarts are stopped; process visibility alone cannot prove this.')
    report=inspect(root)
    if expected not in STEPS or STEPS[expected][0]!=target:raise ValueError('Select exactly one supported step: 4->9, 9->10, 10->11 or 11->12.')
    if report['version']!=expected:raise ValueError('Source version changed or this step already completed; inspect again.')
    if report['blockers']:raise ValueError('Preflight blocked: '+', '.join(report['blockers']))
    # These public entry points acquire maintenance/writer locks, verify pending
    # work again, create and restore-verify an encrypted snapshot, then commit DDL.
    result=STEPS[expected][1](Path(root).resolve())
    return {**result,'configuration_changed':False,'restart_performed':False,
            'next_action':'Inspect before the next step. Restart only with compatible code; restore into a new directory for rollback.'}


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('inspect','prepare'))
    parser.add_argument('--root',type=Path,required=True,help='Existing installation root, not its work directory')
    parser.add_argument('--offline-confirmed',action='store_true',help='Operator has stopped the host service and its automatic restarts')
    parser.add_argument('--from-version',type=int)
    parser.add_argument('--to-version',type=int)
    args=parser.parse_args(argv)
    if args.action=='prepare' and (args.from_version is None or args.to_version is None):parser.error('prepare requires --from-version and --to-version')
    if args.action=='inspect' and (args.from_version is not None or args.to_version is not None or args.offline_confirmed):parser.error('inspect does not take migration versions')
    try:result=inspect(args.root) if args.action=='inspect' else prepare(args.root,args.from_version,args.to_version,offline_confirmed=args.offline_confirmed)
    except (ValueError,sqlite3.Error,OSError) as error:
        print(json.dumps({'ok':False,'error':str(error),'action':'Do not restart or downgrade blindly; inspect the current version before retrying.'}));return 1
    except Exception:
        # A lock or unexpected operational failure may occur after a committed
        # step. Do not promise rollback and do not print credentials/tracebacks.
        print(json.dumps({'ok':False,'error':'Preparation could not complete. Inspect schema and backup state before retrying.'}));return 1
    print(json.dumps({'ok':True,**result}));return 0


if __name__=='__main__':raise SystemExit(main())
