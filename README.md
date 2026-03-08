# 🥕 당근마켓 텍스트 전처리

서울 전체 당근마켓 커뮤니티 게시글에서 **UMC 연결성 차원**과 관련된 글을 추출하고, 한국어 텍스트를 전처리하는 프로젝트입니다.

## 전처리 파이프라인

```
원본 CSV → [Step 1] 키워드 필터링 → [Step 2] 텍스트 정규화 → 정제된 데이터
```

| 단계   | 설명                                          | 파일                       |
| ------ | --------------------------------------------- | -------------------------- |
| Step 1 | UMC 차원별 키워드를 포함하는 게시글만 추출    | `src/filter_by_keyword.py` |
| Step 2 | Kiwi 기반 띄어쓰기 교정, 불용어/형태소 필터링 | `src/normalize.py`         |

## 설치 방법

```bash
# 가상환경 생성 및 의존성 설치
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
```

## 사용 방법

### 전체 파이프라인 실행

```bash
python -m src.pipeline --input data/raw/your_data.csv
```

### 특정 단계만 실행

```bash
# 키워드 필터링만
python -m src.pipeline --input data/raw/your_data.csv --step filter

# 텍스트 정규화만 (띄어쓰기/형태소 교정)
python -m src.pipeline --input data/filtered/01_filtered.csv --step normalize
```

## 프로젝트 구조

```
text-preprocessing/
├── config/
│   └── keywords.yaml         # UMC 차원별 키워드 (팀원이 채울 것)
├── data/
│   ├── raw/                  # 원본 데이터 (Git 미추적)
│   ├── filtered/             # 필터링 결과
│   └── processed/            # 최종 결과
├── src/
│   ├── filter_by_keyword.py  # Step 1
│   ├── normalize.py          # Step 2
│   └── pipeline.py           # 통합 실행
├── notebooks/                # 분석용 노트북
└── tests/                    # 테스트
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
