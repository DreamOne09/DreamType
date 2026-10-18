// Account tokens and audio stay in page memory. No browser storage or owner key.
export class DictationSession {
  constructor(request = (...args) => globalThis.fetch(...args)) { this.request = request; this.token = ''; this.epoch = 0; this.pending = null; }
  clear() { this.epoch++; this.token = ''; this.pending = null; }
  async api(path, options = {}) {
    const epoch = this.epoch;
    const response = await this.request('/v2/' + path, {...options, cache: 'no-store',
      signal: AbortSignal.timeout(35000), headers: {Authorization: 'Bearer ' + this.token, ...options.headers}});
    if (epoch !== this.epoch) throw Error('登入狀態已變更，已忽略舊的回應。');
    let data;
    try { data = await response.json(); } catch { throw Error('服務回應不完整，請稍後取回結果。'); }
    if (epoch !== this.epoch) throw Error('登入狀態已變更，已忽略舊的回應。');
    if (!response.ok) { const error = Error(data.detail || '操作失敗，請稍後重試。'); error.status = response.status; throw error; }
    return data;
  }
  async login(username, password) {
    this.clear();
    const result = await this.api('login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({username, password})});
    if (typeof result.token !== 'string' || !result.token) throw Error('登入回應不完整。');
    this.token = result.token;
    return this.api('me');
  }
  prepare(blob, settings) {
    if (this.pending) throw Error('請先取回上一筆結果，或放棄本頁的重試錄音。');
    if (!blob.size || blob.size > 2 * 1024 * 1024) throw Error('錄音為空或超過 2 MB，請縮短錄音。');
    this.pending = {id: crypto.randomUUID(), blob, settings: {...settings}};
    return this.pending.id;
  }
  async upload() {
    const pending = this.pending;
    if (!pending) throw Error('本頁已沒有可重試的錄音。');
    const body = new FormData(); body.append('file', pending.blob, 'recording');
    return this.api('dictations', {method: 'POST', body, headers: {
      'Idempotency-Key': pending.id, 'X-DreamType-Receipt': '1',
      'X-DreamType-Mode': pending.settings.mode, 'X-DreamType-Target': pending.settings.target,
      'X-DreamType-Source': pending.settings.source}});
  }
  validate(result) {
    if (!result || typeof result.id !== 'string' || !/^[A-Za-z0-9_-]{16,80}$/.test(result.id)) throw Error('結果代碼無效，請重新取回。');
    if (this.pending && result.id !== this.pending.id) throw Error('這不是目前錄音的結果，已保留重試錄音。');
    if (result.state === 'done') {
      if (typeof result.text !== 'string' || !result.text.trim()) throw Error('結果缺少文字，請重新取回。');
      const expected = this.pending?.settings;
      if (expected && (result.mode !== expected.mode || (expected.mode === 'translate' && result.target_language !== expected.target))) throw Error('結果模式不符，請重新取回。');
    }
    return result;
  }
  async receipt(id) { return this.api('dictations/' + encodeURIComponent(id) + '/receipt', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: '{}'}); }
}
