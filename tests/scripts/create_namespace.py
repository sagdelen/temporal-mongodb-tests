"""Create namespaces for testing."""

import asyncio
from temporalio.client import Client
from temporalio.api.workflowservice.v1 import RegisterNamespaceRequest
from google.protobuf.duration_pb2 import Duration

NAMESPACES = ["temporal-mongodb"]


async def main():
    client = await Client.connect("localhost:7233")
    retention = Duration(seconds=86400)  # 1 day

    for ns in NAMESPACES:
        try:
            await client.workflow_service.register_namespace(
                RegisterNamespaceRequest(
                    namespace=ns,
                    workflow_execution_retention_period=retention,
                )
            )
            print(f"✓ Created namespace: {ns}")
        except Exception as e:
            if "already" in str(e).lower():
                print(f"✓ Namespace {ns} already exists")
            else:
                print(f"⚠ Error creating {ns}: {e}")


if __name__ == "__main__":
    asyncio.run(main())
