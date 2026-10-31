from unittest.mock import MagicMock

import main


def test_main_starts_uvicorn(monkeypatch) -> None:
    run = MagicMock()
    monkeypatch.setattr(main.uvicorn, "run", run)
    monkeypatch.setenv("API_HOST", "0.0.0.0")
    monkeypatch.setenv("API_PORT", "9000")

    main.main()

    run.assert_called_once_with(
        "main:app", host="0.0.0.0", port=9000, reload=False
    )
