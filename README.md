# 🥕 당근마켓 텍스트 전처리

서울 전체 당근마켓 커뮤니티 게시글에서 **UMC 연결성 차원**과 관련된 글을 추출하고, 한국어 텍스트를 전처리하는 프로젝트입니다.

## 전체 파이프라인

```
원본 CSV → [데이터 정제] 삭제/차단 제거 및 병합
         → [Phase 0] 키워드 발견 (Claude Code 활용, 포화 추출)
         → [Phase 1] 키워드 필터링
         → [Phase 2] 텍스트 정규화
         → 정제된 데이터
```

| 단계    | 설명                                                         | 파일                         |
| ------- | ------------------------------------------------------------ | ---------------------------- |
| 데이터 정제 | raw CSV에서 DELETED/BLOCKED 제거 후 병합                  | `pipeline.ipynb`             |
| Phase 0 | 씨앗 키워드 → 층화 랜덤 샘플링 → Claude Code로 정밀 키워드 발견 | `src/sample_for_claude.py`   |
| Phase 1 | UMC 차원별 키워드를 포함하는 게시글만 추출                    | `src/filter_by_keyword.py`   |
| Phase 2 | Kiwi 기반 띄어쓰기 교정, 불용어/형태소 필터링                | `src/normalize.py`           |

## 설치 방법

```bash
# 가상환경 생성 및 의존성 설치
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## 사용 방법

### Phase 0: 키워드 발견 (Claude Code 활용)

```bash
# 1. 라운드별 랜덤 샘플 추출 + Claude용 프롬프트 생성
python -m src.sample_for_claude sample --round 1

# 2. prompt_round1.md를 Claude Code에 전달 → JSON 응답 저장

# 3. Claude 응답 병합 + 포화도 확인
python -m src.sample_for_claude merge --round 1 --input data/processed/claude_response_round1.json

# 4. 진행 상태 확인
python -m src.sample_for_claude status
```

> 📓 노트북으로도 실행 가능: `notebooks/phase0_keyword_discovery.ipynb`

### Phase 1~2: 필터링 및 전처리

```bash
# 전체 파이프라인 실행
python -m src.pipeline --input data/raw/your_data.csv

# 키워드 필터링만
python -m src.pipeline --input data/raw/your_data.csv --step filter

# 텍스트 정규화만
python -m src.pipeline --input data/filtered/01_filtered.csv --step normalize
```

## 프로젝트 구조

```
text-preprocessing/
├── config/
│   ├── seed_keywords.yaml    # 씨앗 키워드 (사람이 작성)
│   └── keywords.yaml         # 정밀 키워드 (Phase 0에서 LLM이 생성)
├── data/
│   ├── raw/                  # 원본 데이터 (Git 미추적)
│   └── processed/            # 정제·병합된 데이터 + 샘플 + 프롬프트
├── src/
│   ├── sample_for_claude.py  # Phase 0: 샘플링 + Claude 연동
│   ├── filter_by_keyword.py  # Phase 1: 키워드 필터링
│   ├── normalize.py          # Phase 2: 텍스트 정규화
│   └── pipeline.py           # Phase 1~2 통합 실행
├── notebooks/
│   └── phase0_keyword_discovery.ipynb  # Phase 0 실행 가이드
├── pipeline.ipynb            # 데이터 정제 및 병합
└── tests/
```

## 키워드 설정

`config/keywords.yaml`에 UMC 6개 차원별 키워드를 추가하세요:

```yaml
affordability:
  - 휴대폰 요금
  - 통신비 지원
  - 인터넷 개통

availability:
  - 와이파이
  - 인터넷 설치
```

## 데이터 형식

입력 CSV는 당근마켓 크롤링 데이터 형식을 따릅니다:

| 컬럼         | 설명              |
| ------------ | ----------------- |
| `dbId`       | 게시글 ID         |
| `regionName` | 동 이름           |
| `gu`         | 구 이름           |
| `title`      | 제목              |
| `content`    | 본문              |
| `status`     | 상태 (DELETED 등) |
| ...          | 기타 메타정보     |

## 팀원

| 이름 | 역할                                 |
| ---- | ------------------------------------ |
| 종윤 | 텍스트 분석 깃허브 관리, 전처리 개발 |
| 지윤 | UMC 차원별 키워드 선정, 전처리       |
| 윤지 | UMC 차원별 키워드 선정, 전처리       |
