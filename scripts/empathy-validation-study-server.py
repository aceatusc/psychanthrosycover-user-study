"""
Flask backend for the internal empathy validation study.

Usage (from repository root):
    pip install -r scripts/requirements.txt
    node scripts/build-pages.mjs
    python scripts/empathy-validation-study-server.py [--port 5333]
    open http://localhost:5333/empathy-validation-study.html

Environment variables:
    PORT      Flask port (default 5333, overridden by --port)
    SITE_DIR  Static files directory (default _site)
    DB_PATH   SQLite database file (default empathy-validation-study/empathy-validation-study.db)
"""

import argparse
import os
import sqlite3
import threading
from collections import Counter
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

REPO_ROOT = Path(__file__).resolve().parents[1]
STUDY_DIR = REPO_ROOT / 'empathy-validation-study'

app = Flask(__name__)
CORS(app)

_parser = argparse.ArgumentParser()
_parser.add_argument('--port', type=int, default=int(os.environ.get('PORT', 5333)))
_args = _parser.parse_args()
PORT = _args.port
SITE_DIR = os.path.abspath(os.environ.get('SITE_DIR', REPO_ROOT / '_site'))
DB_PATH = os.environ.get('DB_PATH', STUDY_DIR / 'empathy-validation-study.db')
_lock = threading.Lock()

CREATE_RESPONSES = """
CREATE TABLE IF NOT EXISTS empathy_validation_responses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT NOT NULL,
    session_id      TEXT NOT NULL,
    submitted_at    TEXT,
    ingested_at     TEXT NOT NULL,
    pair_key        TEXT NOT NULL,
    category        TEXT,
    conv_a_file     TEXT NOT NULL,
    empathy_rating  INTEGER NOT NULL,
    note            TEXT,
    UNIQUE(username, session_id, pair_key)
)
"""


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA journal_mode=WAL')
    return conn


def init_db():
    STUDY_DIR.mkdir(parents=True, exist_ok=True)
    with get_db() as conn:
        conn.execute(CREATE_RESPONSES)
        conn.commit()


def _row(username, session_id, submitted_at, response):
    return (
        username,
        session_id,
        submitted_at,
        datetime.now(timezone.utc).isoformat(),
        response.get('pair_key'),
        response.get('category'),
        response.get('conv_a_file'),
        response.get('empathy_rating'),
        response.get('note', ''),
    )


def _upsert(conn, rows):
    conn.executemany(
        """INSERT INTO empathy_validation_responses
           (username, session_id, submitted_at, ingested_at, pair_key, category,
            conv_a_file, empathy_rating, note)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(username, session_id, pair_key) DO UPDATE SET
             submitted_at   = COALESCE(excluded.submitted_at, empathy_validation_responses.submitted_at),
             ingested_at    = excluded.ingested_at,
             category       = excluded.category,
             conv_a_file    = excluded.conv_a_file,
             empathy_rating = excluded.empathy_rating,
             note           = excluded.note
        """,
        rows,
    )


@app.route('/save-response', methods=['POST'])
@app.route('/empathy-save-response', methods=['POST'])
def save_response():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    session_id = (data.get('session_id') or '').strip()
    response = data.get('response') or {}
    if not username or not session_id or not response.get('pair_key') or response.get('empathy_rating') is None:
        return jsonify(ok=False, error='missing fields'), 400
    with _lock:
        with get_db() as conn:
            _upsert(conn, [_row(username, session_id, None, response)])
            conn.commit()
    return jsonify(ok=True)


@app.route('/progress')
@app.route('/empathy-progress')
def progress():
    username = request.args.get('username', '').strip()
    requested_session_id = request.args.get('session_id', '').strip()
    if not username:
        return jsonify(ok=False, error='missing username'), 400
    with get_db() as conn:
        session_id = requested_session_id
        rows = []
        if session_id:
            rows = conn.execute(
                'SELECT pair_key, submitted_at FROM empathy_validation_responses WHERE username = ? AND session_id = ?',
                (username, session_id),
            ).fetchall()
        if not rows:
            latest = conn.execute(
                """SELECT session_id FROM empathy_validation_responses
                   WHERE username = ?
                   GROUP BY session_id
                   ORDER BY MAX(ingested_at) DESC
                   LIMIT 1""",
                (username,),
            ).fetchone()
            if latest:
                session_id = latest['session_id']
                rows = conn.execute(
                    'SELECT pair_key, submitted_at FROM empathy_validation_responses WHERE username = ? AND session_id = ?',
                    (username, session_id),
                ).fetchall()
    return jsonify(
        ok=True,
        session_id=session_id or requested_session_id,
        completed=bool(rows) and all(r['submitted_at'] is not None for r in rows),
        answered_pair_keys=[r['pair_key'] for r in rows],
    )


@app.route('/submit', methods=['POST'])
@app.route('/empathy-submit', methods=['POST'])
def submit():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get('username') or '').strip()
    session_id = (data.get('session_id') or '').strip()
    submitted_at = data.get('submitted_at') or datetime.now(timezone.utc).isoformat()
    responses = data.get('responses') or []
    if not username or not session_id:
        return jsonify(ok=False, error='missing fields'), 400
    with _lock:
        with get_db() as conn:
            if responses:
                _upsert(conn, [_row(username, session_id, submitted_at, r) for r in responses])
            conn.execute(
                'UPDATE empathy_validation_responses SET submitted_at = COALESCE(submitted_at, ?) WHERE username = ? AND session_id = ?',
                (submitted_at, username, session_id),
            )
            conn.commit()
    app.logger.info('empathy validation finalized %s/%s (%d responses)', username, session_id, len(responses))
    return jsonify(ok=True)


def _agreement_stats(items):
    """items is a list of (rating_a, rating_b) tuples."""
    n = len(items)
    if n == 0:
        return {'n': 0, 'exact_agreement': None, 'cohen_kappa': None, 'agreements': 0}
    agreements = sum(1 for a, b in items if a == b)
    exact = agreements / n
    a_counts = Counter(a for a, _ in items)
    b_counts = Counter(b for _, b in items)
    labels = set(a_counts) | set(b_counts)
    expected = sum((a_counts[label] / n) * (b_counts[label] / n) for label in labels)
    kappa = None if expected == 1 else (exact - expected) / (1 - expected)
    return {'n': n, 'exact_agreement': exact, 'cohen_kappa': kappa, 'agreements': agreements}


@app.route('/agreement')
@app.route('/empathy-agreement')
def agreement():
    """
    Inter-rater agreement over finalized empathy-validation sessions.

    Optional query params:
      users=Sadra,Yalda      only include these usernames
    """
    requested_users = [u.strip() for u in request.args.get('users', '').split(',') if u.strip()]

    with get_db() as conn:
        session_rows = conn.execute(
            """SELECT username, session_id, MAX(submitted_at) AS submitted_at
               FROM empathy_validation_responses
               WHERE submitted_at IS NOT NULL
               GROUP BY username, session_id"""
        ).fetchall()
        latest = {}
        for row in session_rows:
            if requested_users and row['username'] not in requested_users:
                continue
            prev = latest.get(row['username'])
            if prev is None or (row['submitted_at'] or '') > (prev['submitted_at'] or ''):
                latest[row['username']] = dict(row)

        by_user = {}
        for username, sess in latest.items():
            rows = conn.execute(
                """SELECT pair_key, empathy_rating FROM empathy_validation_responses
                   WHERE username = ? AND session_id = ? AND submitted_at IS NOT NULL""",
                (username, sess['session_id']),
            ).fetchall()
            by_user[username] = {row['pair_key']: row['empathy_rating'] for row in rows}

    raters = sorted(by_user)
    rater_pairs = []
    pooled = []
    comparison_keys_with_two_plus = set()
    for left_user, right_user in combinations(raters, 2):
        common_keys = sorted(set(by_user[left_user]) & set(by_user[right_user]))
        comparison_keys_with_two_plus.update(common_keys)
        items = [(by_user[left_user][key], by_user[right_user][key]) for key in common_keys]
        pooled.extend(items)
        rater_pairs.append({
            'raters': [left_user, right_user],
            'n_comparisons': len(common_keys),
            'comparison_keys': common_keys,
            'empathy': _agreement_stats(items),
        })

    common_all_raters = []
    if raters:
        common_all_raters = sorted(set.intersection(*(set(by_user[u]) for u in raters)))

    return jsonify(
        ok=True,
        filters={'users': requested_users or raters},
        raters=raters,
        n_raters=len(raters),
        comparison_set={
            'with_two_or_more_raters': sorted(comparison_keys_with_two_plus),
            'common_to_all_included_raters': common_all_raters,
        },
        rater_pairs=rater_pairs,
        overall={'empathy': _agreement_stats(pooled)},
    )


@app.route('/health')
@app.route('/empathy-health')
def health():
    with get_db() as conn:
        rows = conn.execute('SELECT COUNT(*) FROM empathy_validation_responses').fetchone()[0]
        sessions = conn.execute('SELECT COUNT(DISTINCT username || session_id) FROM empathy_validation_responses WHERE submitted_at IS NOT NULL').fetchone()[0]
    return jsonify(ok=True, submitted_sessions=sessions, response_rows=rows)


@app.route('/', defaults={'filename': 'empathy-validation-study.html'})
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(SITE_DIR, filename)


if __name__ == '__main__':
    init_db()
    print(f'Empathy validation study server → http://localhost:{PORT}/empathy-validation-study.html')
    print(f'Static files                     : {SITE_DIR}')
    print(f'Database                         : {os.path.abspath(DB_PATH)}')
    app.run(host='0.0.0.0', port=PORT, debug=False)
