import unittest
from operations import summarize


class OperationsTests(unittest.TestCase):
    def states(self, report):
        return {item['code']: item['state'] for item in report['checks']}

    def test_stale_maintenance_cannot_claim_service_is_healthy(self):
        data={'checked_at':100,'ready':True,'tunnel_ready':True,'last_backup':100,
              'last_deletion_export':100,'errors':[]}
        report=summarize(data,now=1100)
        states=self.states(report)
        self.assertEqual(states['engine'],'attention')
        self.assertEqual(states['tunnel'],'attention')
        self.assertEqual(states['deletions'],'attention')
        self.assertEqual(states['backup'],'ok')

    def test_sync_copy_is_never_cloud_verification(self):
        state={key:100 for key in ('checked_at','last_backup','last_deletion_export','last_backup_copy','last_deletion_copy')}
        state.update(ready=True,tunnel_ready=True,errors=[],disk_free_bytes=10*1024**3)
        state.update(last_backup_verified=100,backup_file='a.dtbackup',backup_verified_file='a.dtbackup')
        report=summarize(state,True,now=110)
        self.assertEqual(self.states(report)['offsite'],'unverified')
        self.assertTrue(report['needs_attention'])
        self.assertTrue(all(item['state']=='ok' for item in report['checks'] if item['code']!='offsite'))

    def test_copy_status_requires_current_backup_and_latest_ledger(self):
        state={key:100 for key in ('last_backup_copy','last_deletion_copy','last_backup_copy_verified',
                                  'last_deletion_copy_verified','last_deletion_export')}
        state.update(backup_file='a.dtbackup',backup_copy_verified_file='a.dtbackup')
        def detail():return next(item['detail'] for item in summarize(state,True,now=110)['checks'] if item['code']=='offsite')
        self.assertIn('已核對內容',detail())
        state['backup_file']='b.dtbackup'
        self.assertIn('尚無目前',detail())
        state['backup_file']='a.dtbackup';state['last_deletion_export']=105
        self.assertIn('尚無目前',detail())
        state['last_deletion_export']=100;del state['last_backup_copy_verified']
        self.assertIn('尚無目前',detail())

    def test_old_verification_cannot_certify_a_new_backup(self):
        state={'last_backup':100,'last_backup_verified':100,'backup_file':'new.dtbackup',
               'backup_verified_file':'old.dtbackup'}
        self.assertEqual(self.states(summarize(state,now=110))['backup_restore'],'attention')
        state['backup_verified_file']='new.dtbackup'
        self.assertEqual(self.states(summarize(state,now=110))['backup_restore'],'ok')
        self.assertEqual(self.states(summarize(state,now=150000))['backup_restore'],'attention')

    def test_malformed_missing_future_and_old_backup_remain_attention(self):
        for value in (None,[],{'checked_at':float('nan')},{'checked_at':True},
                      {'checked_at':5000},{'checked_at':'100'}):
            self.assertEqual(self.states(summarize(value,now=1100))['maintenance'],'attention')
        report=summarize({'last_backup':1,'errors':['backup_or_copy_failed',{}]},now=150000)
        self.assertEqual(self.states(report)['backup'],'attention')
        self.assertIn('備份建立或複製失敗',report['errors'])
        self.assertEqual(len(report['errors']),2)

    def test_disk_capacity_is_reported_without_treating_old_values_as_current(self):
        for value in (None,True,-1,3*1024**3):
            report=summarize({'checked_at':100,'disk_free_bytes':value},now=110)
            self.assertEqual(self.states(report)['storage'],'attention')
        self.assertEqual(self.states(summarize({'checked_at':100,'disk_free_bytes':6*1024**3},now=110))['storage'],'ok')
        self.assertEqual(self.states(summarize({'checked_at':100,'disk_free_bytes':6*1024**3},now=2000))['storage'],'attention')

if __name__=='__main__':unittest.main()
