(function () {
  'use strict';

  // ─── CONFIGURATION ────────────────────────────────────────────────────────
  // Option A — Google Apps Script (free, no server):
  //   1. Create a Google Sheet.
  //   2. In the sheet: Extensions → Apps Script.
  //   3. Paste the doPost function from scripts/study-backend.gs.
  //   4. Deploy → New deployment → Web App.
  //      Execute as: Me  |  Who has access: Anyone
  //   5. Copy the deployment URL here.
  //
  // Option B — Your own server:
  //   Point to any endpoint that accepts a POST with Content-Type: text/plain
  //   whose body is a JSON string (see payload shape in submitResponses below).
  //
  // Leave empty to run in demo mode: responses are logged to the browser console.
  const SUBMIT_URL = 'https://script.google.com/a/macros/usc.edu/s/AKfycbyCj5t8Et3CnEwxr0jo8v8KhFgAmVms3XMJEzV_w8EHEsD44bmawuYaT3FTvFvS7d4exQ/exec';
  // ──────────────────────────────────────────────────────────────────────────

  const pairs = window.STUDY_PAIRS || [];
  const app = document.getElementById('app');
  if (!app) return;

  if (!pairs.length) {
    app.replaceChildren(notice('Study data not loaded', 'Run `node scripts/build-pages.mjs` to generate study-data.js.'));
    return;
  }

  // State
  let participantId = '';
  const sessionId = uid();
  let assignments = [];   // [{pairKey, leftFile}]  — "Conversation A" maps to leftFile
  const responses = [];   // [{pairKey, leftFile, choice}]

  // ─── SEEDED RNG ───────────────────────────────────────────────────────────

  function hashStr(s) {
    let h = 2166136261 >>> 0;
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619) >>> 0;
    }
    return h;
  }

  function seededBool(seed) {
    // mulberry32 — one output value
    let s = seed | 0;
    s = (s + 0x6D2B79F5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) < 2147483648;
  }

  // ─── SCREENS ──────────────────────────────────────────────────────────────

  renderIntro();

  function renderIntro() {
    const frag = document.createDocumentFragment();

    const hero = el('section', 'study-hero');
    hero.appendChild(el('div', 'eyebrow', 'Annotation Study · Task 1'));
    hero.appendChild(el('h1', '', 'Therapy Conversation Quality'));
    const desc = el('p', 'lede', `You will see ${pairs.length} pairs of AI-generated counseling conversations. For each pair, read both conversations carefully and choose which one better follows professional and ethical therapy practices.`);
    hero.appendChild(desc);

    const box = el('div', 'study-box');
    box.appendChild(el('h2', '', 'Before you begin'));
    const ul = el('ul');
    [
      'Read both conversations in full before choosing.',
      'Judge based on professional therapy standards, not personal style preference.',
      'The conversations cover a range of mental health topics.',
      'Your participant ID will be used only to link your responses — it will not be used to identify you.',
    ].forEach((text) => ul.appendChild(el('li', '', text)));
    box.appendChild(ul);
    hero.appendChild(box);

    const form = el('div', 'study-start-form');
    const field = el('div', 'field');
    const lbl = el('label', '', 'Participant ID');
    lbl.setAttribute('for', 'pid-input');
    const input = el('input');
    input.type = 'text';
    input.id = 'pid-input';
    input.placeholder = 'e.g. P01';
    input.autocomplete = 'off';
    field.append(lbl, input);

    const startBtn = el('button', 'btn-primary', 'Start →');
    startBtn.disabled = true;
    input.addEventListener('input', () => { startBtn.disabled = !input.value.trim(); });
    input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && !startBtn.disabled) startBtn.click(); });
    startBtn.addEventListener('click', () => {
      participantId = input.value.trim();
      assignments = pairs.map((pair) => ({
        pairKey: pair.key,
        convAFile: seededBool(hashStr(participantId + '|' + pair.key)) ? 'a' : 'b',
      }));
      renderPair(0);
    });

    form.append(field, startBtn);
    hero.appendChild(form);
    frag.appendChild(hero);
    app.replaceChildren(frag);
    input.focus();
  }

  function renderPair(index) {
    const pair = pairs[index];
    const { convAFile } = assignments[index];
    const convBFile = convAFile === 'a' ? 'b' : 'a';

    const frag = document.createDocumentFragment();

    // Progress
    const prog = el('div', 'study-progress');
    prog.appendChild(el('div', 'progress-label', `Pair ${index + 1} of ${pairs.length}`));
    const bar = el('div', 'progress-bar');
    const fill = el('div', 'progress-fill');
    fill.style.width = `${(index / pairs.length) * 100}%`;
    bar.appendChild(fill);
    prog.appendChild(bar);
    frag.appendChild(prog);

    frag.appendChild(el('div', 'breadcrumb', pair.label));

    // Question
    const q = el('div', 'study-question');
    q.appendChild(el('p', 'question-text', 'Which conversation better follows professional and ethical therapy practices?'));
    frag.appendChild(q);

    // Conversations side by side
    const grid = el('div', 'comparison-grid');
    grid.appendChild(conversationColumn('Conversation A', pair[convAFile].turns));
    grid.appendChild(conversationColumn('Conversation B', pair[convBFile].turns));
    frag.appendChild(grid);

    // Choices
    const choicesRow = el('div', 'study-choices');
    const btnA = choiceBtn('Conversation A');
    const btnB = choiceBtn('Conversation B');
    const btnEq = choiceBtn('Cannot decide');
    choicesRow.append(btnA, btnB, btnEq);
    frag.appendChild(choicesRow);

    const nextBtn = el('button', 'btn-primary btn-next', index < pairs.length - 1 ? 'Next →' : 'Submit responses');
    nextBtn.disabled = true;

    let chosen = null;
    function pick(file, btn) {
      chosen = file;
      [btnA, btnB, btnEq].forEach((b) => b.classList.remove('selected'));
      btn.classList.add('selected');
      nextBtn.disabled = false;
    }
    btnA.addEventListener('click', () => pick(convAFile, btnA));
    btnB.addEventListener('click', () => pick(convBFile, btnB));
    btnEq.addEventListener('click', () => pick('equal', btnEq));

    nextBtn.addEventListener('click', () => {
      responses[index] = { pairKey: pair.key, convAFile, choice: chosen };
      if (index < pairs.length - 1) {
        renderPair(index + 1);
      } else {
        submitResponses();
      }
    });

    frag.appendChild(nextBtn);
    app.replaceChildren(frag);
    window.scrollTo(0, 0);
  }

  function conversationColumn(title, turns) {
    const card = el('article', 'conversation-card');
    const hdr = el('header');
    const titleLine = el('div', 'card-title-line');
    titleLine.appendChild(el('div', 'conversation-title', title));
    hdr.appendChild(titleLine);
    hdr.appendChild(speakerKey());
    card.appendChild(hdr);

    const turnsEl = el('section', 'turns');
    const list = el('div', 'turn-list');
    for (const turn of turns) {
      const item = el('div', `turn ${turn.role}`);
      item.appendChild(el('div', 'turn-text', turn.text));
      list.appendChild(item);
    }
    turnsEl.appendChild(list);
    card.appendChild(turnsEl);
    return card;
  }

  function speakerKey() {
    const key = el('div', 'speaker-key');
    key.appendChild(el('span', 'speaker-pill assistant', 'Therapist'));
    key.appendChild(el('span', 'speaker-pill user', 'User'));
    return key;
  }

  function choiceBtn(text) {
    const btn = el('button', 'choice-btn');
    btn.textContent = text;
    return btn;
  }

  // ─── SUBMISSION ───────────────────────────────────────────────────────────

  async function submitResponses() {
    renderScreen('Submitting…', 'Please wait while your responses are saved.');

    // Payload shape:
    // {
    //   participant_id: string,
    //   session_id:     string,
    //   submitted_at:   ISO string,
    //   responses: [
    //     { pair_key: string, conv_a_file: "a"|"b", choice: "a"|"b"|"equal" },
    //     ...
    //   ]
    // }
    const payload = {
      participant_id: participantId,
      session_id: sessionId,
      submitted_at: new Date().toISOString(),
      responses: responses.map((r) => ({
        pair_key: r.pairKey,
        conv_a_file: r.convAFile,
        choice: r.choice,
      })),
    };

    if (!SUBMIT_URL) {
      console.log('[study] Demo mode — responses not sent. Payload:', JSON.stringify(payload, null, 2));
      setTimeout(() => renderDone(), 600);
      return;
    }

    try {
      // text/plain is required for no-cors cross-origin POST (Apps Script compatible).
      await fetch(SUBMIT_URL, {
        method: 'POST',
        mode: 'no-cors',
        headers: { 'Content-Type': 'text/plain' },
        body: JSON.stringify(payload),
      });
      renderDone();
    } catch (err) {
      renderScreen('Submission error', `Could not save responses: ${err.message}. Please contact the researcher.`);
    }
  }

  function renderScreen(title, body) {
    const sec = el('section', 'study-hero');
    sec.appendChild(el('h1', '', title));
    sec.appendChild(el('p', 'lede', body));
    app.replaceChildren(sec);
    window.scrollTo(0, 0);
  }

  function renderDone() {
    const sec = el('section', 'study-hero');
    sec.appendChild(el('div', 'eyebrow', 'Complete'));
    sec.appendChild(el('h1', '', 'Thank you!'));
    sec.appendChild(el('p', 'lede', 'Your responses have been recorded. You may now close this tab.'));
    app.replaceChildren(sec);
    window.scrollTo(0, 0);
  }

  // ─── HELPERS ──────────────────────────────────────────────────────────────

  function notice(title, body) {
    const sec = el('section', 'notice');
    sec.appendChild(el('h1', '', title));
    sec.appendChild(el('p', '', body));
    return sec;
  }

  function uid() {
    if (typeof crypto !== 'undefined' && crypto.randomUUID) return crypto.randomUUID();
    return Math.random().toString(36).slice(2) + Date.now().toString(36);
  }

  function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }
})();
