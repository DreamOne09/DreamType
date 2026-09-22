"""Conservative, read-only operator signals; never a production certification."""
import math
import time

ERRORS = {
    'maintenance_not_run': '尚未取得維護紀錄',
    'host_restart_failed': '主機服務自動恢復失敗',
    'tunnel_restart_failed': '手機連線通道自動恢復失敗',
    'backup_or_copy_failed': '備份建立或複製失敗',
    'deletion_export_or_copy_failed': '刪除紀錄匯出或複製失敗',
}

def summarize(maintenance, sync_configured=False, now=None):
    now = time.time() if now is None else now
    state = maintenance if isinstance(maintenance, dict) else {}
    def recent(field, limit):
        value = state.get(field)
        return type(value) in (int, float) and math.isfinite(value) and 0 <= now-value <= limit
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
    add('deletions', '刪除紀錄', recent('last_deletion_export', 900),
        '最近 15 分鐘內有成功匯出紀錄', '刪除紀錄未更新，還原前務必取得最新紀錄')
    copied = sync_configured and recent('last_backup_copy', 129600) and recent('last_deletion_copy', 900)
    checks.append({'code': 'offsite', 'title': '異機備援', 'state': 'unverified',
        'detail': ('已複製至同步資料夾；雲端上傳與異機還原仍需驗證' if copied else
                   '同步資料夾的備份或刪除紀錄複製未更新，請檢查同步工作' if sync_configured else
                   '尚未設定同步資料夾；目前只有本機備份')})
    errors = state.get('errors', [])
    if not isinstance(errors, list):
        errors = ['invalid_maintenance_record']
    messages = [ERRORS.get(error, '維護紀錄包含未識別的錯誤，請檢查主機')
                if isinstance(error, str) else '維護紀錄格式異常' for error in errors]
    return {'checks': checks, 'errors': messages,
            'needs_attention': bool(messages) or any(item['state'] != 'ok' for item in checks)}
