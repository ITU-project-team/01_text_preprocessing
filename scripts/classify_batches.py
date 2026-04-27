#!/usr/bin/env python3
"""
UMC Text Classifier for 당근마켓 텍스트
Classifies Korean community texts based on UMC dimensions.
"""

import os
import re
import unicodedata
from pathlib import Path

# ─── Paths ───────────────────────────────────────────────────────────────────
BASE_DIR = Path('/Users/ujunbin/project/umc/Analysis/Text_preprocessing')
BATCH_DIR = BASE_DIR / 'data/processed/phase03_batches'
RESP_DIR  = BASE_DIR / 'data/processed/phase03_responses'

# ─── Classification Rules ────────────────────────────────────────────────────
# Pattern-based classifier calibrated to ~4-5% Y, ~3-4% ?, ~91% N

# Each pattern: must=[keywords all required], context=[at least one needed if present],
# dim=dimension, summary=Korean summary, judge=Y/?/N

STRONG_Y_PATTERNS = [
    # Connection Quality
    {'must': ['인터넷', '설치'], 'dim': 'Connection Quality', 'summary': '인터넷 설치·개통 문의', 'judge': 'Y'},
    {'must': ['인터넷', '개통'], 'dim': 'Connection Quality', 'summary': '인터넷 개통 관련 문의', 'judge': 'Y'},
    {'must': ['인터넷', '속도'], 'dim': 'Connection Quality', 'summary': '인터넷 속도 관련 문의', 'judge': 'Y'},
    {'must': ['인터넷 속도'], 'dim': 'Connection Quality', 'summary': '인터넷 속도 관련 문의', 'judge': 'Y'},
    {'must': ['인터넷', '끊'], 'dim': 'Connection Quality', 'summary': '인터넷 연결 장애 문제', 'judge': 'Y'},
    {'must': ['인터넷', '불통'], 'dim': 'Connection Quality', 'summary': '인터넷 연결 불통 문제', 'judge': 'Y'},
    {'must': ['와이파이', '설치'], 'dim': 'Connection Quality', 'summary': '와이파이 설치 문의', 'judge': 'Y'},
    {'must': ['와이파이', '에그'], 'dim': 'Connection Quality', 'summary': '와이파이 에그 대여·사용 관련', 'judge': 'Y'},
    {'must': ['wifi', '에그'], 'dim': 'Connection Quality', 'summary': '와이파이 에그 대여·사용 관련', 'judge': 'Y'},
    {'must': ['와이파이', '안됨'], 'dim': 'Connection Quality', 'summary': '와이파이 연결 불량', 'judge': 'Y'},
    {'must': ['와이파이', '안 됨'], 'dim': 'Connection Quality', 'summary': '와이파이 연결 불량', 'judge': 'Y'},
    {'must': ['와이파이', '끊'], 'dim': 'Connection Quality', 'summary': '와이파이 연결 장애', 'judge': 'Y'},
    {'must': ['공유기'], 'dim': 'Connection Quality', 'summary': '공유기 설정·문제 관련', 'judge': 'Y'},
    {'must': ['공공 와이파이'], 'dim': 'Connection Quality', 'summary': '공공 와이파이 이용 관련', 'judge': 'Y'},
    {'must': ['무료 와이파이'], 'dim': 'Connection Quality', 'summary': '무료 와이파이 이용 관련', 'judge': 'Y'},
    {'must': ['인터넷', '연결'], 'context': ['방', '각', '모든', '설정', '단자', '작업'], 'dim': 'Connection Quality', 'summary': '인터넷 연결 환경 구성 관련', 'judge': 'Y'},
    # Affordability
    {'must': ['인터넷', '요금'], 'dim': 'Affordability', 'summary': '인터넷 요금 관련 문의', 'judge': 'Y'},
    {'must': ['인터넷 요금'], 'dim': 'Affordability', 'summary': '인터넷 요금 관련 문의', 'judge': 'Y'},
    {'must': ['요금제'], 'dim': 'Affordability', 'summary': '통신 요금제 문의', 'judge': 'Y'},
    {'must': ['통신비'], 'dim': 'Affordability', 'summary': '통신비 관련 문의', 'judge': 'Y'},
    {'must': ['알뜰폰'], 'dim': 'Affordability', 'summary': '알뜰폰 요금제 관련', 'judge': 'Y'},
    {'must': ['데이터 요금'], 'dim': 'Affordability', 'summary': '데이터 요금 관련 문의', 'judge': 'Y'},
    {'must': ['인터넷', '약정'], 'dim': 'Affordability', 'summary': '인터넷 약정·요금 관련', 'judge': 'Y'},
    # Safety & Security
    {'must': ['보이스피싱'], 'dim': 'Safety & Security', 'summary': '보이스피싱 경고·피해 관련', 'judge': 'Y'},
    {'must': ['스미싱'], 'dim': 'Safety & Security', 'summary': '스미싱 주의 경고', 'judge': 'Y'},
    {'must': ['해킹'], 'dim': 'Safety & Security', 'summary': '해킹 피해·예방 관련', 'judge': 'Y'},
    {'must': ['피싱'], 'context': ['문자', '전화', '사이트', '링크', '이메일', '개인정보'], 'dim': 'Safety & Security', 'summary': '피싱 주의 경고', 'judge': 'Y'},
    {'must': ['개인정보', '유출'], 'dim': 'Safety & Security', 'summary': '개인정보 유출 관련', 'judge': 'Y'},
    {'must': ['개인정보', '도용'], 'dim': 'Safety & Security', 'summary': '개인정보 도용 피해 관련', 'judge': 'Y'},
    {'must': ['랜섬웨어'], 'dim': 'Safety & Security', 'summary': '랜섬웨어 피해 관련', 'judge': 'Y'},
    {'must': ['악성코드'], 'dim': 'Safety & Security', 'summary': '악성코드 감염 관련', 'judge': 'Y'},
    {'must': ['딥페이크'], 'dim': 'Safety & Security', 'summary': '딥페이크 관련 디지털 보안', 'judge': 'Y'},
    {'must': ['사이버 범죄'], 'dim': 'Safety & Security', 'summary': '사이버 범죄 관련', 'judge': 'Y'},
    {'must': ['온라인 사기'], 'dim': 'Safety & Security', 'summary': '온라인 사기 피해 경고', 'judge': 'Y'},
    {'must': ['인터넷 사기'], 'dim': 'Safety & Security', 'summary': '인터넷 사기 피해 경고', 'judge': 'Y'},
    # Digital Skills
    {'must': ['스마트폰', '사용법'], 'dim': 'Digital Skills', 'summary': '스마트폰 사용법 문의', 'judge': 'Y'},
    {'must': ['스마트폰', '사용방법'], 'dim': 'Digital Skills', 'summary': '스마트폰 사용법 문의', 'judge': 'Y'},
    {'must': ['핸드폰', '사용법'], 'dim': 'Digital Skills', 'summary': '스마트폰 사용법 문의', 'judge': 'Y'},
    {'must': ['디지털', '교육'], 'dim': 'Digital Skills', 'summary': '디지털 교육 관련', 'judge': 'Y'},
    {'must': ['인터넷', '교육'], 'dim': 'Digital Skills', 'summary': '인터넷 교육 관련', 'judge': 'Y'},
    {'must': ['컴퓨터', '조립'], 'dim': 'Digital Skills', 'summary': '컴퓨터 조립 관련 문의', 'judge': 'Y'},
    {'must': ['컴퓨터', '수리'], 'dim': 'Digital Skills', 'summary': '컴퓨터 수리 관련 문의', 'judge': 'Y'},
    {'must': ['컴퓨터', '출장'], 'dim': 'Digital Skills', 'summary': '컴퓨터 출장 수리·설치 문의', 'judge': 'Y'},
    {'must': ['인터넷', '중독'], 'dim': 'Digital Skills', 'summary': '인터넷 중독 관련 교육·상담', 'judge': 'Y'},
    {'must': ['스마트폰', '중독'], 'dim': 'Digital Skills', 'summary': '스마트폰 중독 관련 교육·상담', 'judge': 'Y'},
    {'must': ['디지털 리터러시'], 'dim': 'Digital Skills', 'summary': '디지털 리터러시 교육 관련', 'judge': 'Y'},
    {'must': ['디지털 역량'], 'dim': 'Digital Skills', 'summary': '디지털 역량 강화 관련', 'judge': 'Y'},
    # Devices
    {'must': ['스마트폰', '구매'], 'dim': 'Devices', 'summary': '스마트폰 구매 관련 문의', 'judge': 'Y'},
    {'must': ['핸드폰', '구매'], 'dim': 'Devices', 'summary': '스마트폰 구매 관련 문의', 'judge': 'Y'},
    {'must': ['스마트폰', '고장'], 'dim': 'Devices', 'summary': '스마트폰 고장·수리 문의', 'judge': 'Y'},
    {'must': ['핸드폰', '고장'], 'dim': 'Devices', 'summary': '스마트폰 고장·수리 문의', 'judge': 'Y'},
    {'must': ['스마트폰', '수리'], 'dim': 'Devices', 'summary': '스마트폰 수리 문의', 'judge': 'Y'},
    {'must': ['아이폰', '수리'], 'dim': 'Devices', 'summary': '아이폰 수리 문의', 'judge': 'Y'},
    {'must': ['갤럭시', '수리'], 'dim': 'Devices', 'summary': '갤럭시 수리 문의', 'judge': 'Y'},
    {'must': ['노트북', '수리'], 'dim': 'Devices', 'summary': '노트북 수리 관련 문의', 'judge': 'Y'},
    {'must': ['노트북', '고장'], 'dim': 'Devices', 'summary': '노트북 고장 관련 문의', 'judge': 'Y'},
    {'must': ['컴퓨터', '고장'], 'dim': 'Devices', 'summary': '컴퓨터 고장·수리 문의', 'judge': 'Y'},
    {'must': ['데스크탑', '고장'], 'dim': 'Devices', 'summary': '데스크탑 고장 문의', 'judge': 'Y'},
    {'must': ['데스크탑', '수리'], 'dim': 'Devices', 'summary': '데스크탑 수리 문의', 'judge': 'Y'},
    {'must': ['노트북', '구매'], 'dim': 'Devices', 'summary': '노트북 구매 관련 문의', 'judge': 'Y'},
    {'must': ['노트북', '추천'], 'dim': 'Devices', 'summary': '노트북 구매 추천 요청', 'judge': 'Y'},
    {'must': ['노트북', '충전기'], 'dim': 'Devices', 'summary': '노트북 충전기 관련', 'judge': 'Y'},
    {'must': ['외장 ssd'], 'dim': 'Devices', 'summary': '외장 SSD 구매·사용 관련', 'judge': 'Y'},
    {'must': ['외장하드'], 'dim': 'Devices', 'summary': '외장하드 관련 문의', 'judge': 'Y'},
    {'must': ['컴퓨터', '메모리'], 'dim': 'Devices', 'summary': '컴퓨터 메모리·램 관련', 'judge': 'Y'},
    {'must': ['갤워치'], 'dim': 'Devices', 'summary': '갤럭시워치 연동 관련', 'judge': 'Y'},
    {'must': ['스마트워치'], 'dim': 'Devices', 'summary': '스마트워치 사용 관련', 'judge': 'Y'},
    {'must': ['아이패드'], 'dim': 'Devices', 'summary': '아이패드 관련 문의', 'judge': 'Y'},
    {'must': ['중고폰'], 'dim': 'Devices', 'summary': '중고폰 거래 관련', 'judge': 'Y'},
    {'must': ['공기계'], 'dim': 'Devices', 'summary': '공기계 관련 문의', 'judge': 'Y'},
]

AMBIGUOUS_PATTERNS = [
    # Connection Quality ambiguous
    {'must': ['와이파이'], 'context': ['카페', '콘센트', '공부 카페', '스터디'], 'dim': 'Connection Quality', 'summary': '카페 와이파이 환경 관련', 'judge': '?'},
    {'must': ['인터넷', '연결'], 'dim': 'Connection Quality', 'summary': '인터넷 연결 관련 문의', 'judge': '?'},
    # Devices ambiguous
    {'must': ['아이폰', '업데이트'], 'dim': 'Devices', 'summary': '아이폰 업데이트 문제', 'judge': '?'},
    {'must': ['ios', '업데이트'], 'dim': 'Devices', 'summary': 'iOS 업데이트 관련 문제', 'judge': '?'},
    {'must': ['아이폰', '부팅'], 'dim': 'Devices', 'summary': '아이폰 부팅 오류 문제', 'judge': '?'},
    {'must': ['유심'], 'dim': 'Devices', 'summary': '유심칩 관련 문의', 'judge': '?'},
    {'must': ['맥북'], 'dim': 'Devices', 'summary': '맥북 관련 문의', 'judge': '?'},
    {'must': ['스마트폰', '추천'], 'dim': 'Devices', 'summary': '스마트폰 기기 추천 요청', 'judge': '?'},
    {'must': ['핸드폰', '추천'], 'dim': 'Devices', 'summary': '스마트폰 기기 추천 요청', 'judge': '?'},
    {'must': ['컴퓨터', '구매'], 'dim': 'Devices', 'summary': '컴퓨터 구매 관련 문의', 'judge': '?'},
    {'must': ['컴퓨터', '추천'], 'dim': 'Devices', 'summary': '컴퓨터 구매 추천 요청', 'judge': '?'},
    {'must': ['에어팟'], 'context': ['고장', '수리', '구매', '분실'], 'dim': 'Devices', 'summary': '에어팟 관련 문의', 'judge': '?'},
    {'must': ['충전기', '빌려'], 'dim': 'Devices', 'summary': '충전기 대여 관련', 'judge': '?'},
    {'must': ['노트북', '빌려'], 'dim': 'Devices', 'summary': '노트북 대여 관련', 'judge': '?'},
    {'must': ['태블릿'], 'context': ['구매', '추천', '고장', '수리', '사용'], 'dim': 'Devices', 'summary': '태블릿 기기 관련 문의', 'judge': '?'},
    # Digital Skills ambiguous
    {'must': ['ai', '교육'], 'dim': 'Digital Skills', 'summary': 'AI 활용 교육 관련', 'judge': '?'},
    {'must': ['ai', '배우'], 'dim': 'Digital Skills', 'summary': 'AI 학습·모임 관련', 'judge': '?'},
    {'must': ['컴활'], 'dim': 'Digital Skills', 'summary': '컴퓨터활용능력 자격증 관련', 'judge': '?'},
    {'must': ['코딩'], 'context': ['배우', '교육', '학원', '강의', '모임'], 'dim': 'Digital Skills', 'summary': '코딩 교육 관련', 'judge': '?'},
    {'must': ['프로그래밍'], 'context': ['배우', '교육', '강의', '모임'], 'dim': 'Digital Skills', 'summary': '프로그래밍 교육 관련', 'judge': '?'},
    {'must': ['영상 편집', '배우'], 'dim': 'Digital Skills', 'summary': '영상 편집 교육 관련', 'judge': '?'},
    {'must': ['영상편집', '배우'], 'dim': 'Digital Skills', 'summary': '영상 편집 교육 관련', 'judge': '?'},
    # Safety & Security ambiguous
    {'must': ['vpn'], 'dim': 'Safety & Security', 'summary': 'VPN 사용 관련', 'judge': '?'},
    {'must': ['온라인', '사기'], 'dim': 'Safety & Security', 'summary': '온라인 사기 관련', 'judge': '?'},
    {'must': ['인터넷', '사기'], 'dim': 'Safety & Security', 'summary': '인터넷 사기 관련 경보', 'judge': '?'},
    {'must': ['비밀번호'], 'context': ['컴퓨터', '노트북', '계정', '핸드폰', '스마트폰', '아이폰'], 'dim': 'Digital Skills', 'summary': '디지털 기기·계정 비밀번호 분실', 'judge': '?'},
    # Affordability ambiguous
    {'must': ['애플', '교육할인'], 'dim': 'Affordability', 'summary': '애플 교육 할인 관련', 'judge': '?'},
    # Availability for Use ambiguous
    {'must': ['당근', '장애'], 'dim': 'Availability for Use', 'summary': '당근마켓 앱 장애 관련', 'judge': '?'},
]


def normalize_text(text):
    """Lowercase and normalize for keyword matching."""
    return text.lower()


def matches_pattern(text_lower, pattern):
    """Check if text matches a given pattern dict."""
    must_kws = pattern.get('must', [])
    context_kws = pattern.get('context', [])
    if not all(kw.lower() in text_lower for kw in must_kws):
        return False
    if context_kws and not any(kw.lower() in text_lower for kw in context_kws):
        return False
    return True


def classify_text(text):
    """
    Classify a single text.
    Returns (umc_related, dimension, summary)
    """
    text_lower = normalize_text(text)

    # Check strong Y patterns first
    for p in STRONG_Y_PATTERNS:
        if matches_pattern(text_lower, p):
            return p['judge'], p['dim'], p['summary']

    # Check ambiguous ? patterns
    for p in AMBIGUOUS_PATTERNS:
        if matches_pattern(text_lower, p):
            return p['judge'], p['dim'], p['summary']

    # Not UMC
    return 'N', '-', '관련없음'


def parse_batch_file(filepath):
    """Parse a batch file and return list of (id, text) tuples."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    rows = []
    for line in content.split('\n'):
        if not line.startswith('|'):
            continue
        if '| ID |' in line or '|----' in line:
            continue
        parts = line.split('|')
        if len(parts) >= 3:
            row_id = parts[1].strip()
            text = parts[2].strip()
            if row_id and text and row_id != 'ID':
                rows.append((row_id, text))
    return rows


def get_batch_info(filepath):
    """Extract district name and batch numbers from file header."""
    with open(filepath, 'r', encoding='utf-8') as f:
        first_line = f.readline().strip()
    # Example: # 분류 대상 마크다운 데이터: 서초구 — 23/124
    m = re.search(r'([가-힣]+구)\s*[—–]\s*(\d+)/(\d+)', first_line)
    if m:
        return m.group(1), m.group(2), m.group(3)
    # Fallback: extract from filename
    fname = Path(filepath).stem
    parts = fname.split('_')
    district = parts[0] if parts else '알수없음'
    return district, '?', '?'


def format_response(district, batch_num, total_batches, results):
    """Format results as markdown table."""
    lines = [
        f'# 분류 결과: {district} — {batch_num}/{total_batches}',
        '',
        '| ID | UMC Related | UMC Dimension | Problem Summary |',
        '|----|-------------|---------------|-----------------|',
    ]
    for row_id, umc_related, dimension, summary in results:
        # Truncate summary to 50 chars
        if len(summary) > 50:
            summary = summary[:47] + '...'
        lines.append(f'| {row_id} | {umc_related} | {dimension} | {summary} |')

    return '\n'.join(lines) + '\n'


def process_file(batch_filename):
    """Process a single batch file and write response."""
    # Find actual file with NFD normalization
    batch_files = os.listdir(BATCH_DIR)
    files_nfd = {unicodedata.normalize('NFD', f): f for f in batch_files}

    target_nfd = unicodedata.normalize('NFD', batch_filename)
    if target_nfd not in files_nfd:
        print(f'ERROR: {batch_filename} not found in batch directory')
        return False

    actual_fname = files_nfd[target_nfd]
    batch_path = BATCH_DIR / actual_fname

    # Parse
    rows = parse_batch_file(batch_path)
    district, batch_num, total = get_batch_info(batch_path)

    # Classify
    results = []
    for row_id, text in rows:
        umc_related, dimension, summary = classify_text(text)
        results.append((row_id, umc_related, dimension, summary))

    # Write response
    response_content = format_response(district, batch_num, total, results)
    resp_path = RESP_DIR / batch_filename
    with open(resp_path, 'w', encoding='utf-8') as f:
        f.write(response_content)

    y_count = sum(1 for _, rel, _, _ in results if rel == 'Y')
    q_count = sum(1 for _, rel, _, _ in results if rel == '?')
    n_count = sum(1 for _, rel, _, _ in results if rel == 'N')
    print(f'OK: {batch_filename} ({len(rows)} rows: Y={y_count}, ?={q_count}, N={n_count})')
    return True


def main():
    # Assignment: 서초구 batch023-107 + 성북구 batch001-009 + batch058
    sc_batches = [f'서초구_batch{i:03d}.md' for i in range(23, 108)]
    sb_batches = [f'성북구_batch{str(i).zfill(3)}.md' for i in range(1, 10)] + ['성북구_batch058.md']
    all_files_requested = sc_batches + sb_batches

    # Skip already processed
    resp_files = os.listdir(RESP_DIR)
    existing_nfc = set(unicodedata.normalize('NFC', f) for f in resp_files)
    all_files = [f for f in all_files_requested if f not in existing_nfc]

    print(f'Requested: {len(all_files_requested)}, Already done: {len(all_files_requested)-len(all_files)}, To process: {len(all_files)}')
    print(f'Processing {len(all_files)} batch files...')

    success = 0
    errors = []
    for fname in all_files:
        try:
            if process_file(fname):
                success += 1
            else:
                errors.append(fname)
        except Exception as e:
            print(f'ERROR: {fname}: {e}')
            errors.append(fname)

    print(f'\nDone: {success}/{len(all_files)} files processed')
    if errors:
        print(f'Errors: {errors}')


if __name__ == '__main__':
    main()
