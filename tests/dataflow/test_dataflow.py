"""Data flow and transformation pipeline tests."""

import os
import uuid
import pytest
import asyncio
from datetime import timedelta
from temporalio.client import Client
from temporalio.worker import Worker
from temporalio import workflow, activity


TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")
TASK_QUEUE = "e2e-dataflow"


@activity.defn
async def extract_data(source: str) -> dict:
    """Extract data from source."""
    return {
        "source": source,
        "data": [1, 2, 3, 4, 5],
        "metadata": {"extracted_at": "2024-01-01"},
    }


@activity.defn
async def transform_data(data: list, operation: str) -> list:
    """Transform data."""
    if operation == "double":
        return [x * 2 for x in data]
    elif operation == "filter_even":
        return [x for x in data if x % 2 == 0]
    elif operation == "square":
        return [x * x for x in data]
    else:
        return data


@activity.defn
async def load_data(destination: str, data: list) -> dict:
    """Load data to destination."""
    return {
        "destination": destination,
        "count": len(data),
        "success": True,
    }


@activity.defn
async def validate_data(data: list) -> bool:
    """Validate data."""
    return all(isinstance(x, int) for x in data)


@activity.defn
async def aggregate_data(data: list) -> dict:
    """Aggregate data."""
    return {
        "sum": sum(data),
        "count": len(data),
        "avg": sum(data) / len(data) if data else 0,
        "min": min(data) if data else 0,
        "max": max(data) if data else 0,
    }


@activity.defn
async def split_data(data: list, chunk_size: int) -> list:
    """Split data into chunks."""
    return [data[i : i + chunk_size] for i in range(0, len(data), chunk_size)]


@activity.defn
async def merge_data(chunks: list) -> list:
    """Merge data chunks."""
    result = []
    for chunk in chunks:
        result.extend(chunk)
    return result


@activity.defn
async def enrich_data(data: list, factor: int) -> list:
    """Enrich data with additional info."""
    return [{"value": x, "enriched": x * factor} for x in data]


@workflow.defn
class ETLWorkflow:
    @workflow.run
    async def run(self, source: str, operation: str, destination: str) -> dict:
        # Extract
        extracted = await workflow.execute_activity(
            extract_data,
            source,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Transform
        transformed = await workflow.execute_activity(
            transform_data,
            args=[extracted["data"], operation],
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Load
        result = await workflow.execute_activity(
            load_data,
            args=[destination, transformed],
            start_to_close_timeout=timedelta(seconds=30),
        )

        return result


@workflow.defn
class ValidationWorkflow:
    @workflow.run
    async def run(self, source: str) -> bool:
        extracted = await workflow.execute_activity(
            extract_data,
            source,
            start_to_close_timeout=timedelta(seconds=30),
        )

        is_valid = await workflow.execute_activity(
            validate_data,
            extracted["data"],
            start_to_close_timeout=timedelta(seconds=30),
        )

        return is_valid


@workflow.defn
class AggregationWorkflow:
    @workflow.run
    async def run(self, source: str) -> dict:
        extracted = await workflow.execute_activity(
            extract_data,
            source,
            start_to_close_timeout=timedelta(seconds=30),
        )

        aggregated = await workflow.execute_activity(
            aggregate_data,
            extracted["data"],
            start_to_close_timeout=timedelta(seconds=30),
        )

        return aggregated


@workflow.defn
class SplitMergeWorkflow:
    @workflow.run
    async def run(self, source: str, chunk_size: int) -> list:
        extracted = await workflow.execute_activity(
            extract_data,
            source,
            start_to_close_timeout=timedelta(seconds=30),
        )

        chunks = await workflow.execute_activity(
            split_data,
            args=[extracted["data"], chunk_size],
            start_to_close_timeout=timedelta(seconds=30),
        )

        merged = await workflow.execute_activity(
            merge_data,
            chunks,
            start_to_close_timeout=timedelta(seconds=30),
        )

        return merged


@workflow.defn
class EnrichmentWorkflow:
    @workflow.run
    async def run(self, source: str, factor: int) -> list:
        extracted = await workflow.execute_activity(
            extract_data,
            source,
            start_to_close_timeout=timedelta(seconds=30),
        )

        enriched = await workflow.execute_activity(
            enrich_data,
            args=[extracted["data"], factor],
            start_to_close_timeout=timedelta(seconds=30),
        )

        return enriched


@workflow.defn
class MultiTransformWorkflow:
    @workflow.run
    async def run(self, source: str) -> list:
        extracted = await workflow.execute_activity(
            extract_data,
            source,
            start_to_close_timeout=timedelta(seconds=30),
        )

        # Apply multiple transformations
        doubled = await workflow.execute_activity(
            transform_data,
            args=[extracted["data"], "double"],
            start_to_close_timeout=timedelta(seconds=30),
        )

        squared = await workflow.execute_activity(
            transform_data,
            args=[doubled, "square"],
            start_to_close_timeout=timedelta(seconds=30),
        )

        return squared


@pytest.mark.asyncio
async def test_etl_double():
    """Test ETL workflow with double transformation."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ETLWorkflow],
        activities=[extract_data, transform_data, load_data],
    ):
        result = await client.execute_workflow(
            ETLWorkflow.run,
            args=["source1", "double", "dest1"],
            id=f"test-etl-double-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["success"] is True
        assert result["count"] == 5


@pytest.mark.asyncio
async def test_etl_filter():
    """Test ETL workflow with filter transformation."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ETLWorkflow],
        activities=[extract_data, transform_data, load_data],
    ):
        result = await client.execute_workflow(
            ETLWorkflow.run,
            args=["source2", "filter_even", "dest2"],
            id=f"test-etl-filter-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["success"] is True
        assert result["count"] == 2  # Only 2 and 4 are even


@pytest.mark.asyncio
async def test_etl_square():
    """Test ETL workflow with square transformation."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ETLWorkflow],
        activities=[extract_data, transform_data, load_data],
    ):
        result = await client.execute_workflow(
            ETLWorkflow.run,
            args=["source3", "square", "dest3"],
            id=f"test-etl-square-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["success"] is True
        assert result["count"] == 5


@pytest.mark.asyncio
async def test_validation():
    """Test data validation workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ValidationWorkflow],
        activities=[extract_data, validate_data],
    ):
        result = await client.execute_workflow(
            ValidationWorkflow.run,
            "source_valid",
            id=f"test-validation-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result is True


@pytest.mark.asyncio
async def test_aggregation():
    """Test data aggregation workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AggregationWorkflow],
        activities=[extract_data, aggregate_data],
    ):
        result = await client.execute_workflow(
            AggregationWorkflow.run,
            "source_agg",
            id=f"test-agg-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["sum"] == 15  # 1+2+3+4+5
        assert result["count"] == 5
        assert result["avg"] == 3.0


@pytest.mark.asyncio
async def test_split_merge():
    """Test split and merge workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SplitMergeWorkflow],
        activities=[extract_data, split_data, merge_data],
    ):
        result = await client.execute_workflow(
            SplitMergeWorkflow.run,
            args=["source_split", 2],
            id=f"test-split-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_enrichment():
    """Test data enrichment workflow."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[EnrichmentWorkflow],
        activities=[extract_data, enrich_data],
    ):
        result = await client.execute_workflow(
            EnrichmentWorkflow.run,
            args=["source_enrich", 10],
            id=f"test-enrich-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert len(result) == 5
        assert result[0]["value"] == 1
        assert result[0]["enriched"] == 10


@pytest.mark.asyncio
async def test_multi_transform():
    """Test multiple transformations."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[MultiTransformWorkflow],
        activities=[extract_data, transform_data],
    ):
        result = await client.execute_workflow(
            MultiTransformWorkflow.run,
            "source_multi",
            id=f"test-multi-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        # [1,2,3,4,5] -> [2,4,6,8,10] -> [4,16,36,64,100]
        assert result == [4, 16, 36, 64, 100]


@pytest.mark.asyncio
async def test_etl_empty_source():
    """Test ETL with empty source name."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ETLWorkflow],
        activities=[extract_data, transform_data, load_data],
    ):
        result = await client.execute_workflow(
            ETLWorkflow.run,
            args=["", "double", "dest"],
            id=f"test-etl-empty-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["success"] is True


@pytest.mark.asyncio
async def test_split_size_one():
    """Test split with chunk size 1."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SplitMergeWorkflow],
        activities=[extract_data, split_data, merge_data],
    ):
        result = await client.execute_workflow(
            SplitMergeWorkflow.run,
            args=["source", 1],
            id=f"test-split-one-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_split_large_chunk():
    """Test split with large chunk size."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SplitMergeWorkflow],
        activities=[extract_data, split_data, merge_data],
    ):
        result = await client.execute_workflow(
            SplitMergeWorkflow.run,
            args=["source", 100],
            id=f"test-split-large-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_enrichment_zero_factor():
    """Test enrichment with zero factor."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[EnrichmentWorkflow],
        activities=[extract_data, enrich_data],
    ):
        result = await client.execute_workflow(
            EnrichmentWorkflow.run,
            args=["source", 0],
            id=f"test-enrich-zero-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert all(r["enriched"] == 0 for r in result)


@pytest.mark.asyncio
async def test_enrichment_negative_factor():
    """Test enrichment with negative factor."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[EnrichmentWorkflow],
        activities=[extract_data, enrich_data],
    ):
        result = await client.execute_workflow(
            EnrichmentWorkflow.run,
            args=["source", -5],
            id=f"test-enrich-neg-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result[0]["enriched"] == -5


@pytest.mark.asyncio
async def test_aggregation_values():
    """Test aggregation min/max values."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AggregationWorkflow],
        activities=[extract_data, aggregate_data],
    ):
        result = await client.execute_workflow(
            AggregationWorkflow.run,
            "source",
            id=f"test-agg-minmax-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["min"] == 1
        assert result["max"] == 5


@pytest.mark.asyncio
async def test_etl_unicode_destination():
    """Test ETL with unicode destination."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ETLWorkflow],
        activities=[extract_data, transform_data, load_data],
    ):
        result = await client.execute_workflow(
            ETLWorkflow.run,
            args=["source", "double", "目的地"],
            id=f"test-etl-unicode-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["success"] is True


@pytest.mark.asyncio
async def test_split_chunk_three():
    """Test split with chunk size 3."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[SplitMergeWorkflow],
        activities=[extract_data, split_data, merge_data],
    ):
        result = await client.execute_workflow(
            SplitMergeWorkflow.run,
            args=["source", 3],
            id=f"test-split-three-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result == [1, 2, 3, 4, 5]


@pytest.mark.asyncio
async def test_enrichment_large_factor():
    """Test enrichment with large factor."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[EnrichmentWorkflow],
        activities=[extract_data, enrich_data],
    ):
        result = await client.execute_workflow(
            EnrichmentWorkflow.run,
            args=["source", 1000],
            id=f"test-enrich-large-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result[0]["enriched"] == 1000


@pytest.mark.asyncio
async def test_etl_long_source_name():
    """Test ETL with long source name."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ETLWorkflow],
        activities=[extract_data, transform_data, load_data],
    ):
        long_source = "source-" + "x" * 100
        result = await client.execute_workflow(
            ETLWorkflow.run,
            args=[long_source, "double", "dest"],
            id=f"test-etl-long-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
        assert result["success"] is True


@pytest.mark.asyncio
async def test_validation_multiple_sources():
    """Test validation on multiple sources."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[ValidationWorkflow],
        activities=[extract_data, validate_data],
    ):
        result1 = await client.execute_workflow(
            ValidationWorkflow.run,
            "source1",
            id=f"test-val-1-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        result2 = await client.execute_workflow(
            ValidationWorkflow.run,
            "source2",
            id=f"test-val-2-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )

        assert result1 is True
        assert result2 is True
