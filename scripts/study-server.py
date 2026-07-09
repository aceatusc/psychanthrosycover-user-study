"""
Flask backend for the validation study — Phase 1.

Usage (from user-study/ directory):
    pip install -r scripts/requirements.txt
    node scripts/build-pages.mjs
    python scripts/study-server.py [--port 5111]
    open http://localhost:5111/study.html

Options:
    --port    Port to listen on (default 5111; overrides PORT env var)

Environment variables:
    PORT      Flask port (default 5111, overridden by --port)
    SITE_DIR  Static files directory (default _site, relative to CWD)
    DB_PATH   SQLite database file (default study.db)

Progressive save endpoints:
    POST /save-demographics  — called after demographics page; creates partial participant row
    POST /save-pair          — called after each pair; upserts that pair's response rows
    GET  /progress           — returns answered pair keys + completion status for resume
    POST /submit             — final submission; marks participant completed (submitted_at set)
"""

import argparse
import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

_parser = argparse.ArgumentParser()
_parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', 5111)))
_args = _parser.parse_args()
PORT = _args.port
SITE_DIR = os.path.abspath(os.environ.get('SITE_DIR', '_site'))
DB_PATH = os.environ.get('DB_PATH', 'study.db')

_lock = threading.Lock()

# submitted_at and session_id are nullable — they are set only when the participant finalizes.
CREATE_PARTICIPANTS = """
CREATE TABLE IF NOT EXISTS participants (
    participant_id      TEXT PRIMARY KEY,
    session_id          TEXT,
    submitted_at        TEXT,
    ingested_at         TEXT NOT NULL,
    field               TEXT,
    education           TEXT,
    licensed            TEXT,
    seeing_clients      TEXT,
    years_experience    TEXT,
    orientation         TEXT,
    ai_familiarity           TEXT,
    ai_appropriateness       TEXT,
    ai_appropriateness_text  TEXT,
    age                      INTEGER,
    gender                   TEXT
)
"""

# UNIQUE on (participant_id, pair_key, conv_label) enables INSERT OR REPLACE for progressive saves.
CREATE_RESPONSES = """
CREATE TABLE IF NOT EXISTS responses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_id  TEXT NOT NULL REFERENCES participants(participant_id),
    pair_key        TEXT NOT NULL,
    conv_a_file     TEXT NOT NULL,
    conv_label      TEXT NOT NULL,
    underlying_file TEXT NOT NULL,
    a1              INTEGER,
    a2              INTEGER,
    b1_flagged      INTEGER,
    b1_text         TEXT,
    b2              INTEGER,
    b3_flagged      INTEGER,
    b3_options      TEXT,
    b3_other        TEXT,
    UNIQUE(participant_id, pair_key, conv_label)
)
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def init_db():
    with get_db() as conn:
        conn.execute(CREATE_PARTICIPANTS)
        conn.execute(CREATE_RESPONSES)
        conn.commit()


def _bool_flag(val):
    """Convert a JSON boolean/None to 0/1/None for the DB."""
    if val is True:
        return 1
    if val is False:
        return 0
    return None


def _response_rows(pid, conv_a_file, pair_key, conv_a_ratings, conv_b_ratings):
    """Build two response rows (one per conversation) from a pair's ratings dicts."""
    conv_b_file = 'b' if conv_a_file == 'a' else 'a'
    rows = []
    for conv_label, underlying, ratings in [
        ('A', conv_a_file, conv_a_ratings),
        ('B', conv_b_file, conv_b_ratings),
    ]:
        rows.append((
            pid, pair_key, conv_a_file, conv_label, underlying,
            ratings.get('a1'), ratings.get('a2'),
            _bool_flag(ratings.get('b1_flagged')), ratings.get('b1_text', ''),
            ratings.get('b2'),
            _bool_flag(ratings.get('b3_flagged')),
            json.dumps(ratings.get('b3_options', [])),
            ratings.get('b3_other', ''),
        ))
    return rows


# ─── Progressive save endpoints ───────────────────────────────────────────────

@app.route('/save-demographics', methods=['POST'])
def save_demographics():
    data = request.get_json(silent=True) or {}
    pid = (data.get('participant_id') or '').strip()
    sid = (data.get('session_id') or '').strip()
    d = data.get('demographics') or {}
    if not pid:
        return jsonify(ok=False, error='missing participant_id'), 400

    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        with get_db() as conn:
            conn.execute("""
                INSERT INTO participants
                    (participant_id, session_id, ingested_at,
                     field, education, licensed, seeing_clients, years_experience,
                     orientation, ai_familiarity, ai_appropriateness, ai_appropriateness_text,
                     age, gender)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(participant_id) DO UPDATE SET
                    session_id               = excluded.session_id,
                    field                    = excluded.field,
                    education                = excluded.education,
                    licensed                 = excluded.licensed,
                    seeing_clients           = excluded.seeing_clients,
                    years_experience         = excluded.years_experience,
                    orientation              = excluded.orientation,
                    ai_familiarity           = excluded.ai_familiarity,
                    ai_appropriateness       = excluded.ai_appropriateness,
                    ai_appropriateness_text  = excluded.ai_appropriateness_text,
                    age                      = excluded.age,
                    gender                   = excluded.gender
                WHERE participants.submitted_at IS NULL
            """, (
                pid, sid, now,
                d.get('field'), d.get('education'), d.get('licensed'),
                d.get('seeing_clients'), d.get('years_experience'),
                d.get('orientation'), d.get('ai_familiarity'),
                d.get('ai_appropriateness'), d.get('ai_appropriateness_text'),
                d.get('age'), d.get('gender'),
            ))
            conn.commit()
    return jsonify(ok=True)


@app.route('/save-pair', methods=['POST'])
def save_pair():
    data = request.get_json(silent=True) or {}
    pid = (data.get('participant_id') or '').strip()
    pair_key = (data.get('pair_key') or '').strip()
    conv_a_file = (data.get('conv_a_file') or '').strip()
    if not pid or not pair_key or not conv_a_file:
        return jsonify(ok=False, error='missing fields'), 400

    rows = _response_rows(
        pid, conv_a_file, pair_key,
        data.get('conv_a_ratings') or {},
        data.get('conv_b_ratings') or {},
    )
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        with get_db() as conn:
            # Ensure a placeholder participant row exists (save-demographics may not have been called yet).
            conn.execute(
                'INSERT OR IGNORE INTO participants (participant_id, ingested_at) VALUES (?,?)',
                (pid, now),
            )
            conn.executemany(
                """INSERT OR REPLACE INTO responses
                   (participant_id, pair_key, conv_a_file, conv_label, underlying_file,
                    a1, a2, b1_flagged, b1_text, b2, b3_flagged, b3_options, b3_other)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                rows,
            )
            conn.commit()
    return jsonify(ok=True)


@app.route('/progress')
def progress():
    pid = request.args.get('participant_id', '').strip()
    if not pid:
        return jsonify(ok=False, error='missing participant_id'), 400
    with get_db() as conn:
        part = conn.execute(
            'SELECT submitted_at, field FROM participants WHERE participant_id = ?', (pid,)
        ).fetchone()
        if not part:
            return jsonify(ok=True, completed=False, demographics_saved=False, answered_pair_keys=[])
        answered = conn.execute(
            "SELECT DISTINCT pair_key FROM responses WHERE participant_id = ? AND conv_label = 'A'",
            (pid,),
        ).fetchall()
    return jsonify(
        ok=True,
        completed=part['submitted_at'] is not None,
        demographics_saved=part['field'] is not None,
        answered_pair_keys=[r['pair_key'] for r in answered],
    )


# ─── Final submission ──────────────────────────────────────────────────────────

@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify(ok=False, error='invalid JSON body'), 400

    try:
        now = datetime.now(timezone.utc).isoformat()
        pid = data['participant_id']
        sid = data.get('session_id', '')
        submitted_at = data['submitted_at']
        demo = data.get('demographics') or {}

        response_rows = []
        for r in (data.get('responses') or []):
            response_rows.extend(_response_rows(
                pid, r['conv_a_file'], r['pair_key'],
                r.get('conv_a_ratings') or {},
                r.get('conv_b_ratings') or {},
            ))

    except (KeyError, TypeError) as exc:
        return jsonify(ok=False, error=f'missing or malformed field: {exc}'), 400

    with _lock:
        with get_db() as conn:
            existing = conn.execute(
                'SELECT submitted_at FROM participants WHERE participant_id = ?', (pid,)
            ).fetchone()
            if existing and existing['submitted_at'] is not None:
                return jsonify(ok=False, error='already_submitted'), 409

            # Upsert participant — COALESCE keeps saved demographics if demo is empty (finalize-only mode).
            conn.execute("""
                INSERT INTO participants
                    (participant_id, session_id, submitted_at, ingested_at,
                     field, education, licensed, seeing_clients, years_experience,
                     orientation, ai_familiarity, ai_appropriateness, ai_appropriateness_text,
                     age, gender)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(participant_id) DO UPDATE SET
                    submitted_at             = excluded.submitted_at,
                    session_id               = COALESCE(excluded.session_id,              participants.session_id),
                    field                    = COALESCE(excluded.field,                   participants.field),
                    education                = COALESCE(excluded.education,               participants.education),
                    licensed                 = COALESCE(excluded.licensed,                participants.licensed),
                    seeing_clients           = COALESCE(excluded.seeing_clients,          participants.seeing_clients),
                    years_experience         = COALESCE(excluded.years_experience,        participants.years_experience),
                    orientation              = COALESCE(excluded.orientation,             participants.orientation),
                    ai_familiarity           = COALESCE(excluded.ai_familiarity,          participants.ai_familiarity),
                    ai_appropriateness       = COALESCE(excluded.ai_appropriateness,      participants.ai_appropriateness),
                    ai_appropriateness_text  = COALESCE(excluded.ai_appropriateness_text, participants.ai_appropriateness_text),
                    age                      = COALESCE(excluded.age,                     participants.age),
                    gender                   = COALESCE(excluded.gender,                  participants.gender)
            """, (
                pid, sid, submitted_at, now,
                demo.get('field'), demo.get('education'), demo.get('licensed'),
                demo.get('seeing_clients'), demo.get('years_experience'),
                demo.get('orientation'), demo.get('ai_familiarity'),
                demo.get('ai_appropriateness'), demo.get('ai_appropriateness_text'),
                demo.get('age'), demo.get('gender'),
            ))

            if response_rows:
                conn.executemany(
                    """INSERT OR REPLACE INTO responses
                       (participant_id, pair_key, conv_a_file, conv_label, underlying_file,
                        a1, a2, b1_flagged, b1_text, b2, b3_flagged, b3_options, b3_other)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    response_rows,
                )
            conn.commit()

    app.logger.info('finalized %s (%d response rows in this submission)', pid, len(response_rows))
    return jsonify(ok=True)


# ─── Utility endpoints ────────────────────────────────────────────────────────

@app.route('/check-status')
def check_status():
    pid = request.args.get('participant_id', '').strip()
    if not pid:
        return jsonify(ok=False, error='missing participant_id'), 400
    with get_db() as conn:
        row = conn.execute(
            'SELECT submitted_at FROM participants WHERE participant_id = ?', (pid,)
        ).fetchone()
    completed = row is not None and row['submitted_at'] is not None
    return jsonify(ok=True, completed=completed)


@app.route('/health')
def health():
    with get_db() as conn:
        participants = conn.execute('SELECT COUNT(*) FROM participants WHERE submitted_at IS NOT NULL').fetchone()[0]
        in_progress  = conn.execute('SELECT COUNT(*) FROM participants WHERE submitted_at IS NULL').fetchone()[0]
        responses    = conn.execute('SELECT COUNT(*) FROM responses').fetchone()[0]
    return jsonify(ok=True, participants=participants, in_progress=in_progress, response_rows=responses)


@app.route('/', defaults={'filename': 'study.html'})
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(SITE_DIR, filename)


if __name__ == '__main__':
    init_db()
    print(f'Study server  → http://localhost:{PORT}/study.html')
    print(f'Static files  : {SITE_DIR}')
    print(f'Database      : {os.path.abspath(DB_PATH)}')
    app.run(host='0.0.0.0', port=PORT, debug=False)
