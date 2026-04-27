"""
Step 1: 키워드 기반 게시글 필터링

당근마켓 CSV 데이터에서 UMC 차원별 키워드를 포함하는 게시글만 추출합니다.
"""

import pandas as pd  # type: ignore
import yaml  # type: ignore
from pathlib import Path
from tqdm import tqdm  # type: ignore


def load_keywords(keywords_path: str = "config/keywords.yaml") -> dict[str, list[str]]:
    """keywords.yaml에서 차원별 키워드를 로드합니다.

    Returns:
        dict: {차원명: [키워드1, 키워드2, ...]}
    """
    with open(keywords_path, "r", encoding="utf-8") as f:
        keywords = yaml.safe_load(f)

    # 빈 리스트인 차원은 제외
    return {dim: kws for dim, kws in keywords.items() if kws}


def filter_deleted_posts(df: pd.DataFrame) -> pd.DataFrame:
    """삭제, 숨김(BLOCKED), 또는 내용이 없는 게시글을 제거하고 결과를 출력합니다."""
    initial_count = len(df)

    # status가 DELETED 또는 BLOCKED인 행 제거
    if "status" in df.columns:
        df = df[~df["status"].isin(["DELETED", "BLOCKED"])]

    # content가 비어있는 행 제거
    if "content" in df.columns:
        df = df[df["content"].notna() & (df["content"].str.strip() != "")]

    final_count = len(df)
    removed_count = initial_count - final_count
    ratio = (removed_count / initial_count * 100) if initial_count > 0 else 0.0

    print(f"  [데이터 정제] 전체 원본 데이터: {initial_count:,}개")
    print(f"  [데이터 정제] 정제된 데이터: {final_count:,}개")
    print(f"  [데이터 정제] 제외된 데이터(삭제/숨김/빈게시글): {removed_count:,}개 ({ratio:.2f}%)")

    return df.reset_index(drop=True)


def check_keyword_match(text: str, keywords: list[str]) -> bool:
    """텍스트에 키워드 중 하나라도 포함되어 있는지 확인합니다."""
    if not isinstance(text, str):
        return False
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def filter_by_keywords(
    df: pd.DataFrame,
    keywords: dict[str, list[str]],
) -> pd.DataFrame:
    """키워드를 포함하는 게시글만 필터링하고, 매칭된 차원 정보를 추가합니다.

    Args:
        df: 원본 데이터프레임
        keywords: {차원명: [키워드 리스트]}

    Returns:
        필터링된 데이터프레임 (matched_dimensions 컬럼 추가)
    """
    # title + content를 합쳐서 검색
    df = df.copy()
    df["_search_text"] = (
        df.get("title", pd.Series([""] * len(df))).fillna("")
        + " "
        + df.get("content", pd.Series([""] * len(df))).fillna("")
    )

    matched_rows = []
    matched_dims = []

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="키워드 필터링"):
        text = row["_search_text"]
        dims = [
            dim
            for dim, kws in keywords.items()
            if check_keyword_match(text, kws)
        ]
        if dims:
            matched_rows.append(idx)
            matched_dims.append(", ".join(dims))

    result = df.loc[matched_rows].copy()
    result["matched_dimensions"] = matched_dims
    result = result.drop(columns=["_search_text"])

    return result.reset_index(drop=True)


def run(
    input_path: str,
    output_path: str,
    keywords_path: str = "config/keywords.yaml",
) -> pd.DataFrame:
    """키워드 필터링을 실행합니다.

    Args:
        input_path: 입력 CSV 파일 경로
        output_path: 출력 CSV 파일 경로
        keywords_path: 키워드 YAML 파일 경로

    Returns:
        필터링된 데이터프레임
    """
    print(f"[Step 1] 키워드 필터링 시작: {input_path}")

    # 키워드 로드
    keywords = load_keywords(keywords_path)
    if not keywords:
        print("⚠️  설정된 키워드가 없습니다. config/keywords.yaml을 확인하세요.")
        return pd.DataFrame()

    print(f"  로드된 차원 수: {len(keywords)}")
    for dim, kws in keywords.items():
        print(f"    - {dim}: {len(kws)}개 키워드")

    # 데이터 로드
    df = pd.read_csv(input_path, encoding="utf-8")

    # 삭제/빈 게시글 제거
    df = filter_deleted_posts(df)

    # 키워드 필터링
    result = filter_by_keywords(df, keywords)
    print(f"  키워드 매칭된 게시글 수: {len(result):,}")

    # 저장
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"  저장 완료: {output_path}")

    return result
