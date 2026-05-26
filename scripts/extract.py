"""
scripts/extract.py
index.html の現在のエントリ配列を data/movies.csv に書き出す（初回のみ実行）
Usage: python3 scripts/extract.py
"""

import csv
import json
import os
import re

ROOT     = os.path.join(os.path.dirname(__file__), '..')
HTML_PATH = os.path.join(ROOT, 'index.html')
CSV_PATH  = os.path.join(ROOT, 'data', 'movies.csv')

# ── index.html からエントリブロックを抽出 ──────────────────────────
with open(HTML_PATH, encoding='utf-8') as f:
    html = f.read()

START_MARKER = '// ═══ MOVIE DATA START ═══'
END_MARKER   = '// ═══ MOVIE DATA END ═══'
start_idx = html.index(START_MARKER) + len(START_MARKER)
end_idx   = html.index(END_MARKER)
block = html[start_idx:end_idx].strip()  # "let entries = [ ... ];"

# "let entries = " と末尾の ";" を除去して JSON ライクな配列文字列を得る
array_str = re.sub(r'^let\s+entries\s*=\s*', '', block)
array_str = re.sub(r';\s*$', '', array_str.strip())

# ── JS → Python オブジェクトへ変換 ───────────────────────────────
# JS リテラルをそのまま eval するのは危険なので、正規表現でパース
# 各エントリを1行ずつマッチ

ENTRY_RE = re.compile(
    r'\{[^{}]*\}',
    re.DOTALL
)

def parse_js_string(s):
    """シングルクォートまたはダブルクォートで囲まれた文字列を返す"""
    s = s.strip()
    if (s.startswith("'") and s.endswith("'")) or \
       (s.startswith('"') and s.endswith('"')):
        inner = s[1:-1]
        # エスケープ処理
        inner = inner.replace("\\'", "'").replace('\\"', '"').replace('\\\\', '\\')
        return inner
    return s

def parse_js_array(s):
    """['a','b'] または [] 形式の JS 配列を Python リストに変換"""
    s = s.strip()
    if s == '[]':
        return []
    inner = s[1:-1]
    # カンマ区切りで分割（クォート内のカンマは無視）
    items = []
    current = ''
    in_q = False
    q_char = None
    for ch in inner:
        if not in_q and ch in ('"', "'"):
            in_q = True; q_char = ch; current += ch
        elif in_q and ch == q_char:
            in_q = False; current += ch
        elif not in_q and ch == ',':
            items.append(parse_js_string(current.strip()))
            current = ''
        else:
            current += ch
    if current.strip():
        items.append(parse_js_string(current.strip()))
    return items

def parse_entry(entry_str):
    """{ key:value, ... } 形式の JS オブジェクトを dict に変換"""
    obj = {}
    # 各フィールドを抽出
    # id, yearSort は数値
    for key in ('id', 'yearSort'):
        m = re.search(rf'\b{key}\s*:\s*([0-9.]+)', entry_str)
        if m:
            val = m.group(1)
            obj[key] = float(val) if '.' in val else int(val)

    # 文字列フィールド
    for key in ('yearDisplay', 'genre', 'icon', 'events'):
        # シングルクォートで囲まれた値（エスケープ考慮）
        m = re.search(rf"\b{key}\s*:\s*'((?:[^'\\]|\\.)*)'", entry_str)
        if m:
            obj[key] = m.group(1).replace("\\'", "'").replace('\\\\', '\\')
        else:
            obj[key] = ''

    # 配列フィールド
    for key in ('movieList', 'movieGenres'):
        m = re.search(rf'\b{key}\s*:\s*(\[.*?\])', entry_str, re.DOTALL)
        if m:
            obj[key] = parse_js_array(m.group(1))
        else:
            obj[key] = []

    return obj

# エントリ文字列の分割（ネストなし）
entries = []
depth = 0
current = ''
recording = False

for ch in array_str:
    if ch == '{':
        depth += 1
        recording = True
        current += ch
    elif ch == '}':
        depth -= 1
        current += ch
        if depth == 0 and recording:
            entries.append(parse_entry(current.strip()))
            current = ''
            recording = False
    elif recording:
        current += ch

print(f'パース完了: {len(entries)} 件')

# ── CSV 書き出し ──────────────────────────────────────────────────
HEADERS = ['id', 'yearDisplay', 'yearSort', 'genre', 'icon', 'events', 'movieList', 'movieGenres']

with open(CSV_PATH, 'w', encoding='utf-8', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(HEADERS)
    for e in entries:
        writer.writerow([
            e.get('id', ''),
            e.get('yearDisplay', ''),
            e.get('yearSort', ''),
            e.get('genre', ''),
            e.get('icon', ''),
            e.get('events', ''),
            '|'.join(e.get('movieList', [])),
            '|'.join(e.get('movieGenres', [])),
        ])

print(f'✅ data/movies.csv に書き出し完了')
