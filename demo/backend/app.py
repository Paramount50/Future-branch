"""FastAPI-style profile endpoint used by the Future Branch demo."""

from dataclasses import dataclass

class MockApp:
    def get(self, *args, **kwargs):
        return lambda f: f

app = MockApp()



@dataclass
class UserResponse:
    username: str
    email: str
    credits: int


def get_profile() -> UserResponse:
    return UserResponse(username="ada", email="ada@example.com", credits=42)


@app.get("/api/profile", response_model=UserResponse)
def profile() -> UserResponse:
    return get_profile()
