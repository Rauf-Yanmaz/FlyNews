"""Publish a readable Actions summary without relying on the job-log viewer."""

import os
from html import escape
from pathlib import Path


def write_report(output_path: Path, summary_path: Path, outcome: str) -> None:
    output = output_path.read_text(encoding="utf-8") if output_path.exists() else ""
    # Artifact files are not automatically secret-masked by GitHub, unlike console logs.
    for name in ("GEMINI_API_KEY", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"):
        secret = os.environ.get(name, "")
        if secret:
            output = output.replace(secret, "[REDACTED]")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(output, encoding="utf-8")
    status = {"success": "Başarılı", "failure": "Başarısız"}.get(outcome, "Tamamlanamadı")
    preview = output[:100_000] or "Çıktı dosyası oluşmadı. Çalışma tamamlanmadan kesilmiş olabilir."
    truncated = (
        "\n\nTam çıktı digest-preview artifact dosyasında bulunuyor."
        if len(output) > 100_000
        else ""
    )
    with summary_path.open("a", encoding="utf-8") as summary:
        summary.write(
            "## FlyNews deneme çıktısı\n\n"
            f"Sonuç: **{status}**. Bu deneme Telegram'a mesaj göndermez.\n\n"
            "Haber metinleri ve çalışma kayıtları aşağıdadır. Telegram HTML etiketleri "
            "önizlemede metin olarak gösterilir.\n\n"
            f"<pre>{escape(preview)}</pre>{truncated}\n"
        )


if __name__ == "__main__":
    write_report(
        Path("data/digest-preview.txt"),
        Path(os.environ["GITHUB_STEP_SUMMARY"]),
        os.environ.get("RUN_OUTCOME", "failure"),
    )
