import re

from app.integrations import dashboard_pdf, telegram_gateway


def sample_document():
    return {
        "wallet_names": ["Cafetería"],
        "start": "2026-11-01",
        "end": "2026-11-02",
        "income": "500.00",
        "expense": "80.00",
        "net": "420.00",
        "days": [
            {"day": "2026-11-01", "income": "300.00", "expense": "0.00"},
            {"day": "2026-11-02", "income": "200.00", "expense": "80.00"},
        ],
        "media": {
            "CASH": {"income": "200.00", "expense": "80.00"},
            "DIGITAL": {"income": "300.00", "expense": "0.00"},
        },
        "declared_digital": "300.00",
        "environment": "DEMO",
        "empty": False,
    }


def test_pdf_is_a_real_vector_document_and_has_no_public_url():
    content = dashboard_pdf.render(sample_document())
    assert content.startswith(b"%PDF-")
    assert b"/Type /Page" in content and content.rstrip().endswith(b"%%EOF")
    assert b"/URI" not in content


def test_empty_pdf_and_negative_result_render():
    doc = sample_document()
    doc.update(income="0.00", expense="80.00", net="-80.00", empty=True)
    assert dashboard_pdf.render(doc).startswith(b"%PDF-")


def test_pdf_has_overview_and_one_page_per_wallet():
    business = sample_document()
    personal = {
        **sample_document(),
        "wallet_names": ["Principal"],
        "income": "0.00",
        "expense": "0.00",
        "net": "0.00",
        "empty": True,
        "includes_personal": True,
    }
    document = {
        **business,
        "wallet_names": ["Cafetería", "Principal"],
        "section_title": "Resumen general",
        "wallet_reports": [business, personal],
    }
    content = dashboard_pdf.render(document)
    assert len(re.findall(rb"/Type\s*/Page\b", content)) == 3
    assert len(re.findall(rb"/Type\s*/Page\b", dashboard_pdf.render(business))) == 1


def test_telegram_document_is_private_multipart(monkeypatch):
    calls = []
    monkeypatch.setattr(telegram_gateway, "is_live", lambda: True)

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True, "result": {"message_id": 27}}

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return Response()

    monkeypatch.setattr(telegram_gateway.httpx, "post", post)
    result = telegram_gateway.send_document("123", b"%PDF-test", "Mica.pdf", "Tu PDF")
    assert result.provider_sid == "TG123:27"
    url, payload = calls[0]
    assert url.endswith("/sendDocument")
    assert payload["data"]["chat_id"] == "123"
    assert payload["files"]["document"] == ("Mica.pdf", b"%PDF-test", "application/pdf")
