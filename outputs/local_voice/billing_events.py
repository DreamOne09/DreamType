"""Privacy-minimal operator signals, not a refund case inbox."""
import time

MESSAGES={
    'refund_review_pending':'最近 24 小時收到待審查退款通知，請立即到 Google 管理工具確認並處理；系統尚未提交退款建議。',
    'notification_unsupported':'最近 24 小時收到尚未支援的付款通知，請檢查 Pub/Sub 重送或失敗佇列。',
    'purchase_unbound':'最近 24 小時有付款通知找不到已綁定購買，請確認手機恢復購買與 Pub/Sub 重送狀態。',
}

def record(store,code,*,now=None):
    if code not in MESSAGES:raise ValueError('Unknown billing signal')
    now=time.time() if now is None else now
    action='billing_notice_'+code
    with store.db() as db:
        db.execute('BEGIN IMMEDIATE')
        row=db.execute('SELECT MAX(created) FROM audit WHERE action=?',(action,)).fetchone()
        # Coalesce retries per type per minute, not per person or purchase.
        if row[0] is not None and 0<=now-row[0]<60:return
        db.execute('INSERT INTO audit(created,action,uid) VALUES(?,?,NULL)',(now,action))

def recent(db,now):
    result=[]
    for code,message in MESSAGES.items():
        row=db.execute('SELECT MAX(created) FROM audit WHERE action=? AND created>=? AND created<=?',
            ('billing_notice_'+code,now-86400,now)).fetchone()
        if row[0] is not None:result.append({'code':code,'message':message,'last_seen':row[0]})
    return result
