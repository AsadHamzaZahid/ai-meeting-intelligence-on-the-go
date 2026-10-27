/* Bridge between your page and Streamlit. It is added to the END of meeting.html by streamlit_app.py.
   Your page stays exactly as it is. Only two functions are swapped, so they talk to Python instead of FastAPI:
   callApi()  -> starts the analysis in Python and polls until it is done
   chatAsk()  -> asks the transcript chat in Python                                                        */
(() => {
  const MAX_MB = 60;                       // largest file the page may send to Python
  let seq = 0, chain = Promise.resolve();
  const waiters = new Map();
  const send = (type, data) => window.parent.postMessage(Object.assign({ isStreamlitMessage: true, type }, data), '*');

  addEventListener('message', e => {
    const m = e.data;
    if (!m || m.type !== 'streamlit:render') return;
    const r = (m.args || {}).reply;
    if (r && waiters.has(r.id)) { const w = waiters.get(r.id); waiters.delete(r.id); w(r) }
  });
  send('streamlit:componentReady', { apiVersion: 1 });
  const fit = () => { try { send('streamlit:setFrameHeight', { height: window.parent.innerHeight || 800 }) } catch (e) { } };
  fit(); try { window.parent.addEventListener('resize', fit) } catch (e) { }

  /* one request at a time, so Streamlit never drops one */
  const raw = (payload, ms) => new Promise((res, rej) => {
    const id = 'm' + (++seq) + '-' + Date.now();
    const t = setTimeout(() => { waiters.delete(id); rej(new Error('The server took too long to answer.')) }, ms);
    waiters.set(id, r => { clearTimeout(t); res(r) });
    send('streamlit:setComponentValue', { value: Object.assign({ id }, payload), dataType: 'json' });
  });
  const call = (payload, ms = 300000) => { const run = chain.then(() => raw(payload, ms)); chain = run.catch(() => { }); return run };
  window.__stCall = call;

  const b64 = f => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(r.result); r.onerror = () => rej(new Error('Could not read the file.')); r.readAsDataURL(f) });

  callApi = async function () {
    const f = $('#file').files[0], payload = { action: 'analyse', language: $('#lang').value };
    if (f) {
      if (f.size > MAX_MB * 1048576) throw new Error('That file is over ' + MAX_MB + ' MB. Please use a YouTube link or a shorter clip.');
      payload.filename = f.name; payload.data = await b64(f);
    } else payload.url = $('#url').value.trim();
    const r = await call(payload);
    if (!r.ok) throw new Error(r.error || 'The request failed.');
    const job_id = r.job_id;
    for (; ;) {
      await sleep(3000);
      const s = await call({ action: 'poll', job_id });
      if (s.status === 'done') { const res = s.result; res._job = job_id; return res }
      if (s.status === 'error') throw new Error(s.error || 'The analysis failed.');
      if (s.status === 'missing') throw new Error('Lost track of the job. Please try again.');
    }
  };

  chatAsk = async function () {
    const q = $('#q'), v = q.value.trim(); if (!v) return; q.value = '';
    const add = (t, k) => { const m = document.createElement('div'); m.className = 'm ' + k; m.textContent = t; $('#log').append(m); $('#log').scrollTop = 1e9; return m };
    add(v, 'u'); const w = add('Thinking…', '');
    const show = t => { w.innerHTML = md(t); $('#log').scrollTop = 1e9 };
    if (!SID) { await sleep(300); show(localAnswer(v, DATA)); return }
    try {
      const r = await call({ action: 'chat', session_id: SID, question: v });
      if (!r.ok || !r.answer) throw new Error(r.error || 'empty');
      show(r.answer);
    } catch (e) { show(localAnswer(v, DATA)) }
  };
})();
