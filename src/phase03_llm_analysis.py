"""
Phase 3: UMC 차원 분류 — Claude Code 오프라인 워크플로우

워크플로우:
  1. prepare : 구별 CSV → 배치 입력 마크다운(.md) 생성
  2. parse   : Claude의 마크다운 테이블 응답을 CSV로 파싱
  3. merge   : 파싱된 배치 CSV들을 원본 데이터와 병합하여 최종 CSV 생성

실행 예시:
  # 전체 구 배치 생성
  python -m src.phase03_llm_analysis prepare

  # 특정 구만 배치 생성
  python -m src.phase03_llm_analysis prepare --gu 종로구

  # Claude 응답 파싱
  python -m src.phase03_llm_analysis parse

  # 최종 병합
  python -m src.phase03_llm_analysis merge

Claude Code 사용법:
  1. `prepare` 실행 후 생성된 data/processed/phase03_batches/*.md 파일을
     Claude Code에 열어주세요.
  2. umc_classification_prompt.md를 시스템 프롬프트(CLAUDE.md)로 참조합니다.
  3. Claude 응답을 data/processed/phase03_responses/ 에 동일 파일명으로 저장하세요.
  4. `parse` → `merge` 순서로 실행하여 최종 CSV를 생성하세요.

입출력 파일명 체계:
  data/processed/split_by_gu/{구명}.csv          ← prepare 입력
  data/processed/phase03_batches/{구명}_batch{N}.md   ← prepare 출력 / Claude 입력
  data/processed/phase03_responses/{구명}_batch{N}.md ← Claude 응답 (수동 저장)
  data/processed/phase03_parsed/{구명}_batch{N}.csv   ← parse 출력
  data/processed/03_umc_classified.csv            ← merge 최종 출력
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd  # type: ignore

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ── 경로 상수 ────────────────────────────────────────────────────────────────
SPLIT_DIR = "data/processed/split_by_gu"
BATCH_DIR = "data/processed/phase03_batches"
RESPONSE_DIR = "data/processed/phase03_responses"
PARSED_DIR = "data/processed/phase03_parsed"
FINAL_OUTPUT = "data/processed/03_umc_classified.csv"
PROMPT_FILE = "umc_classification_prompt.md"

# ── UMC 출력 컬럼 정의 ────────────────────────────────────────────────────────
OUTPUT_COLS = ["dbId", "umc_related", "umc_dimensions", "problem_group"]


def _resolve(rel: str) -> Path:
    return PROJECT_ROOT / rel


# ─────────────────────────────────────────────────────────────────────────────
# PREPARE: 배치 입력 마크다운 생성
# ─────────────────────────────────────────────────────────────────────────────

def _build_batch_md(batch_df: pd.DataFrame, gu: str, batch_num: int, total_batches: int) -> str:
    """Claude Code에 전달할 배치 입력 마크다운을 생성합니다.

    umc_classification_prompt.md의 입력 형식에 맞춰
    ID + 텍스트 테이블만 포함합니다.
    """
    lines = [
        f"# 분류 대상 마크다운 데이터: {gu} — {batch_num}/{total_batches}",
        "",
        "| ID | 텍스트 |",
        "|----|--------|",
    ]

    for _, row in batch_df.iterrows():
        db_id = str(row.get("dbId", "")).strip()
        title = str(row.get("title", "") or "").strip()
        content = str(row.get("content", "") or "").strip()
        combined = f"{title} {content}".strip()
        # 테이블 셀 내 파이프 문자 이스케이프
        combined = combined.replace("|", "｜")
        combined_str: str = combined
        if len(combined_str) > 300:
            combined_str = combined_str[:300] + "..."  # type: ignore[index]
        lines.append(f"| {db_id} | {combined_str} |")

    return "\n".join(lines) + "\n"


def run_prepare(
    gu_list: list[str] | None = None,
    batch_size: int = 50,
) -> None:
    """구별 CSV를 읽어 배치 입력 마크다운을 생성합니다.

    Args:
        gu_list:    처리할 구 목록 (None이면 split_by_gu 내 전체)
        batch_size: 배치당 최대 행 수 (기본 50)
    """
    split_dir = _resolve(SPLIT_DIR)
    batch_dir = _resolve(BATCH_DIR)
    batch_dir.mkdir(parents=True, exist_ok=True)

    if gu_list:
        gu_csv_list = [split_dir / f"{gu}.csv" for gu in gu_list]
    else:
        gu_csv_list = sorted(split_dir.glob("*.csv"))

    if not gu_csv_list:
        print(f"❌ {SPLIT_DIR} 에서 CSV 파일을 찾을 수 없습니다.")
        print("   먼저 `python main.py --step split` 을 실행하세요.")
        return

    total_batches_created = 0
    for csv_path in gu_csv_list:
        gu = csv_path.stem
        if not csv_path.exists():
            print(f"⚠️  파일 없음: {csv_path}, 건너뜁니다.")
            continue

        df = pd.read_csv(csv_path, encoding="utf-8")

        if "dbId" not in df.columns:
            print(f"⚠️  'dbId' 컬럼 없음: {csv_path.name} — 임시 ID 부여")
            df["dbId"] = [f"{gu}_{i}" for i in range(len(df))]

        # 필요 컬럼만 추출
        for col in ["title", "content"]:
            if col not in df.columns:
                df[col] = ""

        keep = ["dbId", "title", "content"]
        df = df[keep]

        # 배치 분할
        n_batches = (len(df) + batch_size - 1) // batch_size
        print(f"\n[{gu}] {len(df):,}건 → {n_batches}개 배치 생성")

        for b_idx in range(n_batches):
            batch_df = df.iloc[b_idx * batch_size : (b_idx + 1) * batch_size]
            batch_num = b_idx + 1
            md_content = _build_batch_md(batch_df, gu, batch_num, n_batches)
            out_path = batch_dir / f"{gu}_batch{batch_num:03d}.md"
            out_path.write_text(md_content, encoding="utf-8")
            print(f"  ✅ {out_path.name} ({len(batch_df)}건)")
            total_batches_created = total_batches_created + 1  # type: ignore[operator]

    print(f"\n{'=' * 60}")
    print(f"✅ prepare 완료: 총 {total_batches_created}개 배치 생성")
    print(f"   저장 위치: {batch_dir}")
    print(f"   다음 단계: 각 파일을 Claude Code에서 분석 후")
    print(f"   응답을 {_resolve(RESPONSE_DIR)} 에 동일 파일명으로 저장하세요.")
    print(f"{'=' * 60}")


# ─────────────────────────────────────────────────────────────────────────────
# PARSE: Claude 마크다운 응답 → CSV 파싱
# ─────────────────────────────────────────────────────────────────────────────

def _parse_md_table(md_text: str) -> pd.DataFrame | None:
    """마크다운 테이블에서 분류 결과를 추출하여 DataFrame으로 반환합니다.

    umc_classification_prompt.md의 출력 형식:
    | ID | 텍스트 | UMC관련 | UMC 차원 | 문제 그룹 |

    Returns:
        DataFrame (컬럼: dbId, umc_related, umc_dimensions, problem_group)
        파싱 실패 시 None
    """
    # 마크다운 테이블 추출 — 라인 단위 파싱으로 더 유연하게 처리
    # | 로 시작·끝나는 줄만 수집하여 테이블 블록 그룹화
    all_lines = md_text.splitlines()
    table_blocks: list[list[str]] = []
    current_block: list[str] = []
    in_table = False

    for line in all_lines:
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            in_table = True
            current_block.append(stripped)
        else:
            if in_table and current_block:
                table_blocks.append(list(current_block))
                current_block = []
            in_table = False

    if in_table and current_block:
        table_blocks.append(list(current_block))

    if not table_blocks:
        return None

    # 가장 긴 테이블 선택 (분류 결과 테이블)
    target_block = max(table_blocks, key=len)

    rows: list[list[str]] = []
    for line in target_block:
        cells: list[str] = [c.strip() for c in line.strip("|").split("|")]
        if not cells:
            continue
        # 구분선 행 건너뜀 (---로만 구성)
        if all(re.match(r"^[-: ]*$", c) for c in cells):
            continue
        # 텍스트 셀에 파이프가 포함되어 셀이 분리된 경우 대비:
        # 헤더 기준 컬럼 수보다 셀이 많으면 중간 셀들을 텍스트로 병합
        if rows and len(cells) > len(rows[0]):
            expected = len(rows[0])
            # 첫 셀(ID)은 유지, 마지막 3개 셀(UMC관련/차원/그룹)은 유지, 나머지를 텍스트로 합침
            overflow = len(cells) - expected
            merged_text = "|".join(cells[1 : 1 + overflow + 1])
            cells = [cells[0], merged_text] + cells[2 + overflow :]
        rows.append(cells)

    if len(rows) < 2:
        return None

    # 첫 행: 헤더
    header: list[str] = [h.lower() for h in rows[0]]

    # 컬럼 인덱스 결정 (유연하게)
    def _find_col(*candidates: str) -> int:
        for c in candidates:
            for i, h in enumerate(header):
                if c in h:
                    return i
        return -1

    idx_id = _find_col("id")
    idx_related = _find_col("umc관련", "related", "umc_related")
    idx_dim = _find_col("차원", "dimension")
    idx_group = _find_col("그룹", "group")

    if idx_id < 0:
        return None

    records = []
    for raw_row in rows[1:]:  # type: ignore[index]
        row: list[str] = raw_row
        if len(row) <= max(idx_id, idx_related, idx_dim, idx_group):
            continue
        db_id = row[idx_id] if idx_id >= 0 else ""
        umc_related = row[idx_related] if idx_related >= 0 else ""
        umc_dimensions = row[idx_dim] if idx_dim >= 0 else ""
        problem_group = row[idx_group] if idx_group >= 0 else ""

        # 유효 행 필터 (ID가 있어야 함)
        if not db_id or db_id in ("{ID}", "ID"):
            continue

        records.append({
            "dbId": db_id,
            "umc_related": umc_related,
            "umc_dimensions": umc_dimensions,
            "problem_group": problem_group,
        })

    if not records:
        return None

    return pd.DataFrame(records, columns=OUTPUT_COLS)


def run_parse(gu_list: list[str] | None = None) -> None:
    """Claude 응답 마크다운을 파싱하여 배치별 CSV를 생성합니다.

    Args:
        gu_list: 처리할 구 목록 (None이면 전체)
    """
    response_dir = _resolve(RESPONSE_DIR)
    parsed_dir = _resolve(PARSED_DIR)
    parsed_dir.mkdir(parents=True, exist_ok=True)

    if gu_list:
        pattern_files: list[Path] = []
        for gu in gu_list:
            pattern_files.extend(sorted(response_dir.glob(f"{gu}_batch*.md")))
    else:
        pattern_files = sorted(response_dir.glob("*_batch*.md"))

    if not pattern_files:
        print(f"❌ {RESPONSE_DIR} 에서 응답 파일을 찾을 수 없습니다.")
        print(f"   Claude 응답을 {RESPONSE_DIR}/{{구명}}_batch{{N}}.md 형태로 저장하세요.")
        return

    success_count = 0
    fail_count = 0

    for md_path in pattern_files:
        md_text = md_path.read_text(encoding="utf-8")
        df = _parse_md_table(md_text)

        if df is None or df.empty:
            print(f"⚠️  파싱 실패: {md_path.name}")
            fail_count += 1
            continue

        out_path = parsed_dir / md_path.with_suffix(".csv").name
        df.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"  ✅ {out_path.name} ({len(df)}건 파싱됨)")
        success_count += 1

    print(f"\n parse 완료: 성공 {success_count}개, 실패 {fail_count}개")


# ─────────────────────────────────────────────────────────────────────────────
# MERGE: 파싱 결과 + 원본 데이터 병합
# ─────────────────────────────────────────────────────────────────────────────

def run_merge(
    source_csv: str = "data/processed/02_keyword_filtered.csv",
    output_csv: str = FINAL_OUTPUT,
) -> None:
    """파싱된 배치 CSV들을 원본 데이터와 병합하여 최종 분류 CSV를 생성합니다.

    Args:
        source_csv: 원본(키워드 필터링된) CSV 경로
        output_csv: 최종 출력 CSV 경로
    """
    parsed_dir = _resolve(PARSED_DIR)
    parsed_files = sorted(parsed_dir.glob("*_batch*.csv"))

    if not parsed_files:
        print(f"❌ {PARSED_DIR} 에서 파싱된 파일을 찾을 수 없습니다.")
        print("   먼저 `python main.py --step parse` 를 실행하세요.")
        return

    # 모든 파싱 결과 합치기
    print(f"\n[1/3] 파싱 결과 {len(parsed_files)}개 파일 병합...")
    parsed_dfs = []
    for f in parsed_files:
        df = pd.read_csv(f, encoding="utf-8")
        parsed_dfs.append(df)

    all_parsed = pd.concat(parsed_dfs, ignore_index=True)
    all_parsed["dbId"] = all_parsed["dbId"].astype(str)
    # 중복 제거 (같은 dbId가 여러 배치에 존재하는 경우)
    all_parsed = all_parsed.drop_duplicates(subset=["dbId"], keep="first")
    print(f"  총 파싱 결과: {len(all_parsed):,}건")

    # 원본 데이터 로드
    source_path = _resolve(source_csv)
    if not source_path.exists():
        print(f"❌ 원본 파일 없음: {source_path}")
        return

    print(f"\n[2/3] 원본 데이터 로드: {source_path.name}")
    orig_df = pd.read_csv(source_path, encoding="utf-8")
    if "dbId" not in orig_df.columns:
        print("⚠️  원본에 'dbId' 컬럼 없음 → 인덱스 기반 임시 ID 사용")
        orig_df["dbId"] = orig_df.index.astype(str)
    orig_df["dbId"] = orig_df["dbId"].astype(str)
    print(f"  원본 행 수: {len(orig_df):,}")

    # 병합
    print(f"\n[3/3] 병합 및 최종 CSV 저장...")
    merged = orig_df.merge(
        all_parsed[OUTPUT_COLS],
        on="dbId",
        how="left",
    )

    # 분류 결과가 있는 행만 최종 출력
    classified = merged[merged["umc_related"].notna()].copy()
    print(f"  분류 완료 행: {len(classified):,}건 / 전체 {len(orig_df):,}건")

    out_path = _resolve(output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    classified.to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  ✅ 저장 완료: {out_path}")

    # 간단한 통계 출력
    if "umc_related" in classified.columns:
        counts = classified["umc_related"].value_counts()
        print("\n  [UMC 관련성 분포]")
        for val, cnt in counts.items():
            print(f"    {val}: {cnt:,}건")


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Phase 3: UMC 분류 — Claude Code 오프라인 워크플로우",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예:
  python -m src.phase03_llm_analysis prepare
  python -m src.phase03_llm_analysis prepare --gu 종로구 --batch-size 30
  python -m src.phase03_llm_analysis parse
  python -m src.phase03_llm_analysis parse --gu 종로구
  python -m src.phase03_llm_analysis merge
  python -m src.phase03_llm_analysis merge --source data/processed/02_keyword_filtered.csv
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="서브커맨드")

    # prepare
    sp_prep = subparsers.add_parser("prepare", help="배치 입력 마크다운 생성")
    sp_prep.add_argument(
        "--gu",
        nargs="+",
        default=None,
        metavar="구명",
        help="처리할 구 목록 (기본: 전체). 예: --gu 종로구 강남구",
    )
    sp_prep.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="배치당 게시글 수 (기본: 50)",
    )

    # parse
    sp_parse = subparsers.add_parser("parse", help="Claude 응답 파싱 → 배치 CSV")
    sp_parse.add_argument(
        "--gu",
        nargs="+",
        default=None,
        metavar="구명",
        help="처리할 구 목록 (기본: 전체)",
    )

    # merge
    sp_merge = subparsers.add_parser("merge", help="배치 CSV → 최종 분류 CSV 병합")
    sp_merge.add_argument(
        "--source",
        default="data/processed/02_keyword_filtered.csv",
        help="원본 CSV 경로 (기본: data/processed/02_keyword_filtered.csv)",
    )
    sp_merge.add_argument(
        "--output",
        default=FINAL_OUTPUT,
        help=f"최종 출력 CSV 경로 (기본: {FINAL_OUTPUT})",
    )

    args = parser.parse_args()

    if args.command == "prepare":
        run_prepare(gu_list=args.gu, batch_size=args.batch_size)
    elif args.command == "parse":
        run_parse(gu_list=args.gu)
    elif args.command == "merge":
        run_merge(source_csv=args.source, output_csv=args.output)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
