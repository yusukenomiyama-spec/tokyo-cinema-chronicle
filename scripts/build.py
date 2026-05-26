"""
scripts/build.py
data/movies.csv を読み込み、index.html のエントリ配列を更新する
Usage: python3 scripts/build.py

CSV 列:
  id, yearDisplay, yearSort, genre, icon, events, movieList, movieGenres
  - movieList / movieGenres は "|" 区切りで複数作品を記載
  - movieGenres は movieList が1作品のときは空欄でよい
"""

import csv
import json
import os

ROOT      = os.path.join(os.path.dirname(__file__), '..')
CSV_PATH  = os.path.join(ROOT, 'data', 'movies.csv')
HTML_PATH = os.path.join(ROOT, 'index.html')

START_MARKER = '// ═══ MOVIE DATA START ═══'
END_MARKER   = '// ═══ MOVIE DATA END ═══'

# ── CSV を読み込む ────────────────────────────────────────────────
entries = []
with open(CSV_PATH, encoding='utf-8', newline='') as f:
    reader = csv.DictReader(f)
    for row in reader:
        movie_list   = [m.strip() for m in row['movieList'].split('|')   if m.strip()]
        movie_genres = [g.strip() for g in row['movieGenres'].split('|') if g.strip()]

        entry = {
            'id':          int(row['id']),
            'yearDisplay': row['yearDisplay'],
            'yearSort':    float(row['yearSort']),
            'genre':       row['genre'],
            'icon':        row['icon'],
            'events':      row['events'],
            'movieList':   movie_list,
        }
        # movieGenres は複数作品のときのみ付与
        if len(movie_list) > 1 and movie_genres:
            entry['movieGenres'] = movie_genres

        entries.append(entry)

# ── Python dict → JS オブジェクト文字列 ──────────────────────────
def esc(s):
    """JS シングルクォート文字列用エスケープ"""
    return s.replace('\\', '\\\\').replace("'", "\\'")

def entry_to_js(e):
    movie_list_js   = json.dumps(e['movieList'],   ensure_ascii=False)
    movie_genres_js = (
        f", movieGenres:{json.dumps(e['movieGenres'], ensure_ascii=False)}"
        if 'movieGenres' in e else ''
    )
    year_sort = int(e['yearSort']) if e['yearSort'] == int(e['yearSort']) else e['yearSort']
    return (
        f"  {{ id:{e['id']}, yearDisplay:'{esc(e['yearDisplay'])}', "
        f"yearSort:{year_sort}, genre:'{esc(e['genre'])}', icon:'{esc(e['icon'])}', "
        f"events:'{esc(e['events'])}', movieList:{movie_list_js}{movie_genres_js} }}"
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

if start_idx < 0 or end_idx < 0:
    print('❌ マーカーが見つかりません。index.html を確認してください。')
    exit(1)

updated = html[:start_idx] + new_block + html[end_idx:]

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(updated)

print(f'✅ ビルド完了: {len(entries)} 件のエントリを index.html に反映しました')
