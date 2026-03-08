"""
Step 2: Kiwi 기반 텍스트 정규화

Kiwi(kiwipiepy) 형태소 분석기를 사용하여:
  - 띄어쓰기가 엉망인 텍스트를 정규화
  - 형태소 분석 + 품사 태깅
  - 품사 기반 필터링 (조사, 어미 등 자동 제거)
  - 어간 추출 (동사/형용사를 원형으로)

이전 ElectraSpacer 방식(공백제거→재띄어쓰기→수동불용어)을
한 단계로 대체합니다.
"""

import re
import pandas as pd  # type: ignore
from pathlib import Path
from tqdm import tqdm  # type: ignore
from kiwipiepy import Kiwi  # type: ignore


# 유지할 품사 태그
# NNG: 일반명사, NNP: 고유명사, NNB: 의존명사
# VV: 동사, VA: 형용사, MAG: 일반부사
# SL: 외국어, SN: 숫자
USEFUL_POS_TAGS = {"NNG", "NNP", "VV", "VA", "MAG", "SL", "SN"}


def init_kiwi() -> Kiwi:
    """Kiwi 형태소 분석기를 초기화합니다."""
    kiwi = Kiwi()
    print("  ✅ Kiwi 형태소 분석기 로드 완료")
    return kiwi


def remove_emoji(text: str) -> str:
    """이모지를 제거합니다."""
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"
        "\U0001f300-\U0001f5ff"
        "\U0001f680-\U0001f6ff"
        "\U0001f1e0-\U0001f1ff"
        "\U00002702-\U000027b0"
        "\U0001f900-\U0001f9ff"
        "\U0001fa00-\U0001fa6f"
        "\U0001fa70-\U0001faff"
        "\U00002600-\U000026ff"
        "\U0000fe00-\U0000fe0f"
        "\U0000200d"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def remove_jamo(text: str) -> str:
    """단독 자모음을 제거합니다 (ㅋㅋ, ㅜㅜ 등)."""
    return re.sub(r"[ㄱ-ㅎㅏ-ㅣ]+", "", text)


def normalize_text(
    kiwi: Kiwi,
    text: str,
    pos_tags: set[str] | None = None,
    join_char: str = " ",
) -> str:
    """Kiwi로 텍스트를 정규화합니다.

    1. 이모지 제거
    2. 단독 자모음 제거
    3. 형태소 분석 + 품사 기반 필터링
    4. 토큰을 공백으로 조합하여 반환

    Args:
        kiwi: Kiwi 인스턴스
        text: 입력 텍스트
        pos_tags: 유지할 품사 태그 set (None이면 기본값 사용)
        join_char: 토큰 사이 구분자

    Returns:
        정규화된 텍스트
    """
    if not isinstance(text, str) or not text.strip():
        return ""

    if pos_tags is None:
        pos_tags = USEFUL_POS_TAGS

    # 1. 이모지, 자모음 제거
    text = remove_emoji(text)
    text = remove_jamo(text)

    if not text.strip():
        return ""

    # 2. Kiwi 형태소 분석
    try:
        tokens = kiwi.tokenize(text)
    except Exception as e:
        print(f"  ⚠️ 형태소 분석 실패: {e}")
        return text

    # 3. 품사 기반 필터링 + 어간 추출
    # Kiwi는 동사/형용사를 어간(lemma)으로 반환 (예: "느려" → "느리다"의 "느리")
    # form이 실제 토큰, tag가 품사
    filtered = [tok.form for tok in tokens if tok.tag in pos_tags]

    return join_char.join(filtered)


def run(
    input_path: str,
    output_path: str,
    content_col: str = "content",
    pos_tags: set[str] | None = None,
) -> pd.DataFrame:
    """텍스트 정규화를 실행합니다.

    Args:
        input_path: 입력 CSV 파일 경로
        output_path: 출력 CSV 파일 경로
        content_col: 정규화할 텍스트 컬럼명
        pos_tags: 유지할 품사 태그 (None이면 기본값)

    Returns:
        정규화된 데이터프레임
    """
    print(f"[Step 2] Kiwi 텍스트 정규화 시작: {input_path}")

    # 데이터 로드
    df = pd.read_csv(input_path, encoding="utf-8")
    print(f"  게시글 수: {len(df):,}")

    # Kiwi 초기화
    kiwi = init_kiwi()

    # 정규화 실행
    tqdm.pandas(desc="텍스트 정규화")
    df["content_normalized"] = df[content_col].fillna("").progress_apply(
        lambda x: normalize_text(kiwi, x, pos_tags)
    )

    # 빈 텍스트 제거
    before = len(df)
    df = df[df["content_normalized"].str.strip() != ""].reset_index(drop=True)
    removed = before - len(df)
    if removed > 0:
        print(f"  빈 텍스트 제거: {removed}건")
    print(f"  최종 게시글 수: {len(df):,}")

    # 저장
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"  저장 완료: {output_path}")

    return df
