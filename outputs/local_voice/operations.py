"""Conservative, read-only operator signals; never a production certification."""
import math
import time

ERRORS = {
    'maintenance_not_run': '尚未取得維護紀錄',
    'host_restart_failed': '主機服務自動恢復失敗',
    'tunnel_restart_failed': '手機連線通道自動恢復失敗',
    'backup_or_copy_failed': '備份建立或複製失敗',
    'deletion_export_or_copy_failed': '刪除紀錄匯出或複製失敗',
    'r2_sync_failed': 'R2 上傳、下載核對或還原驗證失敗，請檢查憑證與主機',
}

def summarize(maintenance, sync_configured=False, now=None):
    now = time.time() if now is None else now
    state = maintenance if isinstance(maintenance, dict) else {}
    def recent(field, limit):
        value = state.get(field)
        return type(value) in (int, float) and math.isfinite(value) and value > 0 and 0 <= now-value <= limit
    fresh = recent('checked_at', 900)
    checks = []
    def add(code, title, ok, good, bad):
        checks.append({'code': code, 'title': title, 'state': 'ok' if ok else 'attention',
                       'detail': good if ok else bad})
    add('maintenance', '自動維護', fresh, '最近 15 分鐘內有檢查', '超過 15 分鐘未更新或尚無有效紀錄，請檢查主機排程')
    add('engine', '語音與翻譯服務', fresh and state.get('ready') is True,
        '最近一次維護檢查正常', '需要確認主機與模型服務；舊紀錄不能代表目前正常')
    add('tunnel', '手機連線', fresh and state.get('tunnel_ready') is True,
        '最近一次通道檢查正常', '需要確認連線通道；重新啟動後網址可能改變')
    add('backup', '本機加密備份', recent('last_backup', 129600),
        '最近 36 小時內有成功備份紀錄', '超過 36 小時未成功備份或尚無紀錄，請檢查備份工作')
    verified = (recent('last_backup_verified',129600) and isinstance(state.get('backup_file'),str) and bool(state.get('backup_file'))
                and state.get('backup_verified_file')==state.get('backup_file'))
    add('backup_restore','備份還原驗證',verified,
        '這份備份已在本機記憶體通過還原準備驗證；尚不代表雲端可恢復',
        '尚無這份備份的近期還原驗證，不能只憑檔案存在判定可恢復')
    add('deletions', '刪除紀錄', recent('last_deletion_export', 900),
        '最近 15 分鐘內有成功匯出紀錄', '刪除紀錄未更新，還原前務必取得最新紀錄')
    free=state.get('disk_free_bytes')
    valid_space=type(free) is int and free>=0 and fresh
    storage_ok=valid_space and free>=5*1024**3
    storage_detail=('可用空間約 %.1f GB；低於 5 GB，請釋放空間或規劃搬移資料，避免錄音與備份寫入失敗' % (free/1024**3)
                    if valid_space else '尚無近期磁碟空間紀錄，請檢查主機')
    add('storage','主機儲存空間',storage_ok,
        '可用空間至少 5 GB，仍需留意模型與備份成長',storage_detail)
    available=state.get('memory_available_bytes');total=state.get('memory_total_bytes')
    valid_memory=(fresh and type(available) is int and type(total) is int and 0<=available<=total and total>0)
    memory_ok=valid_memory and available>=1024**3 and available/total>=0.1
    memory_detail=('可用記憶體約 %.1f GB；偏低可能造成模型變慢或逾時。請檢查其他程式用量，勿僅憑服務啟動判定可正常翻譯' % (available/1024**3)
        if valid_memory else '尚無近期有效記憶體紀錄，請檢查主機維護工作')
    add('memory','主機記憶體',memory_ok,
        '最近檢查尚有至少 1 GB 且 10% 可用記憶體；仍需以實際辨識及翻譯測試確認速度',memory_detail)
    files=state.get('backup_inventory')
    fields=('encrypted_archive_files','legacy_zip_files','incomplete_files','total_bytes','skipped_links','read_errors')
    valid_files=(fresh and isinstance(files,dict) and all(type(files.get(key)) is int and 0<=files[key]<2**63 for key in fields))
    file_detail=('本機 %d 份備份，合計約 %.1f MB；舊版 ZIP %d、未完成檔 %d、略過連結 %d、讀取錯誤 %d。盤點不會刪除檔案，也不代表內容已驗證' %
        (files['encrypted_archive_files'],files['total_bytes']/1024**2,files['legacy_zip_files'],files['incomplete_files'],files['skipped_links'],files['read_errors'])
        if valid_files else '尚無近期有效備份盤點，請等待維護工作或檢查主機')
    file_ok=(valid_files and files['encrypted_archive_files']>0 and all(files[key]==0 for key in ('legacy_zip_files','incomplete_files','skipped_links','read_errors')))
    add('backup_files','備份檔案盤點',file_ok,file_detail,file_detail)
    copied = sync_configured and recent('last_backup_copy', 129600) and recent('last_deletion_copy', 900)
    copy_verified = (copied and recent('last_backup_copy_verified',129600)
        and state.get('last_backup_copy_verified')==state.get('last_backup_copy')
        and bool(state.get('backup_file')) and state.get('backup_copy_verified_file')==state.get('backup_file')
        and recent('last_deletion_copy_verified',900)
        and state.get('last_deletion_copy_verified')==state.get('last_deletion_copy')==state.get('last_deletion_export'))
    remote_ok=(state.get('r2_enabled') is True and recent('last_r2_sync',900)
        and recent('r2_ledger_at',900) and state.get('r2_backup_file')==state.get('backup_file')
        and bool(state.get('backup_file')) and state.get('r2_deletion_export')==state.get('last_deletion_export')
        and 'r2_sync_failed' not in state.get('errors',[])) if isinstance(state.get('errors',[]),list) else False
    if state.get('r2_enabled') is True:
        add('r2','R2 雲端備份',remote_ok,
            '目前快照與近期刪除紀錄已由 R2 下載、核對並通過記憶體還原驗證；金鑰仍須另行保管',
            '目前備份或最新刪除紀錄尚無近期 R2 驗證，請檢查主機排程及憑證')
    checks.append({'code': 'offsite', 'title': '異機備援', 'state': 'unverified',
        'detail': 'R2 下載驗證已通過；另台電腦的完整復原與獨立金鑰保管仍需驗收' if remote_ok else
        ('同步資料夾的備份與最新刪除紀錄已核對內容；雲端上傳與異機還原仍需驗證' if copy_verified else
                   '有同步資料夾複製紀錄，但尚無目前備份與最新刪除紀錄的內容核對；請重新複製驗證' if copied else
                   '同步資料夾的備份或刪除紀錄複製未更新，請檢查同步工作' if sync_configured else
                   '尚未設定同步資料夾；目前只有本機備份')})
    errors = state.get('errors', [])
    if not isinstance(errors, list):
        errors = ['invalid_maintenance_record']
    messages = [ERRORS.get(error, '維護紀錄包含未識別的錯誤，請檢查主機')
                if isinstance(error, str) else '維護紀錄格式異常' for error in errors]
    return {'checks': checks, 'errors': messages,
            'needs_attention': bool(messages) or any(item['state'] != 'ok' for item in checks)}
