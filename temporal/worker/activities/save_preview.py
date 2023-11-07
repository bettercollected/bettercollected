
from temporalio import activity, workflow
from temporalio.exceptions import FailureError

from models.SavePreviewParams import SavePreviewParams
from settings.application import settings

with workflow.unsafe.imports_passed_through():
    from selenium import webdriver
    import requests
    from configs.crypto import crypto
    from io import BytesIO
    from models.user_tokens import UserTokens
    import json
    from asyncio import sleep


@activity.defn(name="save_preview")
async def save_preview(save_preview_params: SavePreviewParams):
    options = webdriver.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)
    driver.set_window_size(640, 620)
    decrypted_token = crypto.decrypt(save_preview_params.token)
    user_token = UserTokens(**json.loads(decrypted_token))
    auth_cookie = {"name": "Authorization", "value": user_token.access_token, "domain": settings.cookie_domain}
    driver.get(save_preview_params.template_url)
    driver.add_cookie(auth_cookie)
    driver.refresh()
    await sleep(20)

    screenshot = driver.get_screenshot_as_png()
    driver.close()
    image_file = BytesIO(screenshot)
    headers = {"api-key": settings.api_key}
    url = settings.server_url + f"/template/{save_preview_params.template_id}/preview"
    files = {"preview_image": ("preview_image.png", image_file, "image/png")}
    response = requests.patch(url, files=files, headers=headers)

    if response.status_code != 200:
        raise FailureError("Preview Image Patch not successful")
