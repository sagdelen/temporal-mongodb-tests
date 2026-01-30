"""Pytest configuration for E2E tests."""

import asyncio
import os
import time

from google.protobuf.duration_pb2 import Duration
from temporalio.api.workflowservice.v1 import (
    ListNamespacesRequest,
    RegisterNamespaceRequest,
)
from temporalio.client import Client
from temporalio.service import RPCError

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")


def pytest_configure(config):
    """Ensure namespace exists before any tests run."""

    async def _setup():
        client = await Client.connect(TEMPORAL_ADDRESS, namespace="temporal-system")

        # Check if namespace exists
        resp = await client.workflow_service.list_namespaces(ListNamespacesRequest())
        names = [ns.namespace_info.name for ns in resp.namespaces]

        if TEST_NAMESPACE not in names:
            try:
                await client.workflow_service.register_namespace(
                    RegisterNamespaceRequest(
                        namespace=TEST_NAMESPACE,
                        workflow_execution_retention_period=Duration(seconds=86400),
                    )
                )
            except RPCError as e:
                if "already exists" not in str(e).lower():
                    raise

            # Wait for namespace to be ready
            for _ in range(30):
                try:
                    test_client = await Client.connect(
                        TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE
                    )
                    # Namespace is ready
                    return
                except Exception:
                    time.sleep(1)

    asyncio.run(_setup())
