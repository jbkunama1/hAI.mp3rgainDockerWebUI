import os
import shutil
import subprocess
import uuid
import zipfile
import json
import re
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from flask import Flask, request, redirect, url_for, render_template_string, send_file, send_from_directory, flash
from werkzeug.utils import secure_filename

app = Flask(__name__, static_folder=None)  # Flask internen /static/-Handler deaktivieren
app.secret_key = 'mp3rgain-webui-secret-2024'
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 2 * 1024 * 1024 * 1024))

APP_PORT          = int(os.environ.get('APP_PORT', '8099'))
INPUT_DIR         = Path(os.environ.get('INPUT_DIR',  '/music/in'))
OUTPUT_DIR        = Path(os.environ.get('OUTPUT_DIR', '/music/out'))
TEMP_DIR          = Path(os.environ.get('TEMP_DIR',   '/tmp/mp3rgain-jobs'))
DEFAULT_TARGET_DB = int(os.environ.get('TARGET_DB',   '101'))
JOB_MAX_AGE_DAYS  = int(os.environ.get('JOB_MAX_AGE_DAYS', '7'))
ALLOWED_EXTENSIONS = {'.mp3'}
APP_ROOT = Path(__file__).parent

for p in (INPUT_DIR, OUTPUT_DIR, TEMP_DIR):
    p.mkdir(parents=True, exist_ok=True)

TEMPLATE = """
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>mp3rgain WebUI</title>
  <style>
    :root{--bg:#0f172a;--panel:#111827;--panel2:#1f2937;--text:#e5e7eb;--muted:#94a3b8;--line:#334155;--primary:#14b8a6;--warn:#f59e0b;--danger:#ef4444;--radius:16px}
    *{box-sizing:border-box}body{margin:0;font-family:Inter,Arial,sans-serif;background:linear-gradient(180deg,#020617,#0f172a);color:var(--text)}
    .wrap{max-width:1200px;margin:0 auto;padding:24px}
    .banner{width:100%;border-radius:var(--radius);overflow:hidden;margin-bottom:24px;box-shadow:0 8px 32px rgba(0,0,0,.4)}
    .banner img{width:100%;display:block;height:auto}
    .hero{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:24px;flex-wrap:wrap}
    .hero-left{display:flex;align-items:center;gap:16px}
    .hero-logo{width:56px;height:56px;border-radius:12px;object-fit:cover;flex-shrink:0}
    .hero h1{margin:0;font-size:clamp(1.6rem,3vw,2.4rem)}.hero p{margin:.4rem 0 0;color:var(--muted)}
    .card{background:rgba(17,24,39,.9);border:1px solid var(--line);border-radius:var(--radius);padding:20px;box-shadow:0 10px 30px rgba(0,0,0,.3);margin-bottom:20px}
    h2{margin:0 0 16px;font-size:1.1rem}
    .grid2{display:grid;grid-template-columns:1fr 1fr;gap:16px}
    .grid3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
    label{display:block;font-size:.9rem;color:#cbd5e1;margin-bottom:6px;font-weight:500}
    input[type=text],input[type=number],select{width:100%;padding:11px 14px;border-radius:12px;border:1px solid var(--line);background:var(--panel2);color:var(--text);font-size:.95rem}
    input[type=file]{width:100%;padding:12px;border:2px dashed #475569;border-radius:12px;background:#0b1220;color:var(--muted)}
    .btn{display:inline-flex;align-items:center;gap:6px;padding:11px 18px;border-radius:12px;border:none;font-weight:700;cursor:pointer;text-decoration:none;font-size:.95rem}
    .btn-primary{background:var(--primary);color:#042f2e}
    .btn-secondary{background:#334155;color:var(--text)}
    .btn-warn{background:var(--warn);color:#1c1917}
    .btn-danger{background:var(--danger);color:#fff}
    .btn-sm{padding:5px 11px;font-size:.82rem;border-radius:9px}
    .actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:16px}
    .flash{padding:12px 16px;border-radius:12px;margin-bottom:14px;background:#172554;border:1px solid #3730a3}
    .flash.ok{background:#052e16;border-color:#166534}
    .flash.error{background:#450a0a;border-color:#991b1b}
    table{width:100%;border-collapse:collapse}
    th,td{padding:10px 8px;border-bottom:1px solid #1e2d3d;text-align:left;font-size:.9rem;vertical-align:middle}
    th{color:var(--muted);font-weight:600;font-size:.82rem;text-transform:uppercase;letter-spacing:.05em}
    code{background:#0b1220;padding:2px 7px;border-radius:8px;color:#99f6e4;font-size:.88rem}
    .badge{display:inline-block;padding:3px 9px;border-radius:999px;font-size:.78rem;font-weight:600}
    .badge-ok{background:#052e16;color:#4ade80;border:1px solid #166534}
    .badge-warn{background:#451a03;color:#fbbf24;border:1px solid #92400e}
    .badge-muted{background:#1e293b;color:var(--muted);border:1px solid var(--line)}
    .badge-age{background:#1e1b4b;color:#a5b4fc;border:1px solid #3730a3;font-size:.75rem}
    .tag{display:inline-block;padding:4px 10px;border-radius:999px;background:#0f766e22;color:#99f6e4;border:1px solid #134e4a;font-size:.78rem}
    .sep{border:none;border-top:1px solid var(--line);margin:20px 0}
    .db-bar-wrap{background:#1e293b;border-radius:999px;height:8px;width:120px;display:inline-block;vertical-align:middle;margin-left:8px}
    .db-bar{height:8px;border-radius:999px;background:var(--primary)}
    .step-header{display:flex;align-items:center;gap:12px;margin-bottom:16px}
    .step-num{width:28px;height:28px;border-radius:50%;background:var(--primary);color:#042f2e;font-weight:800;display:flex;align-items:center;justify-content:center;font-size:.9rem;flex-shrink:0}
    .hint{font-size:.85rem;color:var(--muted);margin-top:4px}
    .jobs-header{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;flex-wrap:wrap;gap:8px}
    .jobs-header h2{margin:0}
    .autodel-info{font-size:.82rem;color:var(--muted);margin-top:6px}
    details summary{cursor:pointer;color:var(--primary);font-size:.85rem;font-weight:600}
    details ul{margin:6px 0 0;padding-left:16px;font-size:.82rem;color:#99f6e4;list-style:disc}
    details ul li{margin-bottom:2px}
    @media(max-width:800px){.grid2,.grid3{grid-template-columns:1fr}}
  </style>
</head>
<body>
<div class="wrap">

  <!-- BANNER -->
  <div class="banner">
    <img src="/assets/banner_mp3gain.png" alt="mp3rgain WebUI Banner">
  </div>

  <!-- HERO -->
  <div class="hero">
    <div class="hero-left">
      <img class="hero-logo" src="/assets/logo_mp3gainUI.png" alt="Logo">
      <div>
        <h1>&#127911; mp3rgain WebUI</h1>
        <p>Verlustlose MP3-Lautst&auml;rkeanpassung &ndash; Analyse &rarr; Ziel setzen &rarr; Anwenden</p>
      </div>
    </div>
    <div class="tag">Port {{ port }}</div>
  </div>

  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}{% for cat, msg in messages %}<div class="flash {{ cat }}">{{ msg }}</div>{% endfor %}{% endif %}
  {% endwith %}

  <!-- SCHRITT 1 -->
  <div class="card">
    <div class="step-header"><div class="step-num">1</div><h2 style="margin:0">Dateien analysieren</h2></div>
    <form action="/analyze" method="post" enctype="multipart/form-data">
      <div class="grid2">
        <div>
          <label>Quelle</label>
          <select name="source_type" onchange="toggleSrc(this.value)">
            <option value="mounted">Gemounteter Eingabeordner</option>
            <option value="upload">Datei-Upload</option>
          </select>
        </div>
        <div id="box-subdir">
          <label>Unterordner in <code>{{ input_dir }}</code> (leer = alles)</label>
          <input type="text" name="subdir" placeholder="z. B. alben/2024">
        </div>
        <div id="box-upload" style="display:none">
          <label>MP3-Dateien hochladen</label>
          <input type="file" name="files" accept=".mp3,audio/mpeg" multiple>
        </div>
      </div>
      <div class="actions">
        <button class="btn btn-primary" type="submit">&#128269; Analysieren</button>
      </div>
    </form>
  </div>

  <!-- SCHRITT 2 -->
  {% if analysis %}
  <div class="card">
    <div class="step-header"><div class="step-num">2</div><h2 style="margin:0">Analyseergebnis &amp; Ziel festlegen</h2></div>
    <table>
      <thead><tr><th>Datei</th><th>Ist-Lautst&auml;rke</th><th>Diff zu Ziel ({{ default_target_db }} dB)</th><th>Clipping?</th></tr></thead>
      <tbody>
        {% for f in analysis.files %}
        <tr>
          <td><code>{{ f.name }}</code></td>
          <td>
            {% if f.db != '?' %}{{ f.db }} dB
              <span class="db-bar-wrap"><span class="db-bar" style="width:{{ f.bar_pct }}%"></span></span>
            {% else %}<span class="badge badge-muted">?</span>{% endif %}
          </td>
          <td>
            {% if f.diff_num is not none %}
              {% if f.diff_num > 0 %}<span class="badge badge-warn">+{{ f.diff }} dB</span>
              {% elif f.diff_num < 0 %}<span class="badge badge-ok">{{ f.diff }} dB</span>
              {% else %}<span class="badge badge-muted">=Ziel</span>{% endif %}
            {% else %}<span class="badge badge-muted">?</span>{% endif %}
          </td>
          <td>{% if f.clipping %}<span class="badge badge-warn">&#9888; Ja</span>{% else %}<span class="badge badge-muted">Nein</span>{% endif %}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    <hr class="sep">
    <form action="/apply" method="post">
      <input type="hidden" name="session_id" value="{{ analysis.session_id }}">
      <div class="grid3">
        <div>
          <label>Ziel-dB</label>
          <input type="number" name="target_db" value="{{ default_target_db }}" min="60" max="120" required>
          <p class="hint">Standard {{ default_target_db }} dB &bull; erlaubt 60&ndash;120</p>
        </div>
        <div>
          <label>Modus</label>
          <select name="mode">
            <option value="track">Track Gain &ndash; jede Datei einzeln</option>
            <option value="album">Album Gain &ndash; alle als Album</option>
            <option value="undo">Undo &ndash; R&uuml;ckg&auml;ngig</option>
          </select>
        </div>
        <div style="display:flex;flex-direction:column;justify-content:flex-end">
          <div class="actions" style="margin-top:0">
            <button class="btn btn-warn" type="submit">&#9889; Anwenden</button>
            <a class="btn btn-secondary" href="/">Abbrechen</a>
          </div>
        </div>
      </div>
    </form>
  </div>
  {% endif %}

  <!-- JOBS -->
  <div class="card">
    <div class="jobs-header">
      <div>
        <h2>&#128230; Abgeschlossene Jobs</h2>
        <p class="autodel-info">&#128465; Automatische L&ouml;schung nach {{ max_age_days }} Tagen &bull; konfigurierbar via <code>JOB_MAX_AGE_DAYS</code></p>
      </div>
      {% if jobs %}
      <form action="/delete_all_jobs" method="post" onsubmit="return confirm('Wirklich alle Jobs l\u00f6schen?')">
        <button class="btn btn-danger btn-sm" type="submit">&#128465; Alle l&ouml;schen</button>
      </form>
      {% endif %}
    </div>
    {% if jobs %}
    <table>
      <thead><tr><th>Zeit</th><th>Modus</th><th>Ziel-dB</th><th>Songs</th><th>Alter</th><th>Aktionen</th></tr></thead>
      <tbody>
        {% for job in jobs %}
        <tr>
          <td>{{ job.created }}</td>
          <td><span class="badge badge-muted">{{ job.mode }}</span></td>
          <td><code>{{ job.target_db }} dB</code></td>
          <td>
            <details>
              <summary>{{ job.count }} Song(s)</summary>
              <ul>
                {% for fname in job.file_names %}
                  <li><code>{{ fname }}</code></li>
                {% else %}
                  <li style="color:var(--muted)">Keine Dateien gefunden</li>
                {% endfor %}
              </ul>
            </details>
          </td>
          <td><span class="badge badge-age">{{ job.age }}</span></td>
          <td style="display:flex;gap:8px;flex-wrap:wrap">
            <a class="btn btn-secondary btn-sm" href="/download/{{ job.id }}">&#11123; ZIP</a>
            <form action="/delete_job/{{ job.id }}" method="post" onsubmit="return confirm('Job {{ job.id }} l\u00f6schen?')" style="margin:0">
              <button class="btn btn-danger btn-sm" type="submit">&#128465;</button>
            </form>
          </td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
    {% else %}<p style="color:var(--muted)">Noch keine Jobs vorhanden.</p>{% endif %}
  </div>
</div>
<script>
function toggleSrc(v){
  document.getElementById('box-subdir').style.display = v==='mounted' ? 'block' : 'none';
  document.getElementById('box-upload').style.display = v==='upload'  ? 'block' : 'none';
}
</script>
</body></html>
"""

# ── Assets-Route (PNG-Dateien aus /app/) ─────────────────────────────────────

@app.route('/assets/<path:filename>')
def assets(filename):
    return send_from_directory(APP_ROOT, filename)

# ── Auto-cleanup background thread ──────────────────────────────────────────

def cleanup_old_jobs():
    """Runs every hour, deletes job folders older than JOB_MAX_AGE_DAYS."""
    while True:
        cutoff = datetime.now() - timedelta(days=JOB_MAX_AGE_DAYS)
        for job_dir in OUTPUT_DIR.glob('job-*'):
            if not job_dir.is_dir():
                continue
            meta = job_dir / 'meta.txt'
            job_time = None
            if meta.exists():
                for line in meta.read_text(encoding='utf-8').splitlines():
                    if line.startswith('created='):
                        try:
                            job_time = datetime.strptime(line.split('=', 1)[1], '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            pass
            if job_time is None:
                job_time = datetime.fromtimestamp(job_dir.stat().st_mtime)
            if job_time < cutoff:
                shutil.rmtree(job_dir, ignore_errors=True)
        time.sleep(3600)

_cleanup_thread = threading.Thread(target=cleanup_old_jobs, daemon=True)
_cleanup_thread.start()

# ── Helpers ───────────────────────────────────────────────────────────────────

def job_age_label(created_str):
    try:
        created = datetime.strptime(created_str, '%Y-%m-%d %H:%M:%S')
        delta = datetime.now() - created
        days  = delta.days
        hours = delta.seconds // 3600
        if days >= 1:
            return f'{days}d'
        return f'{hours}h'
    except Exception:
        return '?'

def gather_mp3s(base):
    return [p for p in base.rglob('*') if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS]

def analyze_files(files, target_db):
    results = []
    for f in files:
        db_val   = None
        clipping = False
        try:
            out = subprocess.run(
                ['mp3rgain', '-s', 's', str(f)],
                capture_output=True, text=True, timeout=30
            )
            combined = out.stdout + out.stderr
            for line in combined.splitlines():
                if f.name in line or str(f) in line:
                    parts = line.split('\t')
                    if len(parts) >= 3:
                        try:
                            db_val = round(float(parts[2]), 1)
                        except ValueError:
                            pass
                if 'clipping' in line.lower():
                    clipping = True
            if db_val is None:
                m = re.search(r'([\-\d\.]+)\s*dB', combined)
                if m:
                    try:
                        db_val = round(float(m.group(1)), 1)
                    except ValueError:
                        pass
        except Exception:
            pass

        if db_val is not None:
            diff_num = round(target_db - db_val, 1)
            bar_pct  = max(0, min(100, round(db_val / 110 * 100)))
            db_str   = str(db_val)
        else:
            diff_num = None
            bar_pct  = 0
            db_str   = '?'

        results.append({
            'name':     f.name,
            'path':     str(f),
            'db':       db_str,
            'bar_pct':  bar_pct,
            'diff':     str(diff_num) if diff_num is not None else '?',
            'diff_num': diff_num,
            'clipping': clipping,
        })
    return results

def run_mp3rgain(mode, files, target_db):
    cmd = ['mp3rgain', f'-d{target_db}']
    if mode == 'track':   cmd.append('-r')
    elif mode == 'album': cmd.append('-a')
    elif mode == 'undo':  cmd.append('-u')
    cmd.extend(str(f) for f in files)
    subprocess.run(cmd, check=True)

def write_meta(job_dir, job_id, mode, count, target_db):
    (job_dir / 'meta.txt').write_text(
        f'job_id={job_id}\ncreated={datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n'
        f'mode={mode}\ncount={count}\ntarget_db={target_db}\n',
        encoding='utf-8')

def zip_dir(src, dest):
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in src.rglob('*'):
            if file.is_file():
                zf.write(file, file.relative_to(src))

def list_jobs():
    jobs = []
    for meta in sorted(OUTPUT_DIR.glob('job-*/meta.txt'), reverse=True):
        data = {}
        for line in meta.read_text(encoding='utf-8').splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                data[k] = v
        created = data.get('created', '')
        job_id  = data.get('job_id', meta.parent.name)

        files_dir  = meta.parent / 'files'
        file_names = sorted([f.name for f in files_dir.rglob('*.mp3')]) if files_dir.exists() else []

        jobs.append({
            'id':         job_id,
            'created':    created,
            'mode':       data.get('mode', ''),
            'count':      data.get('count', '0'),
            'target_db':  data.get('target_db', '?'),
            'age':        job_age_label(created),
            'file_names': file_names,
        })
    return jobs

def save_session_files(session_id, file_paths):
    p = TEMP_DIR / f'session-{session_id}.json'
    p.write_text(json.dumps([str(x) for x in file_paths]), encoding='utf-8')

def load_session_files(session_id):
    p = TEMP_DIR / f'session-{session_id}.json'
    if not p.exists():
        return []
    return [Path(x) for x in json.loads(p.read_text(encoding='utf-8'))]

# ── Routes ────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template_string(TEMPLATE,
        jobs=list_jobs(), analysis=None,
        input_dir=INPUT_DIR, port=APP_PORT,
        default_target_db=DEFAULT_TARGET_DB,
        max_age_days=JOB_MAX_AGE_DAYS)

@app.route('/analyze', methods=['POST'])
def analyze():
    source_type = request.form.get('source_type', 'mounted')
    session_id  = uuid.uuid4().hex
    work_dir    = TEMP_DIR / f'session-{session_id}-files'
    work_dir.mkdir(parents=True, exist_ok=True)
    try:
        if source_type == 'mounted':
            subdir = (request.form.get('subdir') or '').strip().strip('/')
            source = (INPUT_DIR / subdir if subdir else INPUT_DIR).resolve()
            if not str(source).startswith(str(INPUT_DIR.resolve())) or not source.exists():
                flash('Ungueltiger Eingabepfad.', 'error')
                return redirect(url_for('index'))
            src_files = gather_mp3s(source)
            if not src_files:
                flash('Keine MP3-Dateien gefunden.', 'error')
                return redirect(url_for('index'))
            for f in src_files:
                rel  = f.relative_to(source)
                dest = work_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
        else:
            uploads = request.files.getlist('files')
            saved   = 0
            for up in uploads:
                if not up or not up.filename:
                    continue
                name = secure_filename(Path(up.filename).name)
                if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
                    continue
                up.save(work_dir / name)
                saved += 1
            if saved == 0:
                flash('Keine gueltigen MP3-Dateien hochgeladen.', 'error')
                return redirect(url_for('index'))

        files   = gather_mp3s(work_dir)
        results = analyze_files(files, DEFAULT_TARGET_DB)
        save_session_files(session_id, [r['path'] for r in results])
        return render_template_string(TEMPLATE,
            jobs=list_jobs(),
            analysis={'session_id': session_id, 'files': results},
            input_dir=INPUT_DIR, port=APP_PORT,
            default_target_db=DEFAULT_TARGET_DB,
            max_age_days=JOB_MAX_AGE_DAYS)
    except Exception as e:
        shutil.rmtree(work_dir, ignore_errors=True)
        flash(f'Fehler bei Analyse: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/apply', methods=['POST'])
def apply():
    session_id = request.form.get('session_id', '')
    mode       = request.form.get('mode', 'track')
    try:
        target_db = int(request.form.get('target_db') or DEFAULT_TARGET_DB)
        target_db = max(60, min(120, target_db))
    except ValueError:
        target_db = DEFAULT_TARGET_DB

    files = load_session_files(session_id)
    if not files:
        flash('Session abgelaufen – bitte erneut analysieren.', 'error')
        return redirect(url_for('index'))

    job_id  = f'job-{datetime.now().strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:6]}'
    job_dir = OUTPUT_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        run_mp3rgain(mode, files, target_db)
        src_dir   = Path(files[0]).parent
        out_files = job_dir / 'files'
        shutil.copytree(src_dir, out_files, dirs_exist_ok=True)
        write_meta(job_dir, job_id, mode, len(files), target_db)
        zip_dir(out_files, job_dir / f'{job_id}.zip')
        flash(f'Job {job_id}: {len(files)} Datei(en) auf {target_db} dB normiert.', 'ok')
    except subprocess.CalledProcessError as e:
        flash(f'mp3rgain-Fehler: {e}', 'error')
    except Exception as e:
        flash(f'Fehler: {e}', 'error')
    finally:
        shutil.rmtree(TEMP_DIR / f'session-{session_id}-files', ignore_errors=True)
        sess_json = TEMP_DIR / f'session-{session_id}.json'
        if sess_json.exists():
            sess_json.unlink()
    return redirect(url_for('index'))

@app.route('/download/<job_id>')
def download(job_id):
    zip_path = OUTPUT_DIR / job_id / f'{job_id}.zip'
    if not zip_path.exists():
        flash('ZIP nicht gefunden.', 'error')
        return redirect(url_for('index'))
    return send_file(zip_path, as_attachment=True, download_name=zip_path.name)

@app.route('/delete_job/<job_id>', methods=['POST'])
def delete_job(job_id):
    if not re.fullmatch(r'job-[\w\-]+', job_id):
        flash('Ungueltiger Job-ID.', 'error')
        return redirect(url_for('index'))
    job_dir = OUTPUT_DIR / job_id
    if job_dir.exists() and job_dir.is_dir():
        shutil.rmtree(job_dir)
        flash(f'Job {job_id} geloescht.', 'ok')
    else:
        flash('Job nicht gefunden.', 'error')
    return redirect(url_for('index'))

@app.route('/delete_all_jobs', methods=['POST'])
def delete_all_jobs():
    deleted = 0
    for job_dir in OUTPUT_DIR.glob('job-*'):
        if job_dir.is_dir():
            shutil.rmtree(job_dir)
            deleted += 1
    flash(f'{deleted} Job(s) geloescht.', 'ok')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=APP_PORT)
