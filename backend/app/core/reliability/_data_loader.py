"""
Shared data loader for reliability calculations (RE-FI-020).

This module provides the ReliabilityDataLoader class which optimizes database
queries by loading all required data for reliability calculations in a single pass.
This reduces database round trips when calculating multiple reliability metrics
in get_reliability_report().

Reference:
    docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-FI-020)
"""

import logging
from datetime import datetime
from typing import List, Optional, Tuple, TypedDict

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, select

from app.models.models import (
    Response,
    TestSession,
    TestStatus,
    TestResult,
)

logger = logging.getLogger(__name__)


class ReliabilityResponseData(TypedDict):
    """Data structure for response-based reliability calculations."""

    completed_sessions_count: int
    # (session_id, question_id, is_correct, response_id)
    # response_id is included for ordering in split-half calculation
    responses: List[Tuple[int, int, bool, int]]


class ReliabilityTestRetestData(TypedDict):
    """Data structure for test-retest reliability calculations."""

    test_results: List[Tuple[int, int, datetime]]  # (user_id, iq_score, completed_at)


class ReliabilityDataLoader:
    """
    Shared data loader for reliability calculations.

    This class loads all required data for reliability calculations in a single
    pass, reducing database round trips when calculating multiple metrics.

    Usage:
        loader = ReliabilityDataLoader(db)
        response_data = loader.get_response_data()  # For alpha and split-half
        test_retest_data = loader.get_test_retest_data()  # For test-retest

    The loader caches results, so calling the same getter multiple times will
    not trigger additional database queries.

    Reference:
        docs/plans/in-progress/PLAN-RELIABILITY-ESTIMATION.md (RE-FI-020)
    """

    def __init__(self, db: AsyncSession):
        """
        Initialize the data loader.

        Args:
            db: Database session for queries
        """
        self._db = db
        self._response_data: Optional[ReliabilityResponseData] = None
        self._test_retest_data: Optional[ReliabilityTestRetestData] = None

    async def get_response_data(self) -> ReliabilityResponseData:
        """
        Get response data for Cronbach's alpha and split-half calculations.

        This method loads:
        - Count of completed test sessions
        - All responses from completed sessions (session_id, question_id, is_correct, response_id)

        The response_id is included to support ordering for split-half calculation,
        which needs to split responses by their position within each session.

        The data is cached after the first call, so subsequent calls return
        the cached data without additional database queries.

        Returns:
            ReliabilityResponseData containing session count and responses
        """
        if self._response_data is not None:
            return self._response_data

        # Count completed sessions
        completed_sessions_stmt = select(func.count(TestSession.id)).filter(
            TestSession.status == TestStatus.COMPLETED
        )
        result = await self._db.execute(completed_sessions_stmt)
        completed_sessions_count = result.scalar() or 0

        # Get all responses from completed sessions
        # Include Response.id for ordering in split-half calculation
        responses_stmt = (
            select(
                Response.test_session_id,
                Response.question_id,
                Response.is_correct,
                Response.id,
            )
            .join(TestSession, Response.test_session_id == TestSession.id)
            .filter(TestSession.status == TestStatus.COMPLETED)
        )
        result = await self._db.execute(responses_stmt)
        responses_query = result.all()

        # Convert to list of tuples for consistent typing
        # Include response_id for split-half ordering
        responses = [
            (r.test_session_id, r.question_id, r.is_correct, r.id)
            for r in responses_query
        ]

        self._response_data = {
            "completed_sessions_count": completed_sessions_count,
            "responses": responses,
        }

        logger.debug(
            f"ReliabilityDataLoader: Loaded {completed_sessions_count} completed sessions "
            f"and {len(responses)} responses"
        )

        return self._response_data

    async def get_test_retest_data(self) -> ReliabilityTestRetestData:
        """
        Get test result data for test-retest reliability calculations.

        This method loads user test results (user_id, iq_score, completed_at)
        for all completed test sessions, ordered by user and completion time.

        The data is cached after the first call, so subsequent calls return
        the cached data without additional database queries.

        Returns:
            ReliabilityTestRetestData containing test results
        """
        if self._test_retest_data is not None:
            return self._test_retest_data

        # Get all completed test results ordered by user and time
        results_stmt = (
            select(
                TestResult.user_id,
                TestResult.iq_score,
                TestResult.completed_at,
            )
            .join(TestSession, TestResult.test_session_id == TestSession.id)
            .filter(TestSession.status == TestStatus.COMPLETED)
            .order_by(TestResult.user_id, TestResult.completed_at)
        )
        result = await self._db.execute(results_stmt)
        results_query = result.all()

        # Convert to list of tuples for consistent typing
        test_results = [(r.user_id, r.iq_score, r.completed_at) for r in results_query]

        self._test_retest_data = {
            "test_results": test_results,
        }

        logger.debug(
            f"ReliabilityDataLoader: Loaded {len(test_results)} test results for "
            "test-retest calculation"
        )

        return self._test_retest_data

    async def preload_all(self) -> None:
        """
        Preload all data for reliability calculations.

        This method triggers loading of both response data and test-retest data.
        Use this when you know you'll need both datasets to avoid interleaved
        queries.
        """
        await self.get_response_data()
        await self.get_test_retest_data()
        logger.debug("ReliabilityDataLoader: Preloaded all reliability data")
