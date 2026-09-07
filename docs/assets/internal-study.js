(function () {
  'use strict';

  const BASE = location.pathname.replace(/[^/]*$/, '');
  const api = (p) => BASE + p;
  const SUBMIT_URL = api('submit');
  const USERNAMES = ['Sadra', 'Yalda', 'Micah', 'Rini', 'Gabe', 'Guest'];
  const rawPairs = window.INTERNAL_STUDY_PAIRS || [];
  const app = document.getElementById('app');
  if (!app) return;

  let username = localStorage.getItem('internal_study_username') || '';
  let sessionId = '';
  let pairs = [];
  let responses = [];

  if (!rawPairs.length) {
    app.replaceChildren(notice('Study data not loaded', 'Run `node scripts/build-pages.mjs` to generate internal-study-data.js.'));
    return;
  }

  renderIntro();

  function renderIntro() {
    const sec = el('section', 'study-hero study-hero--centered');
    sec.appendChild(el('div', 'eyebrow', 'Internal validation'));
    sec.appendChild(el('h1', '', 'Conversation comparison study'));
    sec.appendChild(el('p', 'lede', 'Compare each fixed-anchor conversation with a changed version. Please judge only the therapist’s answers shown on each page.')); 

    const form = el('div', 'demo-form');
    const field = el('div', 'demo-field');
    field.appendChild(el('label', 'demo-label', 'Username *'));
    const select = el('select', 'demo-select');
    const ph = el('option', '', '— select —'); ph.value = ''; select.appendChild(ph);
    USERNAMES.forEach((u) => { const o = el('option', '', u); o.value = u; select.appendChild(o); });
    select.value = username;
    field.appendChild(select);
    form.appendChild(field);
    sec.appendChild(form);

    const err = el('p', 'form-error'); err.hidden = true; sec.appendChild(err);
    const btn = el('button', 'btn-primary', 'Start study →');
    btn.addEventListener('click', () => {
      username = select.value;
      if (!username) { err.textContent = 'Please select a username.'; err.hidden = false; return; }
      localStorage.setItem('internal_study_username', username);
      sessionId = getOrCreateSessionId(username);
      const seed = hashStr('internal-study-fixed-order-v1');
      pairs = seededShuffle(rawPairs, seed).map((pair) => ({
        ...pair,
        anchorOnLeft: seededBool(hashStr('internal-study-fixed-side|' + pair.key)),
      }));
      responses = new Array(pairs.length);
      fetchProgress().then((progress) => {
        if (progress.session_id) {
          sessionId = progress.session_id;
          localStorage.setItem('internal_study_session_' + username.toLowerCase(), sessionId);
        }
        if (progress.completed) renderAlreadyCompleted();
        else if (progress.answered_pair_keys.length >= pairs.length) renderPendingFinalize();
        else if (progress.answered_pair_keys.length > 0) {
          const nextIdx = pairs.findIndex((pair) => !progress.answered_pair_keys.includes(pair.key));
          renderPair(nextIdx >= 0 ? nextIdx : 0);
        } else renderInstructions();
      });
    });
    sec.appendChild(btn);
    app.replaceChildren(sec);
  }

  async function fetchProgress() {
    try {
      const res = await fetch(api(`progress?username=${encodeURIComponent(username)}&session_id=${encodeURIComponent(sessionId)}`));
      if (!res.ok) return { completed: false, answered_pair_keys: [] };
      const data = await res.json();
      return { completed: !!data.completed, answered_pair_keys: data.answered_pair_keys || [], session_id: data.session_id || '' };
    } catch {
      return { completed: false, answered_pair_keys: [] };
    }
  }

  function renderPendingFinalize() {
    const sec = el('section', 'study-hero study-hero--centered');
    sec.appendChild(el('h2', '', 'Almost done'));
    sec.appendChild(el('p', 'lede', 'All comparisons have already been answered for this username. Click below to finalize them.'));
    const btn = el('button', 'btn-primary', 'Submit responses →');
    btn.addEventListener('click', submitResponses);
    sec.appendChild(btn);
    app.replaceChildren(sec);
  }

  function renderAlreadyCompleted() {
    renderStatusScreen('Already submitted', 'This username has already finalized this internal validation session.');
  }

  function renderInstructions() {
    const sec = el('section', 'study-hero study-hero--centered');
    sec.appendChild(el('div', 'eyebrow', 'Before you begin'));
    sec.appendChild(el('h2', 'instructions-heading', 'Instructions'));
    const body = el('div', 'instructions-body');
    const ul = el('ul', 'instructions-list');
    [
      'Each page shows two conversations side by side: one fixed anchor and one changed version. Labels are hidden and left/right placement is randomized.',
      'Focus your judgments on the therapist’s answers, not on the user’s messages or the overall scenario.',
      'Answer three comparative questions about the therapist’s answers: human-likeness, sycophancy/over-agreeableness, and empathy.',
      'Use “about the same” when there is no meaningful difference between the therapists’ answers.',
      'The goal is to check whether the intended property changed while empathy stayed similar.',
    ].forEach((t) => ul.appendChild(el('li', '', t)));
    body.appendChild(ul);
    sec.appendChild(body);
    const btn = el('button', 'btn-primary', `Start ${pairs.length} comparisons →`);
    btn.addEventListener('click', () => renderPair(0));
    sec.appendChild(btn);
    app.replaceChildren(sec);
    window.scrollTo(0, 0);
  }

  function renderPair(index) {
    const pair = pairs[index];
    const left = pair.anchorOnLeft ? pair.anchor : pair.changed;
    const right = pair.anchorOnLeft ? pair.changed : pair.anchor;
    const frag = document.createDocumentFragment();

    const prog = el('div', 'study-progress');
    prog.appendChild(el('div', 'progress-label', `Comparison ${index + 1} of ${pairs.length}`));
    const bar = el('div', 'progress-bar');
    const fill = el('div', 'progress-fill'); fill.style.width = `${(index / pairs.length) * 100}%`; bar.appendChild(fill); prog.appendChild(bar);
    frag.appendChild(prog);
    frag.appendChild(el('div', 'breadcrumb', pair.label));
    frag.appendChild(el('p', 'question-text', 'Read both conversations, then compare the therapist’s answers below.')); 

    const grid = el('div', 'comparison-grid');
    grid.appendChild(conversationCard('Conversation A', left.turns));
    grid.appendChild(conversationCard('Conversation B', right.turns));
    frag.appendChild(grid);

    const questions = el('div', 'conv-questions-section');
    const hdr = el('div', 'conv-questions-header'); hdr.appendChild(el('h3', 'conv-questions-title', 'Comparative ratings')); questions.appendChild(hdr);
    const answers = {};
    const blocks = [
      comparativeBlock('human_likeness', 'In which conversation do the therapist’s answers sound more human-like?', answers),
      comparativeBlock('sycophancy', 'In which conversation are the therapist’s answers more sycophantic / overly agreeable toward the user?', answers),
      comparativeBlock('empathy', 'In which conversation are the therapist’s answers more empathetic?', answers),
    ];
    blocks.forEach((b) => questions.appendChild(b));
    frag.appendChild(questions);

    const optional = el('div', 'rq-block');
    optional.appendChild(el('p', 'rq-label', 'Optional note: what about the therapist’s answers drove your ratings?')); 
    const note = el('textarea', 'rq-textarea'); note.rows = 3; optional.appendChild(note); frag.appendChild(optional);

    const err = el('p', 'form-error'); err.hidden = true; frag.appendChild(err);
    const btn = el('button', 'btn-primary btn-next', index < pairs.length - 1 ? 'Next comparison →' : 'Submit responses');
    btn.addEventListener('click', async () => {
      const missing = blocks.filter((b) => !answers[b.dataset.key]);
      blocks.forEach((b) => b.classList.toggle('rq-block--missing', !answers[b.dataset.key]));
      if (missing.length) { err.textContent = 'Please answer all three comparative questions.'; err.hidden = false; missing[0].scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
      err.hidden = true;
      responses[index] = {
        pair_key: pair.key,
        category: pair.category,
        anchor_file: pair.anchor.file,
        anchor_condition: pair.anchor.condition,
        changed_file: pair.changed.file,
        change_type: pair.change_type,
        direction: pair.direction,
        anchor_side: pair.anchorOnLeft ? 'A' : 'B',
        ratings: answers,
        note: note.value.trim(),
      };
      await saveProgress(responses[index]);
      if (index < pairs.length - 1) renderPair(index + 1); else submitResponses();
    });
    frag.appendChild(btn);
    app.replaceChildren(frag);
    window.scrollTo(0, 0);
  }

  function comparativeBlock(key, question, answers) {
    const wrap = el('div', 'rq-block'); wrap.dataset.key = key;
    wrap.appendChild(el('p', 'rq-label', question));
    const row = el('div', 'yn-row');
    const opts = [
      ['A_much', 'A: much more'], ['A_slightly', 'A: slightly more'], ['same', 'About the same'], ['B_slightly', 'B: slightly more'], ['B_much', 'B: much more'],
    ];
    const buttons = [];
    opts.forEach(([value, label]) => {
      const btn = el('button', 'yn-btn', label); btn.type = 'button';
      btn.addEventListener('click', () => { buttons.forEach((b) => b.classList.remove('selected')); btn.classList.add('selected'); answers[key] = value; wrap.classList.remove('rq-block--missing'); });
      buttons.push(btn); row.appendChild(btn);
    });
    wrap.appendChild(row);
    return wrap;
  }

  async function saveProgress(response) {
    try { await fetch(api('save-response'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, session_id: sessionId, response }) }); } catch { /* final submit is fallback */ }
  }

  async function submitResponses() {
    renderStatusScreen('Submitting…', 'Please wait while your responses are saved.');
    const payload = { username, session_id: sessionId, submitted_at: new Date().toISOString(), responses: responses.filter(Boolean) };
    try {
      const res = await fetch(SUBMIT_URL, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!res.ok) throw new Error(`Server responded with ${res.status}`);
      renderStatusScreen('Thank you!', 'Your internal validation responses have been recorded.');
    } catch (err) { renderStatusScreen('Submission error', `Could not save responses: ${err.message}`); }
  }

  function conversationCard(title, turns) {
    const card = el('article', 'conversation-card');
    const hdr = el('header'); const line = el('div', 'card-title-line'); line.appendChild(el('div', 'conversation-title', title)); hdr.appendChild(line); hdr.appendChild(speakerKey()); card.appendChild(hdr);
    const turnsEl = el('section', 'turns'); const list = el('div', 'turn-list');
    for (const turn of turns) { const item = el('div', `turn ${turn.role}`); item.appendChild(el('div', 'turn-text', turn.text)); list.appendChild(item); }
    turnsEl.appendChild(list); card.appendChild(turnsEl); return card;
  }

  function speakerKey() { const key = el('div', 'speaker-key'); key.appendChild(el('span', 'speaker-pill assistant', 'Therapist')); key.appendChild(el('span', 'speaker-pill user', 'User')); return key; }
  function renderStatusScreen(title, body) { const sec = el('section', 'study-hero study-hero--centered'); sec.appendChild(el('h1', '', title)); sec.appendChild(el('p', 'lede', body)); app.replaceChildren(sec); window.scrollTo(0, 0); }
  function notice(title, body) { const sec = el('section', 'notice'); sec.appendChild(el('h1', '', title)); sec.appendChild(el('p', '', body)); return sec; }
  function getOrCreateSessionId(name) {
    const key = 'internal_study_session_' + name.toLowerCase();
    let id = localStorage.getItem(key);
    if (!id) { id = uid(); localStorage.setItem(key, id); }
    return id;
  }
  function uid() { return crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now().toString(36); }
  function el(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; }
  function hashStr(s) { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; } return h; }
  function seededBool(seed) { return makeRng(seed)() < 0.5; }
  function makeRng(seed) { let s = seed >>> 0; return function () { s = (s + 0x6D2B79F5) >>> 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function seededShuffle(arr, seed) { const rng = makeRng(seed); const result = arr.slice(); for (let i = result.length - 1; i > 0; i--) { const j = Math.floor(rng() * (i + 1)); [result[i], result[j]] = [result[j], result[i]]; } return result; }
})();
