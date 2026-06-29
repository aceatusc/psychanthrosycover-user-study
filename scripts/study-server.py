"""
Flask backend for the validation study — Phase 1.

Usage (from user-study/ directory):
    pip install -r scripts/requirements.txt
    node scripts/build-pages.mjs
    python scripts/study-server.py
    open http://localhost:5111/study.html

Environment variables:
    PORT      Flask port (default 5111)
    SITE_DIR  Static files directory (default _site, relative to CWD)
    DB_PATH   SQLite database file (default study.db)
"""

import json
import os
import sqlite3
import threading
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

PORT = int(os.environ.get('PORT', 5111))
SITE_DIR = os.path.abspath(os.environ.get('SITE_DIR', '_site'))
DB_PATH = os.environ.get('DB_PATH', 'study.db')

_lock = threading.Lock()

CREATE_PARTICIPANTS = """
CREATE TABLE IF NOT EXISTS participants (
    participant_id      TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL,
    submitted_at        TEXT NOT NULL,
    ingested_at         TEXT NOT NULL,
    field               TEXT,
    education           TEXT,
    licensed            TEXT,
    seeing_clients      TEXT,
    years_experience    TEXT,
    orientation         TEXT,
    ai_familiarity      TEXT,
    ai_appropriateness  INTEGER,
    age                 INTEGER,
    gender              TEXT,
    income              TEXT
)
"""

CREATE_RESPONSES = """
CREATE TABLE IF NOT EXISTS responses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    participant_id  TEXT NOT NULL REFERENCES participants(participant_id),
    pair_key        TEXT NOT NULL,
    conv_a_file     TEXT NOT NULL,   -- which underlying file ('a'|'b') was shown as "Conversation A"
    conv_label      TEXT NOT NULL,   -- display label: 'A' or 'B'
    underlying_file TEXT NOT NULL,   -- actual data file: 'a' or 'b'
    a1              INTEGER,         -- 1–7 professionalism
    a2              INTEGER,         -- 1–7 clinical standards alignment
    b1_flagged      INTEGER,         -- 0 or 1
    b1_text         TEXT,
    b2              INTEGER,         -- 1–7 confidence (B2)
    b3_flagged      INTEGER,         -- 0 or 1 (B3)
    b3_options      TEXT,            -- JSON array of selected option strings
    b3_other        TEXT
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


@app.route('/submit', methods=['POST'])
def submit():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify(ok=False, error='invalid JSON body'), 400

    try:
        now = datetime.now(timezone.utc).isoformat()
        pid = data['participant_id']
        sid = data['session_id']
        submitted_at = data['submitted_at']
        demo = data.get('demographics') or {}

        participant_row = (
            pid, sid, submitted_at, now,
            demo.get('field'), demo.get('education'), demo.get('licensed'),
            demo.get('seeing_clients'), demo.get('years_experience'),
            demo.get('orientation'), demo.get('ai_familiarity'),
            demo.get('ai_appropriateness'), demo.get('age'),
            demo.get('gender'), demo.get('income'),
        )

        response_rows = []
        for r in data['responses']:
            pair_key = r['pair_key']
            conv_a_file = r['conv_a_file']           # 'a' or 'b'
            conv_b_file = 'b' if conv_a_file == 'a' else 'a'

            for conv_label, ratings, underlying in [
                ('A', r['conv_a_ratings'], conv_a_file),
                ('B', r['conv_b_ratings'], conv_b_file),
            ]:
                response_rows.append((
                    pid, pair_key, conv_a_file, conv_label, underlying,
                    ratings.get('a1'), ratings.get('a2'),
                    1 if ratings.get('b1_flagged') else 0, ratings.get('b1_text', ''),
                    ratings.get('b2'),
                    1 if ratings.get('b3_flagged') else 0,
                    json.dumps(ratings.get('b3_options', [])),
                    ratings.get('b3_other', ''),
                ))

    except (KeyError, TypeError) as exc:
        return jsonify(ok=False, error=f'missing or malformed field: {exc}'), 400

    with _lock:
        with get_db() as conn:
            try:
                conn.execute(
                    """INSERT INTO participants
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    participant_row,
                )
            except sqlite3.IntegrityError:
                return jsonify(ok=False, error='already_submitted'), 409
            conn.executemany(
                """INSERT INTO responses
                   (participant_id, pair_key, conv_a_file, conv_label, underlying_file,
                    a1, a2, b1_flagged, b1_text, b2, b3_flagged, b3_options, b3_other)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                response_rows,
            )
            conn.commit()

    app.logger.info('saved %d response rows for participant %s', len(response_rows), pid)
    return jsonify(ok=True)


@app.route('/check-status')
def check_status():
    pid = request.args.get('participant_id', '').strip()
    if not pid:
        return jsonify(ok=False, error='missing participant_id'), 400
    with get_db() as conn:
        exists = conn.execute(
            'SELECT 1 FROM participants WHERE participant_id = ?', (pid,)
        ).fetchone()
    return jsonify(ok=True, completed=exists is not None)


@app.route('/health')
def health():
    with get_db() as conn:
        participants = conn.execute('SELECT COUNT(*) FROM participants').fetchone()[0]
        responses = conn.execute('SELECT COUNT(*) FROM responses').fetchone()[0]
    return jsonify(ok=True, participants=participants, response_rows=responses)


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
