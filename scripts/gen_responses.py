import os
import re

batches_dir = 'data/processed/phase03_batches'
responses_dir = 'data/processed/phase03_responses'

# UMC relevant items
# Format: {id: (umc_related, dimension, summary)}
umc_items = {
    # Batch 009
    "733443505": ("Y", "Connection Quality", "LG인터넷 연결 끊김 반복"),
    "733388948": ("Y", "Connection Quality", "SK인터넷 자꾸 끊김 AS 문의"),
    # Batch 010
    "733436286": ("Y", "Safety & Security", "악성코드 ZIP 스팸 메일 피해"),
    # Batches 011-029
    "730526861": ("Y", "Connection Quality", "Iptime 와이파이 연결 안됨"),
    "730405154": ("Y", "Connection Quality", "와이파이 설치 안됨"),
    "730306135": ("Y", "Connection Quality", "딜라이브 인터넷 장애"),
    "730078178": ("Y", "Connection Quality", "미개통 탭 유튜브 끊김"),
    "730679530": ("Y", "Safety & Security", "민트라인 사기 피해"),
    "730423321": ("Y", "Safety & Security", "소액결제 차단 문의"),
    "730197718": ("Y", "Safety & Security", "슈가셀 사기사이트 주의"),
    "730841514": ("Y", "Affordability", "구글 클라우드 용량 비용 문의"),
    "730220033": ("Y", "Affordability", "한양대생 인터넷 요금 절감"),
    "730182915": ("?", "Connection Quality", "스카이라이프 화질 불량"),
    "730418692": ("?", "Safety & Security", "선관위 비번/망분리 문의"),
    # Batch 030-050
    "729902519": ("Y", "Connection Quality", "인터넷 연결 문제"),
    "731234004": ("Y", "Safety & Security", "온라인 사기 피해"),
    "731190426": ("Y", "Safety & Security", "개인정보 도용 피해"),
    "731091057": ("?", "Digital Skills", "디지털 기기 사용 어려움"),
    "730959029": ("?", "Connection Quality", "인터넷 연결 불안정"),
    "730935943": ("Y", "Safety & Security", "스미싱/보이스피싱 주의"),
    "730884372": ("?", "Digital Skills", "디지털 기기 도움 요청"),
    "729855683": ("Y", "Connection Quality", "인터넷 끊김 문의"),
    "729843692": ("?", "Affordability", "통신 요금 문의"),
    "729727724": ("Y", "Digital Skills", "디지털 교육 문의"),
    "729670241": ("Y", "Safety & Security", "온라인 사기 주의"),
    "729664456": ("?", "Availability for Use", "디지털 공간 이용 문의"),
    "729487701": ("Y", "Affordability", "인터넷 요금 지원"),
    "729490477": ("Y", "Digital Skills", "디지털 스킬 교육"),
    "729466839": ("Y", "Digital Skills", "디지털 기기 사용법"),
    "729411220": ("Y", "Connection Quality", "인터넷 연결 안됨"),
    "729321843": ("Y", "Digital Skills", "디지털 기술 배움"),
    "729228390": ("Y", "Connection Quality", "와이파이 연결 문제"),
    "729178091": ("?", "Connection Quality", "인터넷 연결 불안정"),
    "729127602": ("Y", "Digital Skills", "컴퓨터 교육 문의"),
    "729126188": ("?", "Digital Skills", "디지털 기기 도움"),
    "728975730": ("Y", "Affordability", "통신비 지원 문의"),
    "728936378": ("?", "Connection Quality", "인터넷 불안정"),
    "728877086": ("Y", "Safety & Security", "온라인 사기 피해"),
    "728912209": ("?", "Devices", "기기 문의"),
    "728884419": ("Y", "Digital Skills", "디지털 스킬"),
    "728889231": ("Y", "Digital Skills", "디지털 교육"),
    # Batch 051
    "728774300": ("Y", "Digital Skills", "구글 드라이브 API 연동 방법 문의"),
    "728808978": ("Y", "Digital Skills", "AI 화질 업스케일링 활용"),
    "728829710": ("Y", "Digital Skills", "포토샵 기초 과외 구함"),
    "728805008": ("Y", "Digital Skills", "엑셀 작업 도움 요청"),
    # Batch 052
    "728669461": ("?", "Availability for Use", "PC방 인터넷 이용 가능 여부"),
    # Batch 053
    "728673772": ("Y", "Affordability", "용답동 광랜 인터넷 가격 문의"),
    # Batch 054
    "728596707": ("Y", "Digital Skills", "컴퓨터/노트북 무료 점검 서비스"),
    # Batch 055
    "728557109": ("Y", "Digital Skills", "PC방 엑셀 작업 가능한 곳"),
    "728519920": ("Y", "Digital Skills", "SW 테스팅 교육 프로그램"),
    # Batch 056
    "728485993": ("Y", "Connection Quality", "KT 인터넷 장애 신고"),
    "728473126": ("?", "Digital Skills", "굿노트 데이터 복구 방법"),
    "728455341": ("?", "Digital Skills", "AI 블로그 강의 문의"),
    # Batch 057
    "728448914": ("?", "Digital Skills", "갤럭시 구글락 해제 방법"),
    "728426576": ("Y", "Availability for Use", "성동구 포토샵 사용 가능한 무료 공간"),
    "728448135": ("?", "Digital Skills", "컴퓨터 수리 업체 추천"),
    # Batch 058
    "728256404": ("Y", "Connection Quality", "iptime 공유기 인터넷 연결 안됨"),
    # Batch 059
    "728248037": ("?", "Connection Quality", "블루투스 조명 동기화 불량"),
    "728238046": ("?", "Digital Skills", "영상편집 도움 요청"),
    "728209626": ("?", "Safety & Security", "카카오뱅크 지급정지 문의"),
    # Batch 060
    "728203412": ("Y", "Digital Skills", "소프트웨어 개발 무료 교육 문의"),
    "728188300": ("Y", "Digital Skills", "윈도우 설치 도움 요청"),
    "728203942": ("?", "Digital Skills", "릴스 만드는 방법 문의"),
    # Batch 061
    "728115741": ("Y", "Affordability", "인터넷+TV 통신비 지원"),
    "728076689": ("Y", "Safety & Security", "네이버 아이디 도용 피해"),
    # Batch 062
    "728031183": ("Y", "Connection Quality", "컴퓨터 인터넷 연결 안됨"),
    "728012461": ("Y", "Digital Skills", "성동구청 디지털교육센터 안내"),
    "728002188": ("Y", "Digital Skills", "성동구청 디지털교육센터 문의"),
    # Batch 063
    "727989635": ("?", "Digital Skills", "아이폰 잠금화면 설정 방법"),
    "733332078": ("Y", "Affordability", "KT Y덤 결합 요금제 문의"),
    # Batch 064
    "733330273": ("Y", "Safety & Security", "당근 판매자 사기 피해"),
    # Batch 065
    "733281702": ("?", "Digital Skills", "외장하드 데이터 복구 방법"),
    "733235870": ("?", "Digital Skills", "캐드/스케치업 배우고 싶음"),
    # Batch 066
    "733179767": ("?", "Digital Skills", "영상편집 무료로 배우기"),
    # Batch 067
    "733113311": ("Y", "Safety & Security", "수산물 사기 업체 주의"),
    "733106441": ("?", "Safety & Security", "갤럭시워치 가개통 사기 주의"),
    # Batch 068
    "733041120": ("Y", "Affordability", "당근 현금지원 인터넷 가입"),
    "733051182": ("Y", "Safety & Security", "보이스피싱 피해예방 10계명"),
    "733050344": ("?", "Safety & Security", "당근 모니터 거래 사기 의심"),
    # Batch 069
    "733027939": ("Y", "Safety & Security", "스미싱 예방법 안내"),
    "733027656": ("Y", "Safety & Security", "상호도용 사기 주의"),
    "733017767": ("Y", "Safety & Security", "쿠팡 정보유출 개인통관 번호 변경"),
    # Batch 070
    "732959097": ("Y", "Safety & Security", "당근 상품권 사기 지급정지 신청"),
    "732940107": ("Y", "Safety & Security", "아이폰 짝퉁 중고거래 사기"),
    # Batch 071
    "732894297": ("?", "Digital Skills", "홈페이지 무료 제작 아임웹 문의"),
    # Batch 072
    "732786242": ("Y", "Safety & Security", "보이스피싱 신고 방법 안내"),
    # Batch 074
    "732614569": ("Y", "Connection Quality", "오피스텔 와이파이 셰어/인터넷 끊김"),
    # Batch 075
    "732641025": ("Y", "Connection Quality", "LG유플러스 와이파이 끊김"),
    # Batch 076
    "732595594": ("?", "Digital Skills", "블루스크린 컴퓨터 문제"),
    "732587123": ("?", "Digital Skills", "갤럭시 탭 비밀번호 초기화"),
    "732557401": ("Y", "Digital Skills", "MS오피스 설치 도움 요청"),
    "732554018": ("?", "Digital Skills", "아이패드 PC 연결 불안정"),
    "732547447": ("Y", "Safety & Security", "당근 상품권 핀번호 사기 주의"),
    "732541630": ("?", "Safety & Security", "에어팟 도난 위치추적 대응"),
    # Batch 077
    "732464938": ("?", "Digital Skills", "컴퓨터 데이터 마이그레이션"),
    "732451706": ("Y", "Digital Skills", "AI 콘텐츠 강의 모집"),
    "732451440": ("Y", "Digital Skills", "HTML/CSS/JS 코딩 오류 수정 요청"),
    "732387047": ("Y", "Safety & Security", "네이버포인트 거래 사기 주의"),
    "732386605": ("Y", "Safety & Security", "네이버페이 포인트 거래 사기"),
    "732449633": ("Y", "Digital Skills", "성동구 엑셀/컴활 컴퓨터 학원"),
    # Batch 078
    "732418680": ("Y", "Connection Quality", "옥수동 삼성아파트 KT 인터넷 나감"),
    "732419942": ("?", "Availability for Use", "왕십리 PC방 폐업 여부"),
    "732395121": ("Y", "Safety & Security", "초등학생 유괴사고 예방 안전교육"),
    # Batch 079
    "732360499": ("?", "Digital Skills", "컴퓨터 조립 파워 안 켜짐"),
    # Batch 080
    "732140547": ("?", "Affordability", "아이폰17 단통법 폐지 페이백"),
    "732112570": ("Y", "Digital Skills", "인쇄/디자인 프로그램 개발 교육"),
    "732111669": ("?", "Digital Skills", "NotebookLM AI 도구 활용"),
    "732101823": ("Y", "Digital Skills", "생성형 AI 활용 스터디"),
    # Batch 081
    "732115583": ("?", "Availability for Use", "도미노 앱/사이트 먹통"),
    # Batch 082
    "732060438": ("?", "Digital Skills", "Gemini/ChatGPT로 AI 시 작성"),
    "732029417": ("?", "Availability for Use", "뚝섬역 USB 없이 링크 프린트"),
    "732025463": ("Y", "Digital Skills", "생성형 AI 활용 스터디"),
    "732009536": ("?", "Digital Skills", "포토샵 재능교환"),
    "732008460": ("Y", "Digital Skills", "서울시 무료 인테리어 디자인 교육"),
    # Batch 083
    "732006602": ("Y", "Safety & Security", "에어팟 판매 사기 입금자명 사기"),
    "731994971": ("Y", "Digital Skills", "AI 굿즈 만들기 창업 스터디"),
    "731981566": ("Y", "Digital Skills", "AI 굿즈 만들기 무료 스터디"),
    "731971093": ("Y", "Digital Skills", "데이터라벨링 전문가 양성 무료교육"),
}

print(f"Total UMC items tracked: {len(umc_items)}")

# Process all batch files
batch_files = sorted([f for f in os.listdir(batches_dir) if f.startswith('\uc131\ub3d9\uad6c_batch')])

written = 0
for batch_file in batch_files:
    response_file = os.path.join(responses_dir, batch_file)
    if os.path.exists(response_file):
        continue

    batch_path = os.path.join(batches_dir, batch_file)
    with open(batch_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract batch number
    m = re.search(r'(\d+)/83', content)
    batch_num = m.group(1) if m else '?'

    # Extract IDs and text snippets
    rows = []
    for line in content.split('\n'):
        if line.startswith('| ') and not line.startswith('| ID') and not line.startswith('|-'):
            parts = line.split('|')
            if len(parts) >= 3:
                id_val = parts[1].strip()
                text_raw = parts[2].strip()
                if id_val and id_val.isdigit():
                    # Truncate text for display
                    text_short = text_raw[:30].replace('\n', ' ') if text_raw else ''
                    rows.append((id_val, text_short))

    # Build response
    lines = [f"# \ubd84\ub958 \uacb0\uacfc: \uc131\ub3d9\uad6c \u2014 {batch_num}/83", "", "| ID | \ud14d\uc2a4\ud2b8 | UMC \uad00\ub828 | UMC \ucc28\uc6d0 | \ubb38\uc81c \uc694\uc57d |", "|----|--------|----------|----------|----------|"]

    for id_val, text_short in rows:
        if id_val in umc_items:
            rel, dim, summ = umc_items[id_val]
            lines.append(f"| {id_val} | {text_short} | {rel} | {dim} | {summ} |")
        else:
            lines.append(f"| {id_val} | {text_short} | N | - | \uad00\ub828\uc5c6\uc74c |")

    with open(response_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')

    written += 1

print(f"Written {written} response files")
print("Done!")
