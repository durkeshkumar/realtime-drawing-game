
from fastapi import APIRouter, HTTPException, status

router = APIRouter(
    prefix="/auth",
    tags=["Authentication"],
)


@router.post("/token")
def issue_player_token():
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "This token endpoint is disabled. "
            "Join a room to receive your player access token."
        ),
    )
