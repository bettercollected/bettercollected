import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from activities.delete_user import delete_user
from activities.import_form import import_form
from settings.application import settings
from workflows.form_import_workflow import ImportFormWorkflow
from workflows.user_deletion_workflow import DeleteUserWorkflow


async def main():
    client = await Client.connect(settings.temporal_server_url, namespace=settings.namespace)
    worker = Worker(
        client,
        task_queue=settings.worker_queue,
        workflows=[DeleteUserWorkflow, ImportFormWorkflow],
        activities=[delete_user, import_form],
    )
    await worker.run()
    exit()


if __name__ == "__main__":
    asyncio.run(main())
