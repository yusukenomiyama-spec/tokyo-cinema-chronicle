"""
scripts/build.py
Google スプレッドシート（または data/movies.csv）を読み込み、
index.html のエントリ配列を更新する

Usage: python3 scripts/build.py

データソースの優先順位:
  1. Google スプレッドシート（公開設定の場合）
  2. data/movies.csv（フォールバック）

CSV 列:
  id, yearDisplay, yearSort, genre, icon, events, movieList, movieGenres
  - movieList / movieGenres は "|" 区切りで複数作品を記載
  - movieGenres は movieList が1作品のときは空欄でよい
"""

import csv
import json
import os
import sys
import urllib.request
import urllib.error

# --local フラグで Google Sheets をスキップしてローカル CSV を使用
USE_LOCAL = '--local' in sys.argv

ROOT      = os.path.join(os.path.dirname(__file__), '..')
CSV_PATH  = os.path.join(ROOT, 'data', 'movies.csv')
HTML_PATH = os.path.join(ROOT, 'index.html')

START_MARKER = '// ═══ MOVIE DATA START ═══'
END_MARKER   = '// ═══ MOVIE DATA END ═══'

# ── Google スプレッドシートの設定 ─────────────────────────────────
SHEET_ID    = '1HyKuMj19uvze-1bIXefj47ENHM8aGmW1Ia_Z9_1zWPY'
SHEET_NAME  = ''   # シート名（空欄なら最初のシートを使用）

def get_gsheet_csv_url():
    base = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'
    if SHEET_NAME:
        return base + f'&sheet={urllib.parse.quote(SHEET_NAME)}'
    return base

# ── データソースから CSV テキストを取得 ───────────────────────────
def load_csv_text():
    # --local フラグがある場合はローカル CSV を直接使用
    if USE_LOCAL:
        print('📂 ローカルモード: data/movies.csv を使用します')
        with open(CSV_PATH, encoding='utf-8', newline='') as f:
            return f.read()

    # 1. Google スプレッドシートを試みる
    url = get_gsheet_csv_url()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as res:
            text = res.read().decode('utf-8')
        print(f'📥 Google スプレッドシートから取得')
        return text
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print('⚠️  Google スプレッドシートは非公開です。')
            print('   → スプレッドシートを「リンクを知っている全員が閲覧可」に設定してください。')
        else:
            print(f'⚠️  Google スプレッドシートの取得に失敗しました (HTTP {e.code})')
    except Exception as e:
        print(f'⚠️  Google スプレッドシートに接続できません: {e}')

    # 2. ローカル CSV にフォールバック
    print(f'📂 ローカルの data/movies.csv を使用します')
    with open(CSV_PATH, encoding='utf-8', newline='') as f:
        return f.read()

# ── CSV テキスト → エントリリスト ────────────────────────────────
def parse_csv(text):
    rows = list(csv.DictReader(text.splitlines()))
    return rows

raw_rows = parse_csv(load_csv_text())

# ── dict → Entry オブジェクト ─────────────────────────────────────
entries = []
for row in raw_rows:
    movie_list_raw = str(row.get('movieList', '')).strip()
    if not movie_list_raw:
        continue  # movieList が空の行はスキップ

    movie_list   = [m.strip() for m in movie_list_raw.split('|') if m.strip()]
    movie_genres = [g.strip() for g in str(row.get('movieGenres', '')).split('|') if g.strip()]
    movie_events = [e.strip() for e in str(row.get('movieEvents', '')).split('|') if e.strip()]

    year_sort_raw = str(row.get('yearSort', '0')).strip()
    try:
        year_sort = float(year_sort_raw)
    except ValueError:
        year_sort = 0.0

    real_events = str(row.get('realEvents', '')).strip()

    entry = {
        'id':          int(float(str(row['id']))),
        'yearDisplay': str(row.get('yearDisplay', '')).strip(),
        'yearSort':    year_sort,
        'genre':       str(row.get('genre', '')).strip(),
        'icon':        str(row.get('icon',  '')).strip(),
        'events':      str(row.get('events', '')).strip(),
        'movieList':   movie_list,
    }
    if len(movie_list) > 1 and movie_genres:
        entry['movieGenres'] = movie_genres
    if len(movie_events) == len(movie_list) and movie_events:
        entry['movieEvents'] = movie_events
    if real_events:
        entry['realEvents'] = real_events

    entries.append(entry)

entries.sort(key=lambda e: e['id'])

# ── CSV を同期保存（Google Sheets から取得した内容をローカルにバックアップ） ──
with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['id','yearDisplay','yearSort','genre','icon','events','movieList','movieGenres','movieEvents'])
    for e in entries:
        writer.writerow([
            e['id'], e['yearDisplay'], e['yearSort'],
            e['genre'], e['icon'], e['events'],
            '|'.join(e['movieList']),
            '|'.join(e.get('movieGenres', [])),
            '|'.join(e.get('movieEvents', [])),
        ])

# ── Python dict → JS オブジェクト文字列 ──────────────────────────
def esc(s):
    return s.replace('\\', '\\\\').replace("'", "\\'")

def entry_to_js(e):
    movie_list_js   = json.dumps(e['movieList'],   ensure_ascii=False)
    movie_genres_js = (
        f", movieGenres:{json.dumps(e['movieGenres'], ensure_ascii=False)}"
        if 'movieGenres' in e else ''
    )
    movie_events_js = (
        f", movieEvents:{json.dumps(e['movieEvents'], ensure_ascii=False)}"
        if 'movieEvents' in e else ''
    )
    real_events_js = (
        f", realEvents:'{esc(e['realEvents'])}'"
        if 'realEvents' in e else ''
    )
    year_sort = int(e['yearSort']) if e['yearSort'] == int(e['yearSort']) else e['yearSort']
    return (
        f"  {{ id:{e['id']}, yearDisplay:'{esc(e['yearDisplay'])}', "
        f"yearSort:{year_sort}, genre:'{esc(e['genre'])}', icon:'{esc(e['icon'])}', "
        f"events:'{esc(e['events'])}', movieList:{movie_list_js}{movie_genres_js}{movie_events_js}{real_events_js} }}"
    )

entries_js = ',\n'.join(entry_to_js(e) for e in entries)
new_block = (
    f"{START_MARKER}\n"
    f"let entries = [\n{entries_js},\n];\n"
    f"{END_MARKER}"
)

# ── index.html を更新 ─────────────────────────────────────────────
with open(HTML_PATH, encoding='utf-8') as f:
    html = f.read()

start_idx = html.index(START_MARKER)
end_idx   = html.index(END_MARKER) + len(END_MARKER)

updated = html[:start_idx] + new_block + html[end_idx:]

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(updated)

print(f'✅ ビルド完了: {len(entries)} 件のエントリを index.html に反映しました')
