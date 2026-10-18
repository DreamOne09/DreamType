// Google proof, challenge and session stay in this tab's memory only.
const ORIGIN = 'https://dreamtype.dreamone.li';
let library;
function loadGoogle() {
  if (!library) library = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    const timer = setTimeout(() => { script.remove(); library = null; reject(Error('Google 連線逾時，請重試。')); }, 15000);
    script.src = 'https://accounts.google.com/gsi/client'; script.async = true;
    script.onload = () => { clearTimeout(timer); resolve(globalThis.google.accounts.id); };
    script.onerror = () => { clearTimeout(timer); script.remove(); library = null; reject(Error('無法連線 Google，請檢查網路或使用帳號密碼登入。')); };
    document.head.append(script);
  });
  return library;
}
async function api(path, body, token = '') {
  const response = await fetch('/v2/' + path, {method: body === undefined ? 'GET' : 'POST',
    cache: 'no-store', credentials: 'omit', redirect: 'error', signal: AbortSignal.timeout(35000),
    headers: {'X-DreamType-Client':'web', 'Content-Type':'application/json', ...(token ? {Authorization:'Bearer ' + token} : {})},
    body: body === undefined ? undefined : JSON.stringify(body)});
  let data; try { data = await response.json(); } catch { throw Error('Google 登入服務尚未開放，請使用原本帳號登入。'); }
  if (!response.ok) throw Error((response.status === 404 || (path === 'auth/google/config' && response.status === 401)) ? 'Google 登入服務尚未開放，請使用原本帳號登入。' : data.detail || '驗證失敗，請重試。');
  return data;
}
function button(text, action, parent) {
  const node = document.createElement('button'); node.type = 'button'; node.textContent = text; node.onclick = action; parent.append(node); return node;
}
export function mountGoogle(root, {run, say, getToken, accept, deleted, deletion = false}) {
  let cancel = () => {}, active = false;
  const entry = button(deletion ? '用 Google 再次驗證並刪除' : '使用 Google 帳號', () => run(open), root);
  const choices = document.createElement('div'); root.append(choices);
  addEventListener('pagehide', () => cancel());
  async function open() {
    if (location.origin !== ORIGIN) throw Error('Google 登入請使用 https://dreamtype.dreamone.li。');
    choices.replaceChildren();
    const config = await api('auth/google/config');
    if (!/^[A-Za-z0-9_-]+\.apps\.googleusercontent\.com$/.test(config.client_id) || typeof config.signup_enabled !== 'boolean') throw Error('登入設定不完整。');
    if (deletion) { await begin(config, 'delete'); return; }
    button('登入現有 Google 帳號', () => run(() => begin(config, 'signin')), choices);
    if (config.signup_enabled) button('用 Google 註冊 DreamType', () => run(() => begin(config, 'signup')), choices);
    const help = document.createElement('p'); help.textContent = config.signup_enabled ? '建立 DreamType 帳號不會自動訂閱，也不會合併原本的試用帳號。' : '目前未開放自行註冊。原有試用帳號請使用帳號密碼登入。'; choices.append(help);
  }
  async function begin(config, purpose) {
    if (active) return;
    if (deletion && !confirm('確定永久刪除 DreamType 帳號與設定？無法復原。這不會取消 Google Play 訂閱或退款，請另至 Play 管理訂閱。')) return;
    active = true; const captured = getToken(); let challenge, abandoned = false, timer;
    cancel = () => { abandoned = true; };
    choices.replaceChildren(); entry.hidden = true;
    const base = deletion ? 'me/google/delete' : 'auth/google';
    try {
      challenge = await api(base + '/challenge', deletion ? {} : {purpose}, captured);
      if (!/^[a-f0-9]{32}$/.test(challenge.challenge) || !/^[A-Za-z0-9_-]{43}$/.test(challenge.secret) || !/^[A-Za-z0-9_-]{43}$/.test(challenge.nonce) || !Number.isFinite(challenge.expires_at) || challenge.expires_at * 1000 <= Date.now()) throw Error('驗證已過期，請重新開始。');
      const google = await loadGoogle();
      if (abandoned || captured !== getToken()) throw Error('登入狀態已變更，請重新開始。');
      const proof = await new Promise((resolve, reject) => {
        let settled = false;
        const finish = (value, error) => { if (settled) return; settled = true; clearTimeout(timer); error ? reject(error) : resolve(value); };
        cancel = () => { abandoned = true; finish(null, Error('已取消 Google 驗證。')); };
        timer = setTimeout(() => finish(null, Error('驗證已過期，請重新開始。')), Math.min(240000, challenge.expires_at * 1000 - Date.now()));
        google.initialize({client_id: config.client_id, nonce: challenge.nonce, auto_select: false, ux_mode:'popup',
          callback: response => {
            if (typeof response.credential !== 'string' || !response.credential || response.credential.length > 16384) { finish(null, Error('Google 回應不完整。')); return; }
            finish(response.credential);
          }});
        const target = document.createElement('div'); choices.append(target);
        google.renderButton(target, {type:'standard', theme:'outline', size:'large', text:purpose === 'signup' ? 'signup_with' : 'signin_with', locale:'zh_TW'});
        button('取消驗證', cancel, choices);
        say(deletion ? '請選擇同一個 Google 帳號，確認永久刪除。' : '請按 Google 按鈕完成驗證；關閉彈窗後可按取消重試。');
      });
      if (captured !== getToken() || abandoned) throw Error('登入狀態已變更，請重新開始。');
      // After proof delivery cancellation invalidates adoption, even while HTTP is in flight.
      cancel = () => { abandoned = true; };
      choices.replaceChildren(); say('正在確認 Google 身分…');
      const result = await api(base + '/complete', {challenge:challenge.challenge, secret:challenge.secret, id_token:proof, ...(deletion ? {confirm:true} : {})}, captured);
      if (deletion) {
        if (!abandoned && captured === getToken() && result.deleted === true) deleted();
      } else {
        if (!/^[A-Za-z0-9_-]{43}$/.test(result.token)) throw Error('登入回應不完整。');
        if (abandoned || captured !== getToken()) { await api('logout', {}, result.token); return; }
        try { await accept(result.token); }
        catch (error) { await api('logout', {}, result.token).catch(() => {}); throw error; }
      }
    } finally { clearTimeout(timer); challenge = null; active = false; cancel = () => {}; choices.replaceChildren(); entry.hidden = false; }
  }
}
