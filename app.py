import os
import shutil
import subprocess
import uuid
import zipfile
from pathlib import Path
from datetime import datetime
from flask import Flask, request, redirect, url_for, render_template_string, send_file, flash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'mp3rgain-webui-secret'
app.config['MAX_CONTENT_LENGTH'] = int(os.environ.get('MAX_CONTENT_LENGTH', 2 * 1024 * 1024 * 1024))

APP_PORT = int(os.environ.get('APP_PORT', '8099'))
INPUT_DIR = Path(os.environ.get('INPUT_DIR', '/music/in'))
OUTPUT_DIR = Path(os.environ.get('OUTPUT_DIR', '/music/out'))
TEMP_DIR = Path(os.environ.get('TEMP_DIR', '/tmp/mp3rgain-jobs'))
TARGET_DB = int(os.environ.get('TARGET_DB', '101'))
ALLOWED_EXTENSIONS = {'.mp3'}

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
    :root { --bg:#0f172a; --panel:#111827; --panel2:#1f2937; --text:#e5e7eb; --muted:#94a3b8; --line:#334155; --primary:#14b8a6; --radius:16px; }
    *{box-sizing:border-box} body{margin:0;font-family:Inter,Arial,sans-serif;background:linear-gradient(180deg,#020617,#0f172a);color:var(--text)}
    .wrap{max-width:1100px;margin:0 auto;padding:24px}
    .hero{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-bottom:24px;flex-wrap:wrap}
    .hero h1{margin:0;font-size:clamp(1.8rem,3vw,2.6rem)} .hero p{margin:.4rem 0 0;color:var(--muted)}
    .grid{display:grid;grid-template-columns:1.3fr .9fr;gap:20px}
    .card{background:rgba(17,24,39,.88);border:1px solid var(--line);border-radius:var(--radius);padding:20px;box-shadow:0 10px 30px rgba(0,0,0,.25)}
    h2{margin:0 0 12px;font-size:1.15rem} h3{margin:18px 0 10px;font-size:1rem}
    .row{display:grid;grid-template-columns:1fr 1fr 1fr;gap:14px}
    label{display:block;font-size:.92rem;color:#cbd5e1;margin-bottom:6px}
    input[type=text],input[type=number],select{width:100%;padding:12px 14px;border-radius:12px;border:1px solid var(--line);background:var(--panel2);color:var(--text)}
    input[type=file]{width:100%;padding:12px;border:1px dashed #475569;border-radius:12px;background:#0b1220;color:var(--muted)}
    .hint{font-size:.88rem;color:var(--muted)} .actions{display:flex;gap:12px;flex-wrap:wrap;margin-top:18px}
    button,.btn{background:var(--primary);color:#042f2e;border:none;border-radius:12px;padding:12px 16px;font-weight:700;text-decoration:none;display:inline-block;cursor:pointer}
    .btn.secondary{background:#334155;color:var(--text)}
    .flash{padding:12px 14px;border-radius:12px;margin-bottom:12px;background:#172554;border:1px solid #3730a3}
    table{width:100%;border-collapse:collapse} th,td{padding:10px 8px;border-bottom:1px solid #263244;text-align:left;font-size:.93rem;vertical-align:top}
    code{background:#0b1220;padding:2px 6px;border-radius:8px;color:#99f6e4}
    .tag{display:inline-block;padding:4px 8px;border-radius:999px;background:#0f766e22;color:#99f6e4;border:1px solid #134e4a;font-size:.78rem}
    .muted{color:var(--muted)}
    @media(max-width:880px){.grid,.row{grid-template-columns:1fr}}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div><h1>mp3rgain WebUI</h1><p>Verlustlose MP3-Lautstaerkeanpassung - Ordner-Mount, Upload, Stapelverarbeitung, ZIP-Download.</p></div>
      <div class="tag">Port {{ port }} &nbsp;|&nbsp; Ziel: {{ target_db }} dB</div>
    </div>
    {% with messages = get_flashed_messages() %}{% if messages %}{% for msg in messages %}<div class="flash">{{ msg }}</div>{% endfor %}{% endif %}{% endwith %}
    <div class="grid">
      <div class="card">
        <h2>Verarbeitung starten</h2>
        <form action="/process" method="post" enctype="multipart/form-data">
          <div class="row">
            <div>
              <label>Modus</label>
              <select name="mode">
                <option value="track">Track Gain (-r)</option>
                <option value="album">Album Gain (-a)</option>
                <option value="undo">Undo (-u)</option>
              </select>
            </div>
            <div>
              <label>Quelle</label>
              <select name="source_type" onchange="toggleSource(this.value)">
                <option value="mounted">Gemounteter Eingabeordner</option>
                <option value="upload">Datei-Upload</option>
              </select>
            </div>
            <div>
              <label>Ziel-dB (leer = {{ target_db }} dB)</label>
              <input type="number" name="target_db" placeholder="{{ target_db }}" min="60" max="120">
            </div>
          </div>
          <div id="mounted-box">
            <h3>Gemounteter Ordner</h3>
            <label>Relativer Unterordner in <code>{{ input_dir }}</code> (leer = alles)</label>
            <input type="text" name="subdir" placeholder="z. B. alben/neu">
            <p class="hint">Rekursiv alle .mp3-Dateien werden verarbeitet.</p>
          </div>
          <div id="upload-box" style="display:none">
            <h3>Datei-Upload</h3>
            <label>MP3-Dateien auswaehlen</label>
            <input type="file" name="files" accept=".mp3,audio/mpeg" multiple>
            <p class="hint">Mehrfachauswahl moeglich.</p>
          </div>
          <div class="actions">
            <button type="submit">Job starten</button>
            <a class="btn secondary" href="/">Aktualisieren</a>
          </div>
        </form>
      </div>
      <div class="card">
        <h2>Pfad-Konzept</h2>
        <table>
          <tr><th>Eingabe</th><td><code>{{ input_dir }}</code></td></tr>
          <tr><th>Ausgabe</th><td><code>{{ output_dir }}</code></td></tr>
          <tr><th>Standard-dB</th><td><code>{{ target_db }} dB</code> (via TARGET_DB)</td></tr>
          <tr><th>Originale</th><td>Bleiben unveraendert - wird immer in Job-Ordner kopiert</td></tr>
        </table>
        <h3>Ablauf</h3>
        <table>
          <tr><td>1.</td><td>MP3s in Eingabeordner legen oder hochladen</td></tr>
          <tr><td>2.</td><td>Modus und Ziel-dB waehlen, Job starten</td></tr>
          <tr><td>3.</td><td>ZIP herunterladen</td></tr>
        </table>
      </div>
    </div>
    <div class="card" style="margin-top:20px">
      <h2>Ergebnisse</h2>
      {% if jobs %}
      <table>
        <thead><tr><th>Zeit</th><th>Job-ID</th><th>Modus</th><th>dB</th><th>Dateien</th><th>Download</th></tr></thead>
        <tbody>
          {% for job in jobs %}
          <tr>
            <td>{{ job.created }}</td>
            <td><code>{{ job.id }}</code></td>
            <td>{{ job.mode }}</td>
            <td>{{ job.target_db }}</td>
            <td>{{ job.count }}</td>
            <td><a class="btn secondary" href="/download/{{ job.id }}">ZIP laden</a></td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
      {% else %}<p class="muted">Noch keine Jobs vorhanden.</p>{% endif %}
    </div>
  </div>
  <script>
    function toggleSource(v){
      document.getElementById('mounted-box').style.display=v==='mounted'?'block':'none';
      document.getElementById('upload-box').style.display=v==='upload'?'block':'none';
    }
  </script>
</body>
</html>
"""

def list_jobs():
    jobs = []
    for meta in sorted(OUTPUT_DIR.glob('job-*/meta.txt'), reverse=True):
        root = meta.parent
        data = {}
        for line in meta.read_text(encoding='utf-8').splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                data[k] = v
        jobs.append({'id': data.get('job_id', root.name), 'created': data.get('created', ''),
                     'mode': data.get('mode', ''), 'count': data.get('count', '0'),
                     'target_db': data.get('target_db', '?')})
    return jobs

def gather_mp3s(base):
    return [p for p in base.rglob('*') if p.is_file() and p.suffix.lower() in ALLOWED_EXTENSIONS]

def run_mp3rgain(mode, files, target_db):
    cmd = ['mp3rgain', f'-d{target_db}']
    if mode == 'track': cmd.append('-r')
    elif mode == 'album': cmd.append('-a')
    elif mode == 'undo': cmd.append('-u')
    cmd.extend(str(f) for f in files)
    subprocess.run(cmd, check=True)

def write_meta(job_dir, job_id, mode, count, target_db):
    (job_dir / 'meta.txt').write_text(
        f'job_id={job_id}\ncreated={datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\nmode={mode}\ncount={count}\ntarget_db={target_db}\n',
        encoding='utf-8')

def zip_dir(src, dest):
    with zipfile.ZipFile(dest, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file in src.rglob('*'):
            if file.is_file():
                zf.write(file, file.relative_to(src))

@app.route('/')
def index():
    return render_template_string(TEMPLATE, jobs=list_jobs(),
                                  input_dir=INPUT_DIR, output_dir=OUTPUT_DIR,
                                  port=APP_PORT, target_db=TARGET_DB)

@app.route('/process', methods=['POST'])
def process():
    mode = request.form.get('mode', 'track')
    source_type = request.form.get('source_type', 'mounted')
    try:
        target_db = int(request.form.get('target_db') or TARGET_DB)
        target_db = max(60, min(120, target_db))
    except ValueError:
        target_db = TARGET_DB
    job_id = f'job-{datetime.now().strftime("%Y%m%d-%H%M%S")}-{uuid.uuid4().hex[:6]}'
    job_dir = OUTPUT_DIR / job_id
    work_input = TEMP_DIR / job_id / 'input'
    work_input.mkdir(parents=True, exist_ok=True)
    job_dir.mkdir(parents=True, exist_ok=True)
    try:
        if source_type == 'mounted':
            subdir = (request.form.get('subdir') or '').strip().strip('/')
            source = (INPUT_DIR / subdir if subdir else INPUT_DIR).resolve()
            if not str(source).startswith(str(INPUT_DIR.resolve())) or not source.exists():
                flash('Ungueltiger Eingabepfad.')
                return redirect(url_for('index'))
            files = gather_mp3s(source)
            if not files:
                flash('Keine MP3-Dateien gefunden.')
                return redirect(url_for('index'))
            for f in files:
                rel = f.relative_to(source)
                dest = work_input / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)
        else:
            uploads = request.files.getlist('files')
            saved = 0
            for up in uploads:
                if not up or not up.filename: continue
                name = secure_filename(Path(up.filename).name)
                if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS: continue
                up.save(work_input / name)
                saved += 1
            if saved == 0:
                flash('Keine gueltigen MP3-Dateien hochgeladen.')
                return redirect(url_for('index'))
        files = gather_mp3s(work_input)
        run_mp3rgain(mode, files, target_db)
        out_files = job_dir / 'files'
        shutil.copytree(work_input, out_files, dirs_exist_ok=True)
        write_meta(job_dir, job_id, mode, len(files), target_db)
        zip_dir(out_files, job_dir / f'{job_id}.zip')
        flash(f'Job {job_id} abgeschlossen: {len(files)} Datei(en) @ {target_db} dB.')
    except subprocess.CalledProcessError as e:
        flash(f'mp3rgain-Fehler: {e}')
    except Exception as e:
        flash(f'Fehler: {e}')
    finally:
        shutil.rmtree(TEMP_DIR / job_id, ignore_errors=True)
    return redirect(url_for('index'))

@app.route('/download/<job_id>')
def download(job_id):
    zip_path = OUTPUT_DIR / job_id / f'{job_id}.zip'
    if not zip_path.exists():
        flash('ZIP nicht gefunden.')
        return redirect(url_for('index'))
    return send_file(zip_path, as_attachment=True, download_name=zip_path.name)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=APP_PORT)
