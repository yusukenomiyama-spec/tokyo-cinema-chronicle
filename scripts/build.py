"""
scripts/build.py
Google スプレッドシート（または data/movies.csv）を読み込み、
index.html のエントリ配列を更新する

Usage:
  python3 scripts/build.py          # Google Sheets から取得
  python3 scripts/build.py --local  # data/movies.csv をそのまま使用（旧形式）

Google Sheets の列（フラット形式・1映画1行）:
  年代 | 並び順 | ジャンル | アイコン | 映画タイトル | 映画あらすじ | 東京での出来事 | カルチャー
"""

import csv
import json
import os
import sys
import urllib.request
import urllib.error
from collections import defaultdict

USE_LOCAL = '--local' in sys.argv

ROOT      = os.path.join(os.path.dirname(__file__), '..')
CSV_PATH  = os.path.join(ROOT, 'data', 'movies.csv')
HTML_PATH = os.path.join(ROOT, 'index.html')

START_MARKER = '// ═══ MOVIE DATA START ═══'
END_MARKER   = '// ═══ MOVIE DATA END ═══'

SHEET_ID   = '1HyKuMj19uvze-1bIXefj47ENHM8aGmW1Ia_Z9_1zWPY'
SHEET_NAME = ''

def get_gsheet_csv_url():
    base = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv'
    if SHEET_NAME:
        import urllib.parse
        return base + f'&sheet={urllib.parse.quote(SHEET_NAME)}'
    return base

# ── データソースから CSV テキストを取得 ───────────────────────────
def load_csv_text():
    if USE_LOCAL:
        print('📂 ローカルモード: data/movies.csv を使用します')
        with open(CSV_PATH, encoding='utf-8', newline='') as f:
            return f.read()

    url = get_gsheet_csv_url()
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as res:
            text = res.read().decode('utf-8')
        print('📥 Google スプレッドシートから取得')
        return text
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print('⚠️  スプレッドシートが非公開です。「リンクを知っている全員が閲覧可」に設定してください。')
        else:
            print(f'⚠️  Google スプレッドシートの取得に失敗 (HTTP {e.code})')
    except Exception as e:
        print(f'⚠️  接続できません: {e}')

    print('📂 ローカルの data/movies.csv を使用します')
    with open(CSV_PATH, encoding='utf-8', newline='') as f:
        return f.read()

# ── フォーマット判定 ──────────────────────────────────────────────
def is_flat_format(headers):
    """Google Sheets フラット形式（日本語ヘッダー）かどうか判定"""
    return '映画タイトル' in headers

# ── フラット形式（1映画1行）→ エントリリスト ──────────────────────
def parse_flat_rows(rows):
    """
    Google Sheets フラット形式を読み込み、同じ年代の映画をグループ化して
    内部エントリ形式に変換する
    """
    # (年代, 並び順) でグループ化（入力順を保持）
    groups = defaultdict(list)
    order  = []
    for row in rows:
        title = row.get('映画タイトル', '').strip()
        if not title:
            continue
        year_d = row.get('年代', '').strip()
        year_s = row.get('並び順', '0').strip()
        key = (year_d, year_s)
        if key not in groups:
            order.append(key)
        groups[key].append(row)

    entries = []
    auto_id = 1
    for key in order:
        group = groups[key]
        year_d, year_s = key

        try:
            year_sort = float(year_s)
        except ValueError:
            year_sort = 0.0

        first   = group[0]
        movies  = [r['映画タイトル'].strip() for r in group]
        genres  = [r.get('ジャンル', '').strip() for r in group]
        evts    = [r.get('映画あらすじ', '').strip() for r in group]
        icon    = first.get('アイコン', '').strip()

        entry = {
            'id':          auto_id,
            'yearDisplay': year_d,
            'yearSort':    year_sort,
            'genre':       genres[0] if genres else '',
            'icon':        icon,
            'events':      evts[0] if evts else '',
            'movieList':   movies,
        }
        auto_id += 1

        if len(movies) > 1:
            entry['movieGenres'] = genres
            if all(evts):
                entry['movieEvents'] = evts

        real_events  = first.get('東京での出来事', '').strip()
        real_culture = first.get('カルチャー', '').strip()
        if real_events:
            entry['realEvents'] = real_events
        if real_culture:
            entry['realCulture'] = real_culture

        entries.append(entry)

    return entries

# ── 旧形式（パイプ区切り）→ エントリリスト ─────────────────────────
def parse_legacy_rows(rows):
    entries = []
    for row in rows:
        movie_list_raw = str(row.get('movieList', '')).strip()
        if not movie_list_raw:
            continue

        movie_list   = [m.strip() for m in movie_list_raw.split('|') if m.strip()]
        movie_genres = [g.strip() for g in str(row.get('movieGenres', '')).split('|') if g.strip()]
        movie_events = [e.strip() for e in str(row.get('movieEvents', '')).split('|') if e.strip()]

        try:
            year_sort = float(str(row.get('yearSort', '0')).strip())
        except ValueError:
            year_sort = 0.0

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

        real_events  = str(row.get('realEvents',  '')).strip()
        real_culture = str(row.get('realCulture', '')).strip()
        if real_events:
            entry['realEvents'] = real_events
        if real_culture:
            entry['realCulture'] = real_culture

        entries.append(entry)

    entries.sort(key=lambda e: e['id'])
    return entries

# ── CSV パース ────────────────────────────────────────────────────
def parse_csv(text):
    rows = list(csv.DictReader(text.splitlines()))
    if not rows:
        return []
    headers = list(rows[0].keys())
    if is_flat_format(headers):
        print('📋 フラット形式（Google Sheets）として読み込みます')
        return parse_flat_rows(rows)
    else:
        print('📋 旧形式（movies.csv）として読み込みます')
        return parse_legacy_rows(rows)

entries = parse_csv(load_csv_text())
entries.sort(key=lambda e: (e['yearSort'], e['id']))

# ── entries を movies.csv にバックアップ保存 ──────────────────────
with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['id','yearDisplay','yearSort','genre','icon','events',
                     'movieList','movieGenres','movieEvents','realEvents','realCulture'])
    for e in entries:
        writer.writerow([
            e['id'], e['yearDisplay'], e['yearSort'],
            e['genre'], e['icon'], e['events'],
            '|'.join(e['movieList']),
            '|'.join(e.get('movieGenres', [])),
            '|'.join(e.get('movieEvents', [])),
            e.get('realEvents', ''),
            e.get('realCulture', ''),
        ])

# ── Python dict → JS オブジェクト文字列 ──────────────────────────
def esc(s):
    return s.replace('\\', '\\\\').replace("'", "\\'")

def entry_to_js(e):
    movie_list_js   = json.dumps(e['movieList'], ensure_ascii=False)
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
    real_culture_js = (
        f", realCulture:'{esc(e['realCulture'])}'"
        if 'realCulture' in e else ''
    )
    year_sort = int(e['yearSort']) if e['yearSort'] == int(e['yearSort']) else e['yearSort']
    return (
        f"  {{ id:{e['id']}, yearDisplay:'{esc(e['yearDisplay'])}', "
        f"yearSort:{year_sort}, genre:'{esc(e['genre'])}', icon:'{esc(e['icon'])}', "
        f"events:'{esc(e['events'])}', movieList:{movie_list_js}"
        f"{movie_genres_js}{movie_events_js}{real_events_js}{real_culture_js} }}"
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
updated   = html[:start_idx] + new_block + html[end_idx:]

with open(HTML_PATH, 'w', encoding='utf-8') as f:
    f.write(updated)

print(f'✅ ビルド完了: {len(entries)} 件のエントリを index.html に反映しました')
