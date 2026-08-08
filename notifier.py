import time

import requests

from models import Posting

RETRY_DELAYS = (2, 5)


def send_text(topic_url: str, message: str) -> None:
    for attempt, delay in enumerate((0, *RETRY_DELAYS)):
        if delay:
            time.sleep(delay)
        try:
            response = requests.post(topic_url, data=message.encode("utf-8"), timeout=15)
            response.raise_for_status()
            return
        except requests.exceptions.ConnectionError:
            if attempt == len(RETRY_DELAYS):
                raise


def send_posting(topic_url: str, posting: Posting) -> None:
    message = f"{posting.company}: {posting.title} ({posting.location})\n{posting.link}"
    send_text(topic_url, message)
