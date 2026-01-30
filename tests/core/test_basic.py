"""Basic connectivity test."""

import os
import pytest
from temporalio.client import Client
from temporalio.api.workflowservice.v1 import (
    ListNamespacesRequest,
    RegisterNamespaceRequest,
)
from temporalio.service import RPCError
from google.protobuf.duration_pb2 import Duration

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")


@pytest.mark.asyncio
async def test_connect_to_server():
    """Test basic connection to Temporal server."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace="temporal-system")
    assert client.namespace == "temporal-system"


@pytest.mark.asyncio
async def test_register_namespace():
    """Register test namespace."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace="temporal-system")
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


@pytest.mark.asyncio
async def test_list_namespaces():
    """List all namespaces."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace="temporal-system")
    resp = await client.workflow_service.list_namespaces(ListNamespacesRequest())
    names = [ns.namespace_info.name for ns in resp.namespaces]
    assert TEST_NAMESPACE in names
