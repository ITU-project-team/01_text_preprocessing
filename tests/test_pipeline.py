"""핵심 파이프라인 함수 단위 테스트"""

import pandas as pd
import pytest

from src.phase01_keyword_filter import check_keyword_match, filter_by_keywords, filter_deleted_posts
from src.phase03_llm_analysis import _parse_md_table


# ── filter_deleted_posts ────────────────────────────────────────────────────

class TestFilterDeletedPosts:
    def test_removes_deleted_and_blocked(self):
        df = pd.DataFrame({
            "status": ["ACTIVE", "DELETED", "BLOCKED", "ACTIVE"],
            "content": ["hi", "bye", "no", "ok"],
        })
        result = filter_deleted_posts(df)
        assert len(result) == 2
        assert list(result["content"]) == ["hi", "ok"]

    def test_removes_empty_content(self):
        df = pd.DataFrame({
            "status": ["ACTIVE", "ACTIVE", "ACTIVE"],
            "content": ["hello", "", None],
        })
        result = filter_deleted_posts(df)
        assert len(result) == 1

    def test_no_status_column(self):
        df = pd.DataFrame({"content": ["a", "b"]})
        result = filter_deleted_posts(df)
        assert len(result) == 2


# ── check_keyword_match ─────────────────────────────────────────────────────

class TestCheckKeywordMatch:
    def test_match_found(self):
        assert check_keyword_match("인터넷이 느려요", ["느려"])

    def test_case_insensitive(self):
        assert check_keyword_match("WiFi is slow", ["wifi"])

    def test_no_match(self):
        assert not check_keyword_match("맛집 추천해주세요", ["느려", "끊겨"])

    def test_non_string(self):
        assert not check_keyword_match(None, ["test"])


# ── filter_by_keywords ──────────────────────────────────────────────────────

class TestFilterByKeywords:
    def test_basic_filtering(self):
        df = pd.DataFrame({
            "title": ["인터넷 느려요", "맛집 추천", "와이파이 끊겨"],
            "content": ["정말 답답", "여기 좋아요", "계속 끊김"],
        })
        keywords = {"connection_quality": ["느려", "끊겨", "끊김"]}
        result = filter_by_keywords(df, keywords)
        assert len(result) == 2
        assert "matched_dimensions" in result.columns


# ── _parse_md_table ─────────────────────────────────────────────────────────

class TestParseMdTable:
    def test_basic_parse(self):
        md = """\
| ID | 텍스트 | UMC관련 | UMC 차원 | 문제 그룹 |
|----|--------|---------|----------|-----------|
| 100 | 인터넷 느림 | Y | Connection Quality | 인터넷 속도 불만 |
| 200 | 맛집 추천 | N | - | 관련없음 |
"""
        df = _parse_md_table(md)
        assert df is not None
        assert len(df) == 2
        assert df.iloc[0]["dbId"] == "100"
        assert df.iloc[0]["umc_related"] == "Y"

    def test_pipe_in_text(self):
        """텍스트 셀에 파이프(|)가 포함된 경우도 파싱 가능해야 함"""
        md = """\
| ID | 텍스트 | UMC관련 | UMC 차원 | 문제 그룹 |
|----|--------|---------|----------|-----------|
| 100 | A｜B 텍스트 | Y | Connection Quality | 문제요약 |
"""
        df = _parse_md_table(md)
        assert df is not None
        assert len(df) == 1

    def test_empty_input(self):
        assert _parse_md_table("no table here") is None

    def test_header_only(self):
        md = """\
| ID | 텍스트 | UMC관련 |
|----|--------|---------|
"""
        result = _parse_md_table(md)
        assert result is None
