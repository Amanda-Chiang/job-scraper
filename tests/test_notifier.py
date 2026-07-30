from models import Posting
import notifier


def test_send_text_posts_message_to_topic_url(requests_mock):
    requests_mock.post("https://ntfy.sh/my-topic")
    notifier.send_text("https://ntfy.sh/my-topic", "hello world")
    assert requests_mock.last_request.body == b"hello world"


def test_send_posting_formats_company_title_location_link(requests_mock):
    requests_mock.post("https://ntfy.sh/my-topic")
    posting = Posting(
        company="Acme", title="Software Engineer Intern", location="NYC",
        link="https://acme.com/jobs/1", is_internship=True,
    )
    notifier.send_posting("https://ntfy.sh/my-topic", posting)
    body = requests_mock.last_request.body.decode("utf-8")
    assert "Acme: Software Engineer Intern (NYC)" in body
    assert "https://acme.com/jobs/1" in body
