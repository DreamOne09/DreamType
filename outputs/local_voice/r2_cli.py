"""Private R2 setup, sync, verification and non-overwriting restore."""
import argparse
import getpass
import json
import time
from pathlib import Path
from contextlib import closing
from backup import create, export_deletions
from r2_config import configure, read_config, client_for, atomic_json
from r2_sync import sync_latest, restore_latest
from process_lock import exclusive


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('configure', 'enable', 'disable', 'sync', 'verify', 'restore'))
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--account-id'); parser.add_argument('--bucket')
    parser.add_argument('--destination', type=Path)
    parser.add_argument('--recovery-key', type=Path)
    parser.add_argument('--accept-stale-ledger', action='store_true')
    args = parser.parse_args(); root = args.root.resolve()
    if args.action == 'configure':
        if not args.account_id or not args.bucket: parser.error('configure requires --account-id and --bucket')
        configure(root, args.account_id, args.bucket, getpass.getpass('R2 Access Key ID: '),
                  getpass.getpass('R2 Secret Access Key: '))
        print('R2 credentials protected with Windows DPAPI. Automatic sync remains disabled.')
        return 0
    config = read_config(root)
    if args.action == 'disable':
        config['enabled'] = False; atomic_json(root / 'work/r2-config.json', config)
        print('Automatic R2 synchronization disabled; existing backups retained.')
        return 0
    if args.action == 'restore' and args.destination is None: parser.error('restore requires --destination')
    key = args.recovery_key or root / 'work/backup-recovery.key'
    with closing(client_for(root, config)) as client:
        if args.action in ('sync', 'enable'):
            with exclusive(root / 'work/maintenance.lock'):
                archive = create(root); ledger = export_deletions(root); now = time.time()
                status_path = root / 'work/maintenance-status.json'
                try: state = json.loads(status_path.read_text(encoding='utf-8'))
                except (OSError, ValueError): state = {}
                state.update(last_backup=now, backup_file=archive.name, last_backup_verified=now,
                             backup_verified_file=archive.name, last_deletion_export=now)
                atomic_json(status_path, state)
                result = sync_latest(client, config['bucket'], root, archive, key, ledger)
                state.update(last_r2_sync=result['checked_at'], r2_ledger_at=result['ledger_at'],
                             r2_backup_file=archive.name, r2_archive_sha256=result['archive_sha256'],
                             r2_deletion_export=now)
                if args.action == 'enable':
                    config['enabled'] = True; atomic_json(root / 'work/r2-config.json', config)
                state['r2_enabled'] = config['enabled']; atomic_json(status_path, state)
        else:
            result = restore_latest(client, config['bucket'], root, key,
                destination=args.destination if args.action == 'restore' else None,
                accept_stale=args.accept_stale_ledger)
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as error:
        # SDK exception strings can include endpoints/request details. Do not
        # leak these into scheduled logs or offer a false success status.
        print('R2 operation failed (' + type(error).__name__ + '). Check configuration, credentials and ledger freshness.')
        raise SystemExit(1)
