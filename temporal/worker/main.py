import asyncio
import random
import string

from temporalio.client import Client
from temporalio.worker import Worker

from activities.delete_response import delete_response
from activities.delete_user import delete_user
from activities.import_form import import_form
from activities.save_preview import save_preview
from settings.application import settings
from workflows.form_import_workflow import ImportFormWorkflow
from workflows.response_deletion_workflow import DeleteResponseWorkflow
from workflows.save_template_preview import SaveTemplatePreview
from workflows.user_deletion_workflow import DeleteUserWorkflow


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
        workflows=[DeleteUserWorkflow, ImportFormWorkflow, DeleteResponseWorkflow, SaveTemplatePreview],
        activities=[delete_user, import_form, delete_response, save_preview],
    )
    response = await worker.run()
    print(response)


async def main():
    workers = [run_worker() for i in range(0, settings.workers)]
    await asyncio.gather(*workers)


if __name__ == "__main__":
    asyncio.run(main())
