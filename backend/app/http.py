import httpx

TRANSPORT = None  # tests replace this with httpx.MockTransport so no real network call is made


def client() -> httpx.Client:
    return httpx.Client(timeout=20.0, transport=TRANSPORT)
