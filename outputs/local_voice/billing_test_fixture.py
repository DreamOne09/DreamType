"""Synthetic unit fixture only; production must use prepare_storage offline."""
from beta_store import Store
from billing_migration import _upgrade

def prepared_store(path,policy=None):
    baseline=Store(path)
    with baseline.db() as db:
        db.execute('BEGIN IMMEDIATE')
        _upgrade(db)
    return Store(path,policy)


def notification_store(store):
    from notification_migration import _upgrade
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE');_upgrade(db)
    return store
