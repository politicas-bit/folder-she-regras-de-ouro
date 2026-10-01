import json
import sqlite3
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / 'readings.db'


def html_escape(value):
    return (
        str(value)
        .replace('&', '&amp;')
        .replace('<', '&lt;')
        .replace('>', '&gt;')
        .replace('"', '&quot;')
        .replace("'", '&#39;')
    )


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            reading_date TEXT NOT NULL,
            confirmed INTEGER NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/readings':
            self.send_error(404, 'Not found')
            return

        length = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(length)
        try:
            payload = json.loads(body.decode('utf-8'))
            name = payload['name'].strip()
            reading_date = payload['date'].strip()
            confirmed = 1 if payload.get('confirmed') else 0
        except Exception:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Invalid payload'}).encode('utf-8'))
            return

        if not name or not reading_date:
            self.send_response(400)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.end_headers()
            self.wfile.write(json.dumps({'error': 'Missing fields'}).encode('utf-8'))
            return

        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO readings (name, reading_date, confirmed, created_at) VALUES (?, ?, ?, datetime('now'))",
            (name, reading_date, confirmed),
        )
        conn.commit()
        inserted_id = cur.lastrowid
        conn.close()

        self.send_response(201)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps({'id': inserted_id, 'status': 'saved'}).encode('utf-8'))

    def do_GET(self):
        if self.path == '/api/readings':
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            rows = conn.execute('SELECT id, name, reading_date, confirmed, created_at FROM readings ORDER BY id DESC').fetchall()
            conn.close()

            cards = []
            for row in rows:
                cards.append(f"""
                <article class=\"record\">
                  <div class=\"record-head\">
                    <strong>{html_escape(row['name'])}</strong>
                    <span>ID {row['id']}</span>
                  </div>
                  <div class=\"record-grid\">
                    <div><label>Data da leitura</label><p>{html_escape(row['reading_date'])}</p></div>
                    <div><label>Confirmação</label><p>{'Sim' if row['confirmed'] else 'Não'}</p></div>
                    <div><label>Registrado em</label><p>{html_escape(row['created_at'])}</p></div>
                  </div>
                </article>
                """)

            page = f"""<!doctype html>
<html lang=\"pt-BR\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Registros de leitura</title>
  <style>
    :root {{ --blue:#0f4c81; --bg:#f3f6fb; --card:#fff; --text:#1f2937; --muted:#6b7280; --line:#d1d5db; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Arial, Helvetica, sans-serif; color:var(--text); background:linear-gradient(180deg, #fff 0%, var(--bg) 100%); }}
    .wrap {{ max-width:1100px; margin:0 auto; padding:40px 20px; }}
    .hero {{ background:linear-gradient(135deg, #0f4c81 0%, #0b3760 100%); color:#fff; border-radius:24px; padding:28px; box-shadow:0 14px 40px rgba(15,76,129,.12); }}
    .hero h1 {{ margin:0 0 8px; font-size:clamp(28px, 4vw, 44px); }}
    .hero p {{ margin:0; color:rgba(255,255,255,.85); }}
    .toolbar {{ display:flex; justify-content:space-between; gap:12px; align-items:center; margin:20px 0 24px; flex-wrap:wrap; }}
    .pill {{ background:#fff; border:1px solid var(--line); color:var(--muted); border-radius:999px; padding:10px 14px; }}
    .records {{ display:grid; gap:16px; }}
    .record {{ background:var(--card); border:1px solid var(--line); border-radius:20px; padding:20px; box-shadow:0 10px 28px rgba(15,76,129,.08); }}
    .record-head {{ display:flex; justify-content:space-between; gap:12px; align-items:center; margin-bottom:16px; }}
    .record-head strong {{ font-size:20px; color:var(--blue); }}
    .record-head span {{ color:var(--muted); }}
    .record-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(200px, 1fr)); gap:14px; }}
    label {{ display:block; font-size:12px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin-bottom:6px; }}
    p {{ margin:0; font-size:16px; }}
    .empty {{ background:#fff; border:1px dashed var(--line); border-radius:20px; padding:30px; text-align:center; color:var(--muted); }}
  </style>
</head>
<body>
  <main class=\"wrap\">
    <section class=\"hero\">
      <h1>Registros de leitura</h1>
      <p>Visualização dos nomes, datas e confirmações salvas no banco local.</p>
    </section>
    <div class=\"toolbar\">
      <div class=\"pill\">Total de registros: {len(rows)}</div>
      <div class=\"pill\">Banco local SQLite ativo</div>
    </div>
    <section class=\"records\">{''.join(cards) if cards else '<div class=\"empty\">Nenhum registro encontrado.</div>'}</section>
  </main>
</body>
</html>"""

            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(page.encode('utf-8'))
            return
        return super().do_GET()


if __name__ == '__main__':
    init_db()
    server = ThreadingHTTPServer(('127.0.0.1', 8000), Handler)
    print('Serving on http://127.0.0.1:8000')
    server.serve_forever()
