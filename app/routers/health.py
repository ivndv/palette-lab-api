from fastapi import APIRouter

router = APIRouter(tags=["salud"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Estado ultraligero: no toca la IA."""
    return {"status": "ok"}
