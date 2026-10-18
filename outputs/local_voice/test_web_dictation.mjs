import {test} from 'node:test';
import assert from 'node:assert/strict';
import {DictationSession} from './web_dictation.mjs';
const settings = {mode:'translate',target:'ja',source:'zh-TW'};
const response = data => new Response(JSON.stringify(data), {headers:{'Content-Type':'application/json'}});

test('uncertain upload retries identical audio, ID and captured settings', async () => {
  const calls = [];
  const client = new DictationSession(async (url, options) => { calls.push({url, options}); if(calls.length === 1) throw Error('connection lost'); return response({state:'queued'}); });
  client.token = 'user-token'; const chosen = {...settings};
  client.prepare(new Blob(['audio'], {type:'audio/webm'}), chosen); chosen.target = 'en';
  await assert.rejects(client.upload()); await client.upload();
  assert.equal(calls[0].options.headers['Idempotency-Key'], calls[1].options.headers['Idempotency-Key']);
  assert.equal(calls[1].options.headers['X-DreamType-Target'], 'ja');
  assert.equal(await calls[1].options.body.get('file').text(), 'audio');
  assert.equal(calls[1].options.headers.Authorization, 'Bearer user-token');
  assert.throws(() => client.prepare(new Blob(['another']), settings));
});
test('clearing account rejects in-flight old responses and erases recording', async () => {
  let resolve;
  const client = new DictationSession(() => new Promise(done => { resolve = done; }));
  client.token = 'old'; client.prepare(new Blob(['audio']), settings);
  const pending = client.api('me'); client.clear(); client.token = 'new';
  resolve(response({name:'old-user'})); await assert.rejects(pending, /登入狀態/);
  assert.equal(client.pending, null); assert.equal(client.token, 'new');
});
test('wrong request, mode, target or empty text never qualifies for a receipt', () => {
  const client = new DictationSession(); const id = client.prepare(new Blob(['audio']), settings);
  const valid = {id,state:'done',mode:'translate',target_language:'ja',text:'こんにちは'};
  assert.equal(client.validate(valid), valid);
  for(const patch of [{id:crypto.randomUUID()}, {mode:'organize'}, {target_language:'en'}, {text:''}, {text:null}]) assert.throws(() => client.validate({...valid,...patch}));
  assert.equal(client.pending.id, id);
});
test('receipt failure retains valid output and does not upload again', async () => {
  const urls=[];
  const client = new DictationSession(async url => { urls.push(url); return new Response('{}',{status:503}); });
  const id=client.prepare(new Blob(['audio']), settings);
  const result=client.validate({id,state:'done',mode:'translate',target_language:'ja',text:'明日。'});
  await assert.rejects(client.receipt(id)); assert.equal(result.text,'明日。');
  assert.deepEqual(urls,['/v2/dictations/'+id+'/receipt']);
});
test('reject empty and oversized audio before any network operation', () => {
  const client=new DictationSession();
  assert.throws(()=>client.prepare(new Blob([]),settings));
  assert.throws(()=>client.prepare(new Blob([new Uint8Array(2*1024*1024+1)]),settings));
  assert.equal(client.pending,null);
});
test('login requires a nonempty token; HTTP error preserves status', async () => {
  const client = new DictationSession(async()=>response({}));
  await assert.rejects(client.login('test','password'),/登入回應/);
  const unauthorized=new DictationSession(async()=>new Response('{"detail":"expired"}',{status:401}));
  await assert.rejects(unauthorized.api('me'), error=>error.status===401);
});
