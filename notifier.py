import requests

from models import Posting


def send_text(topic_url: str, message: str) -> None:
    response = requests.post(topic_url, data=message.encode("utf-8"), timeout=15)
    response.raise_for_status()


def send_posting(topic_url: str, posting: Posting) -> None:
    message = f"{posting.company}: {posting.title} ({posting.location})\n{posting.link}"
    send_text(topic_url, message)
