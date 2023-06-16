import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from activities.delete_user import delete_user
from workflows.user_deletion_workflow import DeleteUserWorkflow


async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="delete_user",
        workflows=[DeleteUserWorkflow],
        activities=[delete_user],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
