import {DictationSession} from './web_dictation.mjs';
// Existing owner pairing links carry a fragment, never a server query parameter.
if (location.hash.startsWith('#key=')) location.replace('/private' + location.hash);
const $ = id => document.getElementById(id);
const session = new DictationSession();
let busy = false, recorder = null, stream = null, timer = null, canceled = false;
let original = '', undo = '', receiptId = '', operation = 0;
const say = text => { $('status').textContent = text; };
function controls() {
  $('record').disabled = busy || !!session.pending || !!receiptId;
  $('record').setAttribute('aria-pressed', String(!!recorder));
  $('record-label').textContent = recorder ? '停止錄音' : '開始錄音';
  $('cancel').hidden = !recorder;
  for (const id of ['mode','target','source','recover','logout']) $(id).disabled = busy || !!recorder;
  for (const id of ['retry','discard']) { $(id).hidden = !session.pending; $(id).disabled = busy; }
  $('login').querySelector('button').disabled = busy;
}
function releaseMicrophone() { clearInterval(timer); timer = null; stream?.getTracks().forEach(track => track.stop()); stream = null; }
function clearPage() {
  operation++; session.clear(); canceled = true;
  if (recorder?.state === 'recording') recorder.stop();
  recorder = null; releaseMicrophone();
  original = undo = receiptId = '';
  for (const id of ['text','password','username']) $(id).value = '';
  $('raw').textContent = $('identity').textContent = '';
  $('workspace').hidden = $('result').hidden = true; $('signin').hidden = false;
  $('receipt').hidden = true; controls();
}
async function run(action) {
  if (busy) return;
  busy = true; controls();
  try { await action(); }
  catch (error) { if (error.status === 401) clearPage(); say(error.name === 'TimeoutError' ? '連線逾時。請取回上一筆，或重試同一筆上傳。' : error.message || '連線失敗，請重試。'); }
  finally { busy = false; controls(); }
}
async function acknowledge(announce = false) {
  if (!receiptId) return;
  const id = receiptId;
  try { await session.receipt(id); if (receiptId === id) { receiptId = ''; $('receipt').hidden = true; if (announce) say('結果已收到。請先複製文字，再關閉分頁。'); } }
  catch { say('文字已取回，但收件確認未成功。請按「確認已收到結果」，不需要重送錄音。'); }
}
async function display(progress) {
  const result = session.validate(progress);
  if (result.state === 'done') {
    // Show and retain valid text before confirming delivery. Never acknowledge an invalid result.
    undo = $('text').value; $('text').value = result.text;
    original = typeof result.raw_text === 'string' ? result.raw_text : '';
    $('raw').textContent = original || '這筆沒有提供辨識原文。'; $('restore').disabled = !original;
    $('result').hidden = false; session.pending = null;
    receiptId = result.receipt_required ? result.id : ''; $('receipt').hidden = !receiptId;
    say(result.warning ? '已完成；整理未完整成功，請核對原文。' : '完成了。你可以修改，再複製到任何地方。');
    await acknowledge(); return true;
  }
  if (['failed','expired'].includes(result.state)) {
    session.pending = null; say(result.message || '這筆無法取回，請重新錄音。'); return true;
  }
  if (!['queued','running'].includes(result.state)) throw Error('未知的處理狀態，請稍後取回結果。');
  say(result.state === 'queued' ? '錄音已送達，正在排隊。' : '正在辨識與整理，請稍候。'); return false;
}
async function follow(progress) {
  if (progress.state === 'none') { say('還沒有可取回的錄音。'); return; }
  const epoch = operation, deadline = Date.now() + 180000;
  while (epoch === operation) {
    if (await display(progress)) return;
    if (Date.now() >= deadline) { say('仍在處理。請稍後按「取回上一筆」，不必重錄。'); return; }
    await new Promise(resolve => setTimeout(resolve, 1500));
    if (epoch !== operation) return;
    progress = await session.api('dictations/' + encodeURIComponent(progress.id));
  }
}
$('login').onsubmit = event => {
  event.preventDefault(); const password = $('password').value; $('password').value = '';
  run(async () => {
    const me = await session.login($('username').value.trim(), password);
    $('identity').textContent = me.name + ' · 本月剩約 ' + Math.floor(me.remaining_seconds / 60) + ' 分鐘';
    const prefs = me.preferences || {};
    for (const [id, key] of [['mode','mode'],['target','target_language'],['source','source_language']]) {
      if ([...$(id).options].some(option => option.value === prefs[key])) $(id).value = prefs[key];
    }
    $('mode').dispatchEvent(new Event('change'));
    $('signin').hidden = true; $('workspace').hidden = false; say('已登入。按圓形按鈕開始錄音。');
  });
};
$('mode').onchange = () => { $('target-label').hidden = $('mode').value !== 'translate'; };
$('record').onclick = () => {
  if (recorder) { recorder.stop(); return; }
  run(async () => {
    if (!navigator.mediaDevices?.getUserMedia || !globalThis.MediaRecorder) throw Error('此瀏覽器無法錄音，請用最新版 Chrome、Edge 或 Safari 開啟 HTTPS 網址。');
    canceled = false;
    const settings = {mode: $('mode').value, target: $('target').value, source: $('source').value};
    try {
      stream = await navigator.mediaDevices.getUserMedia({audio: true});
      const mimeType = ['audio/webm;codecs=opus','audio/mp4'].find(type => MediaRecorder.isTypeSupported(type));
      const active = new MediaRecorder(stream, {...(mimeType ? {mimeType} : {}), audioBitsPerSecond: 64000});
      recorder = active; const chunks = []; let bytes = 0; const start = Date.now();
      active.ondataavailable = event => {
        if (event.data.size) { chunks.push(event.data); bytes += event.data.size; }
        if (bytes > 1900000 && active.state === 'recording') active.stop();
      };
      active.onerror = () => { canceled = true; releaseMicrophone(); recorder = null; say('錄音中斷，請檢查麥克風後重錄。'); controls(); };
      active.onstop = () => {
        releaseMicrophone(); recorder = null; $('clock').textContent = '最長 1 分 50 秒'; controls();
        if (canceled) { say('已取消，沒有上傳這次錄音。'); return; }
        run(async () => { session.prepare(new Blob(chunks, {type: active.mimeType}), settings); say('正在上傳錄音…'); await follow(await session.upload()); });
      };
      active.start(1000); say('正在錄音，再按一次就會停止。');
      timer = setInterval(() => {
        const seconds = Math.floor((Date.now() - start) / 1000);
        $('clock').textContent = seconds + ' / 110 秒';
        if (seconds >= 110 && active.state === 'recording') active.stop();
      }, 250);
    } catch (error) { releaseMicrophone(); recorder = null; throw error; }
  });
};
$('cancel').onclick = () => { canceled = true; if (recorder?.state === 'recording') recorder.stop(); };
$('retry').onclick = () => run(async () => { say('正在重試同一筆錄音…'); await follow(await session.upload()); });
$('recover').onclick = () => run(async () => {
  const id = session.pending?.id || receiptId;
  const path = id ? 'dictations/' + encodeURIComponent(id) : 'me/latest-dictation';
  await follow(await session.api(path));
});
$('discard').onclick = () => {
  if (!confirm('放棄本頁的重試錄音？已送達主機的工作仍會繼續，可用「取回上一筆」查看。')) return;
  session.pending = null; controls(); say('已清除本頁錄音；這不會取消主機已接收的工作。');
};
$('logout').onclick = () => run(async () => { await session.api('logout', {method: 'POST', headers: {'Content-Type':'application/json'}, body:'{}'}); clearPage(); say('已登出，憑證已撤銷。'); });
$('copy').onclick = () => run(async () => { await navigator.clipboard.writeText($('text').value); say('文字已複製。'); });
function replace(text) { undo = $('text').value; $('text').value = text; }
$('erase').onclick = () => replace('');
$('restore').onclick = () => replace(original);
$('undo').onclick = () => { const current = $('text').value; $('text').value = undo; undo = current; };
$('receipt').onclick = () => run(() => acknowledge(true));
addEventListener('beforeunload', event => { if (recorder || session.pending || $('text').value) { event.preventDefault(); event.returnValue = ''; } });
addEventListener('pagehide', () => { canceled = true; releaseMicrophone(); });
controls();
