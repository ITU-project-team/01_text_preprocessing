# 🥕 당근마켓 텍스트 전처리 & UMC 분류

서울 전체 당근마켓 커뮤니티 게시글에서 **UMC(Universal Meaningful Connectivity) 6개 차원**과 관련된 글을 추출하고 분류합니다.

## 전체 파이프라인

```
raw CSV
  └─ [데이터 정제]  phase00_data_cleaning.ipynb
       └─ data/processed/01_cleaned_merged.csv
            └─ [Phase 1: filter]  키워드 필터링
                 └─ data/processed/02_keyword_filtered.csv
                      └─ [Phase 2: split]  구별 분할
                           └─ data/processed/split_by_gu/{구명}.csv
                                └─ [Phase 3a: prepare]  배치 입력 생성
                                     └─ data/processed/phase03_batches/{구명}_batch{N}.md
                                          └─ [Claude Code 분석]  (수동)
                                               └─ data/processed/phase03_responses/
                                                    └─ [Phase 3b: parse]  응답 파싱
                                                         └─ data/processed/phase03_parsed/
                                                              └─ [Phase 3c: merge]
                                                                   └─ data/processed/03_umc_classified.csv
```

## 설치

```bash
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## 실행 방법

### 통합 실행 (추천)

```bash
# 전체 파이프라인 (filter → split → prepare)
python main.py

# 응답 저장 후 나머지
python main.py --step parse merge
```

### 단계별 실행

```bash
python main.py --step filter             # Phase 1: 키워드 필터링
python main.py --step split              # Phase 2: 구별 분할
python main.py --step prepare            # Phase 3a: 배치 입력 생성
python main.py --step prepare --gu 종로구 # 특정 구만
python main.py --step parse              # Phase 3b: Claude 응답 파싱
python main.py --step merge              # Phase 3c: 최종 병합
```

### Phase 0: 키워드 발견 (별도 실행)

```bash
python -m src.phase00_sample_for_claude sample --round 1
python -m src.phase00_sample_for_claude merge --round 1 --input data/processed/claude_response_round1.json
python -m src.phase00_sample_for_claude status
```

> 📓 노트북으로도 실행 가능: `notebooks/phase00_keyword_discovery.ipynb`

## Claude Code 분류 워크플로우

1. `python main.py --step prepare` 실행 → `data/processed/phase03_batches/*.md` 생성
2. Claude Code 시작 (`CLAUDE.md` 자동 인식)
3. 배치 파일 분석 → `data/processed/phase03_responses/` 에 동일 파일명으로 저장
4. `python main.py --step parse merge` 실행 → `data/processed/03_umc_classified.csv` 생성

> 📓 노트북: `notebooks/phase03_llm_analysis.ipynb`

## 프로젝트 구조

```
text-preprocessing/
├── CLAUDE.md                            # Claude Code 시스템 프롬프트 (자동 인식)
├── umc_classification_prompt.md         # UMC 분류 에이전트 프롬프트
├── main.py                              # 통합 파이프라인 실행 진입점
├── config/
│   ├── seed_keywords.yaml               # 씨앗 키워드 (사람이 작성)
│   └── keywords.yaml                    # 정밀 키워드 (Phase 0 LLM 생성)
├── data/
│   ├── raw/                             # 원본 데이터 (Git 미추적)
│   └── processed/
│       ├── 01_cleaned_merged.csv        # 정제·병합된 전체 데이터
│       ├── 02_keyword_filtered.csv      # 키워드 필터링 결과
│       ├── split_by_gu/                 # 구별 분할 CSV
│       ├── phase03_batches/             # Claude 배치 입력
│       ├── phase03_responses/           # Claude 응답 (수동 저장)
│       ├── phase03_parsed/              # 파싱된 배치 CSV
│       └── 03_umc_classified.csv        # 최종 분류 결과
├── src/
│   ├── phase00_data_cleaning.py         # Phase 00: 데이터 클리닝 및 병합
│   ├── phase00_sample_for_claude.py     # Phase 0: 키워드 발견
│   ├── phase01_keyword_filter.py        # Phase 1: 키워드 필터링
│   ├── phase02_split_by_gu.py           # Phase 2: 구별 분할
│   └── phase03_llm_analysis.py          # Phase 3: prepare / parse / merge
└── notebooks/
    ├── phase00_data_cleaning.ipynb      # 데이터 정제
    ├── phase00_keyword_discovery.ipynb   # Phase 0 실행 가이드
    ├── phase01_keyword_filtering.ipynb   # Phase 1 실행 가이드
    ├── phase02_split_by_gu.ipynb   # Phase 2 실행 가이드
    └── phase03_llm_analysis.ipynb       # Phase 3 실행 가이드
```

## UMC 6개 차원

| 차원 | 설명 |
|------|------|
| `Connection Quality` | 연결 품질 (인터넷 속도, 안정성) |
| `Availability for Use` | 이용 가능성 (장소·시간 제약) |
| `Affordability` | 경제적 접근성 (통신비 부담) |
| `Devices` | 기기 접근성 (스마트폰, PC 보유) |
| `Digital Skills` | 디지털 역량 (앱 사용, 리터러시) |
| `Safety & Security` | 안전·보안 (사기, 개인정보) |

## 출력 CSV 컬럼 (`03_umc_classified.csv`)

| 컬럼 | 설명 |
|------|------|
| `dbId` | 게시글 ID |
| `gu` | 자치구 |
| `title` | 제목 |
| `content` | 본문 |
| `umc_related` | UMC 관련성 (`Y` / `N` / `?`) |
| `umc_dimensions` | 해당 UMC 차원 (쉼표 구분) |
| `problem_group` | 문제 그룹명 |

## 팀원

| 이름 | 역할 |
|------|------|
| 종윤 | 텍스트 분석 깃허브 관리, 전처리 개발 |
| 지윤 | UMC 차원별 키워드 선정, 전처리 |
| 윤지 | UMC 차원별 키워드 선정, 전처리 |
