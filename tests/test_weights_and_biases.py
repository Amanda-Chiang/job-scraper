from sources.custom import weights_and_biases

URL = "https://boards-api.greenhouse.io/v1/boards/coreweave/jobs?content=true"


def test_fetch_filters_to_wandb_acquisition_metadata_only(requests_mock):
    requests_mock.get(
        URL,
        json={
            "jobs": [
                {
                    "title": "Account Solution Architect",
                    "location": {"name": "Remote"},
                    "absolute_url": "https://job-boards.greenhouse.io/coreweave/jobs/1",
                    "metadata": [{"id": 1, "name": "Acquisition Company", "value": "Weights & Biases"}],
                },
                {
                    "title": "Account Executive - Greenfield",
                    "location": {"name": "Remote"},
                    "absolute_url": "https://job-boards.greenhouse.io/coreweave/jobs/2",
                    "metadata": [{"id": 1, "name": "Acquisition Company", "value": "CoreWeave"}],
                },
            ]
        },
    )
    postings = weights_and_biases.fetch()
    assert len(postings) == 1
    assert postings[0].company == "Weights & Biases"
    assert postings[0].title == "Account Solution Architect"
    assert postings[0].link == "https://job-boards.greenhouse.io/coreweave/jobs/1"
