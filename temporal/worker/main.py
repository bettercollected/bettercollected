import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from activities.delete_user import delete_user
from settings.application import settings
from workflows.user_deletion_workflow import DeleteUserWorkflow


async def main():
    client = await Client.connect(settings.temporal_server_url, namespace=settings.namespace)
    worker = Worker(
        client,
        task_queue="delete_user",
        workflows=[DeleteUserWorkflow],
        activities=[delete_user],
    )
    await worker.run()
    exit()


if __name__ == "__main__":
    asyncio.run(main())
