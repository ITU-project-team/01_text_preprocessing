"""
Phase 2: 구(gu)별 CSV 분할

키워드 필터링된 데이터를 자치구별로 분리하여 저장합니다.

실행:
  python -m src.phase02_split_by_gu --input data/processed/02_keyword_filtered.csv

출력:
  data/processed/split_by_gu/{구명}.csv
"""

import argparse
from pathlib import Path

import pandas as pd  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve(rel: str) -> Path:
    return PROJECT_ROOT / rel


def run(
    input_path: str,
    output_dir: str = "data/processed/split_by_gu",
    gu_col: str = "gu",
) -> dict[str, int]:
    """키워드 필터링된 CSV를 구별로 분할합니다.

    Args:
        input_path: 입력 CSV 파일 경로
        output_dir:  구별 CSV 저장 디렉토리
        gu_col: 구(자치구) 컬럼명

    Returns:
        {구명: 행 수} 딕셔너리
    """
    print(f"[Phase 2] 구별 분할 시작: {input_path}")

    df = pd.read_csv(input_path, encoding="utf-8")
    print(f"  전체 행 수: {len(df):,}")

    if gu_col not in df.columns:
        raise ValueError(f"컬럼 '{gu_col}'이 없습니다. 컬럼 목록: {list(df.columns)}")

    out_dir = PROJECT_ROOT / output_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    stats: dict[str, int] = {}
    gu_list = sorted(df[gu_col].dropna().unique())
    print(f"  자치구 수: {len(gu_list)}개")

    for gu in gu_list:
        gu_df = df[df[gu_col] == gu].reset_index(drop=True)
        out_path = out_dir / f"{gu}.csv"
        gu_df.to_csv(out_path, index=False, encoding="utf-8-sig")
        stats[gu] = len(gu_df)
        print(f"  저장: {out_path.name} ({len(gu_df):,}건)")

    print(f"\n  ✅ 총 {len(gu_list)}개 구 분할 완료")
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="키워드 필터링 결과를 구별로 분할")
    parser.add_argument(
        "--input",
        default="data/processed/02_keyword_filtered.csv",
        help="입력 CSV 파일 경로 (기본: data/processed/02_keyword_filtered.csv)",
    )
    parser.add_argument(
        "--output-dir",
        default="data/processed/split_by_gu",
        help="구별 CSV 저장 디렉토리 (기본: data/processed/split_by_gu)",
    )
    parser.add_argument(
        "--gu-col",
        default="gu",
        help="구(자치구) 컬럼명 (기본: gu)",
    )
    args = parser.parse_args()
    run(
        input_path=str(_resolve(args.input)),
        output_dir=args.output_dir,
        gu_col=args.gu_col,
    )


if __name__ == "__main__":
    main()
