import random
from curl_cffi.requests import AsyncSession
from fake_headers import Headers


class HeaderRotator:
    def __init__(self):
        self.browsers = [
            "chrome",
            "chrome_android",
            "edge",
            "safari",
            "safari_ios"
        ]

    def get_headers(self):
        return Headers(headers=True).generate()

    def get_browser(self):
        return random.choice(self.browsers)

    async def get(self, client: AsyncSession, url, method="GET", **kwargs):
        headers = self.get_headers()
        browser = self.get_browser()

        response = await client.request(
            method,
            url,
            headers=headers,
            impersonate=browser,
            timeout=30,
            **kwargs
        )

        return response

