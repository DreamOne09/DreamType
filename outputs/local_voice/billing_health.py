"""Administrator-only aggregate billing health; no identities or tokens."""
import time


def snapshot(store,last,worker_alive,*,now=None):
    now=time.time() if now is None else now
    with store.db() as db:
        row=db.execute('''SELECT COUNT(*) AS subscriptions,
          COALESCE(SUM(p.ack_pending),0) AS pending_ack,
          COALESCE(SUM(CASE WHEN p.needs_refresh=1 OR p.checked_at<? OR p.checked_at>? THEN 1 ELSE 0 END),0) AS stale,
          COALESCE(SUM(CASE WHEN r.attempts>0 THEN 1 ELSE 0 END),0) AS retrying,
          COALESCE(SUM(CASE WHEN r.attempts>=5 THEN 1 ELSE 0 END),0) AS repeated_failures,
          COALESCE(SUM(CASE WHEN p.ack_pending=1 AND c.created<? THEN 1 ELSE 0 END),0) AS ack_over_hour
          FROM play_subscriptions p JOIN users u ON u.id=p.uid
          LEFT JOIN billing_retry r ON r.digest=p.digest AND r.revision=p.revision
          LEFT JOIN purchase_claims c ON c.provider='google_play' AND c.digest=p.digest
          WHERE u.enabled=1 AND NOT EXISTS(SELECT 1 FROM play_replacements e WHERE e.old_digest=p.digest)''',
          (now-store.entitlement_policy.max_age,now,now-3600)).fetchone()
    counts=dict(row);alerts=[]
    checked=last.get('checked_at')
    started=last.get('started_at')
    if checked is None and started is not None and now-started>600:
        alerts.append({'code':'worker_stale','message':'付款查驗啟動超過十分鐘仍未完成，請檢查主機。'})
    if not worker_alive:alerts.append({'code':'worker_stopped','message':'付款查驗工作未運行，請檢查主機服務。'})
    if last.get('state')=='failed':alerts.append({'code':'worker_failed','message':'最近一輪付款查驗異常，請檢查設定與連線。'})
    if checked is not None and (checked>now or now-checked>600):alerts.append({'code':'worker_stale','message':'付款查驗超過十分鐘沒有完成，請檢查主機。'})
    if counts['repeated_failures']:alerts.append({'code':'repeated_failures','message':'有訂閱連續查驗失敗至少五次，需要人工檢查。'})
    if counts['ack_over_hour']:alerts.append({'code':'ack_delayed','message':'有購買綁定超過一小時仍未確認交付，請優先處理。'})
    if counts['stale']:alerts.append({'code':'verification_stale','message':'有訂閱需重新查驗，可能暫時無法使用。'})
    state='needs_attention' if alerts else ('retrying' if counts['retrying'] else last.get('state','not_started'))
    return {'state':state,'worker_alive':worker_alive,'checked_at':checked,'counts':counts,'alerts':alerts}
