import json
from io import BytesIO
from time import sleep

from selenium import webdriver

from configs.crypto import crypto
from models.save_preview_params import SavePreviewParams
from models.user_tokens import UserTokens
from settings.application import settings


def get_preview_image(save_preview_params: SavePreviewParams):
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
    sleep(20)
    screenshot = driver.get_screenshot_as_png()
    driver.close()
    return BytesIO(screenshot)
