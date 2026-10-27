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
    const f = $('#file').files[0], pick = window.PICKED; window.PICKED = null;
    const payload = { action: 'analyse', language: $('#lang').value };
    if (pick) payload.sample = pick;
    else if (f) {
      if (f.size > MAX_MB * 1048576) throw new Error('That file is over ' + MAX_MB + ' MB. Please use a shorter clip.');
      payload.filename = f.name; payload.data = await b64(f);
    } else payload.url = $('#url').value.trim();
    const r = await call(payload);
    if (!r.ok) throw new Error(r.error || 'The request failed.');
    const job_id = r.job_id; let lastStage = null;
    window.setStage && window.setStage({});            // reset the lights
    for (; ;) {
      await sleep(3000);
      const s = await call({ action: 'poll', job_id });
      if (s.stage) lastStage = s.stage;
      if (s.status === 'running' && window.setStage) window.setStage(s);
      if (s.status === 'done') {
        window.setStage && window.setStage({ status: 'done' });
        const res = s.result; res._job = job_id; return res;
      }
      if (s.status === 'error') {
        window.setStage && window.setStage({ status: 'error', stage: lastStage });
        const e = new Error(s.code === 'yt_blocked' ? 'YouTube blocks cloud servers. Pick a sample or upload a file.' : (s.error || 'The analysis failed.'));
        e.code = s.code; throw e;
      }
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

  /* ---- sample panel (left side, shown with the upload box) ---- */
  const st = document.createElement('style');
  st.textContent = `#smp{position:fixed;left:12px;top:42%;z-index:62;display:none}
  body.gated #smp{display:block} body.loading #smp,body.black #smp,body.is-day #smp{display:none}
  #smpb{background:#ffd24a;color:#111;border:0;border-radius:10px;padding:10px 14px;font:700 14px Inter,sans-serif;cursor:pointer;box-shadow:0 4px 14px #000a}
  #smpl{display:none;margin-top:8px;width:min(280px,70vw);max-height:50vh;overflow:auto;background:#0a0f1eee;border:1px solid #ffffff30;border-radius:12px;padding:6px}
  #smpl.on{display:block}
  #smpl button{display:block;width:100%;text-align:left;background:none;border:0;color:#eef2ff;padding:9px 10px;border-radius:8px;font:500 14px Inter,sans-serif;cursor:pointer}
  #smpl button:hover{background:#ffffff1a}`;
  document.head.append(st);
  const box = document.createElement('div'); box.id = 'smp';
  box.innerHTML = '<button id="smpb" type="button">🎬 Samples</button><div id="smpl"></div>';
  document.body.append(box);
  $('#smpb').onclick = () => $('#smpl').classList.toggle('on');
  call({ action: 'samples' }).then(r => {
    (r.samples || []).forEach(s => {
      const b = document.createElement('button'); b.type = 'button'; b.textContent = s.title;
      b.onclick = () => {
        window.PICKED = s.file; $('#url').value = ''; $('#file').value = ''; $('#fn').textContent = '';
        $('#smpl').classList.remove('on'); $('#form').requestSubmit();
      };
      $('#smpl').append(b);
    });
  }).catch(() => { });

  /* ================= PIPELINE LIGHTS: zombie-escape checkpoints ================= */
  const STAGES = [['audio', '⚡', 'Power the generator'], ['transcribe', '📻', 'Decode the radio'], ['title', '🔐', 'Crack the keypad'],
  ['summary', '🪵', 'Barricade the room'], ['extract', '📦', 'Find supplies'], ['rag', '🏠', 'Reach the safehouse']];
  const css2 = document.createElement('style');
  css2.textContent = `
  #pl{position:fixed;right:10px;top:58px;z-index:62;display:none;width:min(230px,60vw);background:#0a0f1ecc;border:1px solid #ffffff30;border-radius:12px;padding:10px 12px;font:600 12px Inter,sans-serif;color:#cfd8ff}
  body.loading #pl{display:block} body.black #pl,body.is-day #pl{display:none}
  #pl .plt{letter-spacing:.14em;font-size:11px;color:#ffd24a}
  #pl ul{margin:6px 0 0;padding:0}
  #pl li{list-style:none;display:flex;align-items:center;gap:8px;padding:4px 0;opacity:.5}
  #pl .dot{width:10px;height:10px;border-radius:50%;background:#3a4258;flex:none}
  #pl li.run,#pl li.ok,#pl li.bad{opacity:1}
  #pl li.run .dot{background:#ffd24a;box-shadow:0 0 8px #ffd24a;animation:plf .5s steps(1) infinite}
  #pl li.ok .dot{background:#3ecf8e;box-shadow:0 0 8px #3ecf8e}
  #pl li.bad .dot{background:#ff2a3d;box-shadow:0 0 8px #ff2a3d}
  @keyframes plf{50%{opacity:.25}}
  #plz{position:relative;height:20px;margin-top:6px;border-bottom:2px dashed #ffffff30}
  #plzb{position:absolute;bottom:0;left:20%;transition:left 1s linear}
  #plz .plh{position:absolute;right:0;bottom:0}
  @media(max-width:700px){#pl{width:auto}#pl .lb{display:none}#pl ul{display:flex;gap:12px}#pl li{padding:0}}`;
  document.head.append(css2);
  const pl = document.createElement('div'); pl.id = 'pl';
  pl.innerHTML = '<div class="plt">ESCAPE ROUTE</div><div id="plz"><span id="plzb">🧟</span><span class="plh">🏠</span></div><ul>' +
    STAGES.map(([k, ic, lb]) => `<li data-k="${k}"><i class="dot"></i><span>${ic}</span><span class="lb">${lb}</span></li>`).join('') + '</ul>';
  document.body.append(pl);
  let pz = 20, doneN = 0;
  const zmove = () => { $('#plzb').style.left = Math.max(2, Math.min(85, pz)) + '%' };
  setInterval(() => { if (document.body.classList.contains('loading')) { pz += .5; zmove() } }, 1000);
  window.setStage = s => {
    s = s || {};
    const fin = s.status === 'done', done = new Set(fin ? STAGES.map(x => x[0]) : (s.done_stages || []));
    const noInfo = !fin && !s.stage && !done.size && s.status !== 'error';
    pl.querySelectorAll('li').forEach(li => {
      const k = li.dataset.k;
      li.className = done.has(k) ? 'ok' : s.status === 'error' ? (k === s.stage ? 'bad' : '') : (noInfo || k === s.stage) ? 'run' : '';
    });
    if (!s.status && !s.stage) { pz = 20; doneN = 0 }
    if (done.size > doneN) pz -= 12 * (done.size - doneN);
    doneN = done.size; zmove();
  };

  /* ================= THE HERO: appears with the upload box ================= */
  const BUBBLE_HOLD = 1500;                       // ms each bubble stays after typing (shorten for a faster scene)
  const LINES = ['YouTube blocks cloud servers, so links can\u2019t be processed on this deployed app.',
    'Pick a sample from the box I\u2019m leaving behind, or upload any file from your computer.',
    'Run this code on your own machine and YouTube links work too.'];
  const css3 = document.createElement('style');
  css3.textContent = `
  #hero{position:fixed;right:16px;bottom:9%;z-index:70;width:130px;transform:translateX(220%);transition:transform .7s cubic-bezier(.2,.8,.3,1);pointer-events:none}
  #hero.in{transform:none}
  body.loading #hero,body.black #hero,body.is-day #hero{display:none}
  #hero svg{width:100%;display:block;animation:hfl 1.6s ease-in-out infinite alternate;filter:drop-shadow(0 6px 10px #000a)}
  @keyframes hfl{to{transform:translateY(-8px)}}
  #hb{position:absolute;right:100%;bottom:70%;margin-right:6px;width:min(280px,62vw);background:#0a0f1ef2;border:2px solid #ffd24a;border-radius:14px;padding:10px 14px;color:#fff;font:600 14px/1.4 Inter,sans-serif;display:none;pointer-events:auto;cursor:pointer}
  #hb.on{display:block}
  @keyframes glw{50%{box-shadow:0 0 0 6px #ffd24a66,0 0 22px 8px #ffd24a}}
  .glow{animation:glw .9s ease-in-out infinite}
  @media(max-width:800px){#hero{width:90px;bottom:auto;top:24%}}`;
  document.head.append(css3);
  const hero = document.createElement('div'); hero.id = 'hero';
  hero.innerHTML = '<div id="hb"></div><svg viewBox="0 0 120 200" aria-hidden="true"><path d="M38 56Q8 120 20 192L60 164L100 192Q112 120 82 56z" fill="#e8501a"/><rect x="40" y="52" width="40" height="64" rx="12" fill="#1fa7a0"/><rect x="42" y="112" width="15" height="62" rx="6" fill="#12323a"/><rect x="63" y="112" width="15" height="62" rx="6" fill="#12323a"/><rect x="40" y="170" width="19" height="12" rx="4" fill="#e8501a"/><rect x="61" y="170" width="19" height="12" rx="4" fill="#e8501a"/><path d="M38 62L18 94" stroke="#1fa7a0" stroke-width="10" stroke-linecap="round"/><path d="M82 62L106 38" stroke="#1fa7a0" stroke-width="10" stroke-linecap="round"/><circle cx="106" cy="36" r="7" fill="#e8b48a"/><circle cx="18" cy="96" r="7" fill="#e8b48a"/><circle cx="60" cy="34" r="17" fill="#e8b48a"/><path d="M43 31Q60 12 77 31V37Q60 28 43 37z" fill="#12323a"/><circle cx="53" cy="36" r="2.4" fill="#fff"/><circle cx="67" cy="36" r="2.4" fill="#fff"/><circle cx="60" cy="84" r="9" fill="#ffd24a" stroke="#12323a" stroke-width="2"/></svg>';
  document.body.append(hero);
  const hb = hero.querySelector('#hb');
  let heroBusy = false, skip = false;
  hb.onclick = () => { skip = true };
  const typeIn = async t => { hb.textContent = ''; for (const ch of t) { if (skip) { hb.textContent = t; break } hb.textContent += ch; await sleep(18) } };
  const pulse = () => ['#smpb', '#pick'].forEach(s => { const e = $(s); if (e) { e.classList.add('glow'); setTimeout(() => e.classList.remove('glow'), 6000) } });
  async function runHero(lines) {
    if (heroBusy) return; heroBusy = true; skip = false;
    hero.classList.add('in'); try { noise(.6, 3500, 300, .15, 'bandpass') } catch (e) { }
    await sleep(800);
    for (const t of lines) {
      hb.classList.add('on'); try { tone(520, 780, .1, .1, 'square') } catch (e) { }
      await typeIn(t); skip = false;
      for (let i = 0; i < BUBBLE_HOLD / 100 && !skip; i++) await sleep(100);
      skip = false;
    }
    hb.classList.remove('on'); hero.classList.remove('in'); await sleep(900);
    pulse(); heroBusy = false;
  }
  let heroSeen = false;
  new MutationObserver(() => {
    if (!heroSeen && document.body.classList.contains('gated')) { heroSeen = true; setTimeout(() => runHero(LINES), 1200) }
  }).observe(document.body, { attributes: true, attributeFilter: ['class'] });
  window.onYtBlocked = () => runHero(['Told you: YouTube blocks cloud servers here. Pick a sample or upload a file.']);
})();