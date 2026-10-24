from app.core.config import settings
from app.routers import interpret as router_interpret
from app.schemas.interpret import RespuestaInterpretacion


def test_interpret_sin_api_key(client, monkeypatch) -> None:
    monkeypatch.setattr(settings, "palette_lab_api_key", "secreto")

    async def receta_falsa(prompt: str) -> RespuestaInterpretacion:
        return RespuestaInterpretacion(
            base="#b45309",
            mode="analogous",
            tone="muted",
            label="café cálido",
        )

    monkeypatch.setattr(router_interpret, "interpretar_palette", receta_falsa)

    res = client.post("/interpret", json={"prompt": "café artesanal"})
    assert res.status_code == 401

    res = client.post(
        "/interpret",
        json={"prompt": "café artesanal"},
        headers={"X-API-Key": "secreto"},
    )
    assert res.status_code == 200

    res = client.post(
        "/interpret",
        json={"prompt": "café artesanal"},
        headers={"X-API-Key": "incorrecta"},
    )
    assert res.status_code == 401
