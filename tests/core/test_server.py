"""Server health and cluster tests."""

import os
import uuid
import pytest
from temporalio.client import Client
from temporalio.api.workflowservice.v1 import (
    GetClusterInfoRequest,
    GetSystemInfoRequest,
    DescribeNamespaceRequest,
)

TEMPORAL_ADDRESS = os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")
TEST_NAMESPACE = os.environ.get("NAMESPACE", "temporal-mongodb")


@pytest.mark.asyncio
async def test_get_cluster_info():
    """Test cluster info retrieval."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace="temporal-system")
    resp = await client.workflow_service.get_cluster_info(GetClusterInfoRequest())
    assert resp.cluster_id is not None
    assert len(resp.cluster_id) > 0


@pytest.mark.asyncio
async def test_get_system_info():
    """Test system info retrieval."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace="temporal-system")
    resp = await client.workflow_service.get_system_info(GetSystemInfoRequest())
    assert resp.server_version is not None


@pytest.mark.asyncio
async def test_describe_namespace():
    """Test namespace description."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace="temporal-system")
    resp = await client.workflow_service.describe_namespace(
        DescribeNamespaceRequest(namespace=TEST_NAMESPACE)
    )
    assert resp.namespace_info.name == TEST_NAMESPACE
    assert resp.namespace_info.state == 1  # REGISTERED


@pytest.mark.asyncio
async def test_namespace_retention():
    """Test namespace retention period is set."""
    client = await Client.connect(TEMPORAL_ADDRESS, namespace="temporal-system")
    resp = await client.workflow_service.describe_namespace(
        DescribeNamespaceRequest(namespace=TEST_NAMESPACE)
    )
    # Retention should be set (1 day = 86400 seconds)
    assert resp.config.workflow_execution_retention_ttl.seconds > 0


@pytest.mark.asyncio
async def test_connect_with_different_namespace():
    """Test connecting with different namespaces."""
    # Connect to temporal-system
    client1 = await Client.connect(TEMPORAL_ADDRESS, namespace="temporal-system")
    assert client1.namespace == "temporal-system"

    # Connect to test namespace
    client2 = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
    assert client2.namespace == TEST_NAMESPACE


@pytest.mark.asyncio
async def test_multiple_connections():
    """Test multiple simultaneous connections."""
    clients = []
    for i in range(5):
        client = await Client.connect(TEMPORAL_ADDRESS, namespace=TEST_NAMESPACE)
        clients.append(client)

    # All clients should be connected
    for client in clients:
        assert client.namespace == TEST_NAMESPACE
