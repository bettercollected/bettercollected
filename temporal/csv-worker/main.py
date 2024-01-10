import asyncio
import random
import string

from temporalio.client import Client
from temporalio.worker import Worker

from activities.export_as_csv import export_as_csv
from settings.application import settings
from workflows.export_as_csv import ExportCSVWorkflow


def get_random_string(length=20):
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))


async def run_worker():
    client = await Client.connect(settings.temporal_server_url, namespace=settings.namespace)
    worker = Worker(
        client,
        identity=get_random_string(),
        task_queue=settings.worker_queue,
        workflows=[ExportCSVWorkflow],
        activities=[export_as_csv],
    )
    response = await worker.run()
    print(response)


async def main():
    workers = [run_worker() for i in range(0, settings.workers)]
    await asyncio.gather(*workers)


if __name__ == "__main__":
    asyncio.run(main())
