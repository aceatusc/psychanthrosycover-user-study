(function () {
  'use strict';

  const BASE = location.pathname.replace(/[^/]*$/, '');
  const api = (p) => BASE + p;
  const USERNAMES = ['Sadra', 'Yalda', 'Micah', 'Rini', 'Gabe', 'Guest'];
  const rawPairs = window.EMPATHY_VALIDATION_PAIRS || [];
  const app = document.getElementById('app');
  if (!app) return;

  let username = localStorage.getItem('empathy_validation_username') || '';
  let sessionId = '';
  let pairs = [];
  let responses = [];

  if (!rawPairs.length) {
    app.replaceChildren(notice('Study data not loaded', 'Run `node scripts/build-pages.mjs` to generate empathy-validation-study-data.js.'));
    return;
  }

  renderIntro();

  function renderIntro() {
    const sec = el('section', 'study-hero study-hero--centered');
    sec.appendChild(el('div', 'eyebrow', 'Internal study'));
    sec.appendChild(el('h1', '', 'Empathy validation study'));
    sec.appendChild(el('p', 'lede', 'Compare blinded professional vs. unprofessional conversation pairs and rate which therapist sounds more empathetic.'));

    const form = el('div', 'demo-form');
    const field = el('div', 'demo-field');
    field.appendChild(el('label', 'demo-label', 'Researcher name *'));
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
      if (!username) { err.textContent = 'Please select your name.'; err.hidden = false; return; }
      localStorage.setItem('empathy_validation_username', username);
      sessionId = getOrCreateSessionId(username);
      pairs = seededShuffle(rawPairs, hashStr('empathy-validation-order-v1')).map((pair) => ({
        ...pair,
        aOnLeft: seededBool(hashStr('empathy-validation-side|' + pair.key)),
      }));
      responses = new Array(pairs.length);
      fetchProgress().then((progress) => {
        if (progress.session_id) {
          sessionId = progress.session_id;
          localStorage.setItem(sessionKey(username), sessionId);
        }
        if (progress.completed) renderAlreadyCompleted();
        else if (progress.answered_pair_keys.length >= pairs.length) renderPendingFinalize();
        else if (progress.answered_pair_keys.length > 0) {
          const nextIdx = pairs.findIndex((pair) => !progress.answered_pair_keys.includes(pair.key));
          renderInstructions(nextIdx >= 0 ? nextIdx : 0, progress.answered_pair_keys.length);
        } else renderInstructions(0, 0);
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

  function renderInstructions(startIndex, alreadyAnswered) {
    const sec = el('section', 'study-hero study-hero--centered');
    sec.appendChild(el('div', 'eyebrow', 'Before you begin'));
    sec.appendChild(el('h2', 'instructions-heading', 'Instructions'));
    const ul = el('ul', 'instructions-list');
    [
      'Each page shows two blinded conversations side by side. One is the professional conversation and one is the unprofessional conversation; labels and left/right placement are hidden.',
      'Focus only on the therapist’s answers when judging empathy.',
      'Use the 7-point comparative scale to indicate whether Conversation A or Conversation B is more empathetic, or whether they are about the same.',
      'Your progress is saved after each comparison, so you can resume later with the same researcher name.',
    ].forEach((t) => ul.appendChild(el('li', '', t)));
    sec.appendChild(ul);
    const label = alreadyAnswered ? `Resume (${alreadyAnswered}/${pairs.length} complete) →` : `Start ${pairs.length} comparisons →`;
    const btn = el('button', 'btn-primary', label);
    btn.addEventListener('click', () => renderPair(startIndex));
    sec.appendChild(btn);
    app.replaceChildren(sec);
    window.scrollTo(0, 0);
  }

  function renderPair(index) {
    const pair = pairs[index];
    const left = pair.aOnLeft ? pair.a : pair.b;
    const right = pair.aOnLeft ? pair.b : pair.a;
    const frag = document.createDocumentFragment();

    const prog = el('div', 'study-progress');
    prog.appendChild(el('div', 'progress-label', `Comparison ${index + 1} of ${pairs.length}`));
    const bar = el('div', 'progress-bar');
    const fill = el('div', 'progress-fill'); fill.style.width = `${(index / pairs.length) * 100}%`; bar.appendChild(fill); prog.appendChild(bar);
    frag.appendChild(prog);
    frag.appendChild(el('div', 'breadcrumb', pair.label));
    frag.appendChild(el('p', 'question-text', 'Read both conversations, then rate relative empathy.'));

    const grid = el('div', 'comparison-grid');
    grid.appendChild(conversationCard('Conversation A', left.turns));
    grid.appendChild(conversationCard('Conversation B', right.turns));
    frag.appendChild(grid);

    let empathy = null;
    const block = buildComparativeLikert7(
      'Which conversation has the more empathetic therapist answers?',
      'A much more empathetic',
      'About the same',
      'B much more empathetic',
      (v) => { empathy = v; block.classList.remove('rq-block--missing'); }
    );
    block.classList.add('empathy-validation-rating');
    frag.appendChild(block);

    const optional = el('div', 'rq-block');
    optional.appendChild(el('p', 'rq-label', 'Optional note: what drove your empathy rating?'));
    const note = el('textarea', 'rq-textarea'); note.rows = 3; optional.appendChild(note); frag.appendChild(optional);

    const err = el('p', 'form-error'); err.hidden = true; frag.appendChild(err);
    const btn = el('button', 'btn-primary btn-next', index < pairs.length - 1 ? 'Next comparison →' : 'Submit responses');
    btn.addEventListener('click', async () => {
      if (empathy === null) { block.classList.add('rq-block--missing'); err.textContent = 'Please select an empathy rating.'; err.hidden = false; block.scrollIntoView({ behavior: 'smooth', block: 'center' }); return; }
      const response = {
        pair_key: pair.key,
        category: pair.category,
        conv_a_file: pair.aOnLeft ? 'a' : 'b',
        empathy_rating: empathy,
        note: note.value.trim(),
      };
      responses[index] = response;
      await saveProgress(response);
      if (index < pairs.length - 1) renderPair(index + 1); else submitResponses();
    });
    frag.appendChild(btn);
    app.replaceChildren(frag);
    window.scrollTo(0, 0);
  }

  function buildComparativeLikert7(question, minLabel, midLabel, maxLabel, onChange) {
    const wrap = el('div', 'rq-block');
    wrap.appendChild(el('p', 'rq-label', question));
    const row = el('div', 'likert7-row');
    row.appendChild(el('span', 'l7-anchor l7-anchor--left', `1 — ${minLabel}`));
    const btns = [];
    for (let v = 1; v <= 7; v++) {
      const btn = el('button', 'scale-btn', String(v));
      btn.type = 'button'; btn.dataset.value = String(v);
      btn.addEventListener('click', () => { btns.forEach((b) => b.classList.remove('selected')); btn.classList.add('selected'); onChange(v); });
      if (v === 4) {
        const mid = el('div', 'l7-mid-wrap');
        mid.appendChild(btn); mid.appendChild(el('span', 'l7-mid-label', midLabel)); row.appendChild(mid);
      } else row.appendChild(btn);
      btns.push(btn);
    }
    row.appendChild(el('span', 'l7-anchor l7-anchor--right', `7 — ${maxLabel}`));
    wrap.appendChild(row);
    return wrap;
  }

  function renderPendingFinalize() {
    const sec = el('section', 'study-hero study-hero--centered');
    sec.appendChild(el('h2', '', 'Almost done'));
    sec.appendChild(el('p', 'lede', 'All comparisons have already been answered. Click below to finalize them.'));
    const btn = el('button', 'btn-primary', 'Submit responses →');
    btn.addEventListener('click', submitResponses);
    sec.appendChild(btn);
    app.replaceChildren(sec);
  }

  function renderAlreadyCompleted() { renderStatusScreen('Already submitted', 'This researcher has already finalized this empathy validation session.'); }
  async function saveProgress(response) { try { await fetch(api('save-response'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username, session_id: sessionId, response }) }); } catch { /* final submit is fallback */ } }
  async function submitResponses() {
    renderStatusScreen('Submitting…', 'Please wait while your responses are saved.');
    const payload = { username, session_id: sessionId, submitted_at: new Date().toISOString(), responses: responses.filter(Boolean) };
    try {
      const res = await fetch(api('submit'), { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
      if (!res.ok) throw new Error(`Server responded with ${res.status}`);
      renderStatusScreen('Thank you!', 'Your empathy validation responses have been recorded.');
    } catch (err) { renderStatusScreen('Submission error', `Could not save responses: ${err.message}`); }
  }

  function conversationCard(title, turns) { const card = el('article', 'conversation-card'); const hdr = el('header'); const line = el('div', 'card-title-line'); line.appendChild(el('div', 'conversation-title', title)); hdr.appendChild(line); hdr.appendChild(speakerKey()); card.appendChild(hdr); const turnsEl = el('section', 'turns'); const list = el('div', 'turn-list'); for (const turn of turns) { const item = el('div', `turn ${turn.role}`); item.appendChild(el('div', 'turn-text', turn.text)); list.appendChild(item); } turnsEl.appendChild(list); card.appendChild(turnsEl); return card; }
  function speakerKey() { const key = el('div', 'speaker-key'); key.appendChild(el('span', 'speaker-pill assistant', 'Therapist')); key.appendChild(el('span', 'speaker-pill user', 'User')); return key; }
  function renderStatusScreen(title, body) { const sec = el('section', 'study-hero study-hero--centered'); sec.appendChild(el('h1', '', title)); sec.appendChild(el('p', 'lede', body)); app.replaceChildren(sec); window.scrollTo(0, 0); }
  function notice(title, body) { const sec = el('section', 'notice'); sec.appendChild(el('h1', '', title)); sec.appendChild(el('p', '', body)); return sec; }
  function sessionKey(name) { return 'empathy_validation_session_' + name.toLowerCase(); }
  function getOrCreateSessionId(name) { let id = localStorage.getItem(sessionKey(name)); if (!id) { id = uid(); localStorage.setItem(sessionKey(name), id); } return id; }
  function uid() { return crypto.randomUUID ? crypto.randomUUID() : Math.random().toString(36).slice(2) + Date.now().toString(36); }
  function el(tag, className, text) { const node = document.createElement(tag); if (className) node.className = className; if (text !== undefined) node.textContent = text; return node; }
  function hashStr(s) { let h = 2166136261 >>> 0; for (let i = 0; i < s.length; i++) { h ^= s.charCodeAt(i); h = Math.imul(h, 16777619) >>> 0; } return h; }
  function seededBool(seed) { return makeRng(seed)() < 0.5; }
  function makeRng(seed) { let s = seed >>> 0; return function () { s = (s + 0x6D2B79F5) >>> 0; let t = Math.imul(s ^ (s >>> 15), 1 | s); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; }; }
  function seededShuffle(arr, seed) { const rng = makeRng(seed); const result = arr.slice(); for (let i = result.length - 1; i > 0; i--) { const j = Math.floor(rng() * (i + 1)); [result[i], result[j]] = [result[j], result[i]]; } return result; }
})();
