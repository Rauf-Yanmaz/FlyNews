from scripts.write_preview_report import write_report


def test_summary_and_artifact_redact_secrets_and_escape_untrusted_html(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret-value")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "telegram-secret-value")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "@private_destination")
    output = tmp_path / "preview.txt"
    summary = tmp_path / "summary.md"
    output.write_text(
        '<script>alert("x")</script> & news\n'
        "gemini-secret-value telegram-secret-value @private_destination",
        encoding="utf-8",
    )
    write_report(output, summary, "success")
    for content in (output.read_text(), summary.read_text()):
        assert "gemini-secret-value" not in content
        assert "telegram-secret-value" not in content
        assert "@private_destination" not in content
        assert "[REDACTED]" in content
    assert "<script>" not in summary.read_text()
    assert "&lt;script&gt;" in summary.read_text()
    assert "Başarılı" in summary.read_text()


def test_failed_run_is_not_reported_as_success_and_prior_summary_is_preserved(tmp_path):
    output = tmp_path / "preview.txt"
    summary = tmp_path / "summary.md"
    output.write_text("ERROR No valid analysis", encoding="utf-8")
    summary.write_text("Earlier report\n", encoding="utf-8")
    write_report(output, summary, "failure")
    assert summary.read_text().startswith("Earlier report")
    assert "Başarısız" in summary.read_text()
    assert "ERROR No valid analysis" in summary.read_text()


def test_missing_output_is_explicit(tmp_path):
    output = tmp_path / "preview.txt"
    summary = tmp_path / "summary.md"
    write_report(output, summary, "cancelled")
    assert "Çıktı dosyası oluşmadı" in summary.read_text()
    assert "Tamamlanamadı" in summary.read_text()
