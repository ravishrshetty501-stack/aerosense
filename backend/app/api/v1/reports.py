import re
from urllib.parse import quote
from fastapi import APIRouter, Depends, Query, Response, HTTPException
from app.core.rate_limit import report_limiter
from app.services.report_service import report_service
from app.services.providers.manager import data_manager

router = APIRouter(prefix="/reports", tags=["Environmental Reports"])

_MAX_SEGMENT_LENGTH = 48


def _sanitize_filename_segment(value: str, fallback: str, *, allow_unicode: bool) -> str:
    """Normalizes a dynamic value into a path-safe ASCII or Unicode filename segment."""
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", "", value or "")
    cleaned = re.sub(r"\.{2,}", "_", cleaned)
    pattern = r"[^\w.-]+" if allow_unicode else r"[^A-Za-z0-9._-]+"
    cleaned = re.sub(pattern, "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("._")
    if len(cleaned) > _MAX_SEGMENT_LENGTH:
        cleaned = cleaned[:_MAX_SEGMENT_LENGTH].rstrip("._")
    return cleaned or fallback


def build_pdf_content_disposition(city: str, period: str) -> str:
    """
    Constructs a strict Content-Disposition attachment header with an ASCII fallback filename
    and, when non-ASCII characters are present, an RFC 5987 UTF-8 encoded filename* parameter.
    """
    ascii_city = _sanitize_filename_segment(city, "Location", allow_unicode=False)
    ascii_period = _sanitize_filename_segment(period, "Report", allow_unicode=False)
    ascii_filename = f"AeroSense_{ascii_city}_{ascii_period}.pdf"

    unicode_city = _sanitize_filename_segment(city, "Location", allow_unicode=True)
    unicode_period = _sanitize_filename_segment(period, "Report", allow_unicode=True)
    unicode_filename = f"AeroSense_{unicode_city}_{unicode_period}.pdf"

    if unicode_filename != ascii_filename:
        encoded_utf8 = quote(unicode_filename, safe=".-_")
        return f'attachment; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded_utf8}'
    return f'attachment; filename="{ascii_filename}"'

@router.get("/data", dependencies=[Depends(report_limiter)])
async def get_report_data(
    city: str = Query("London"),
    period: str = Query("Daily Summary"),
    standard: str = Query("US_EPA")
):
    locs = await data_manager.search_cities(city)
    if not locs:
        raise HTTPException(status_code=404, detail=f"Location '{city}' not found.")
    t = locs[0]
    data = await report_service.generate_report_data(
        t["latitude"], t["longitude"], t["name"], period, standard
    )
    return data

@router.get("/export/pdf", dependencies=[Depends(report_limiter)])
async def export_pdf_report(
    city: str = Query("London"),
    period: str = Query("Daily Summary"),
    standard: str = Query("US_EPA")
):
    locs = await data_manager.search_cities(city)
    if not locs:
        raise HTTPException(status_code=404, detail=f"Location '{city}' not found.")
    t = locs[0]
    report_data = await report_service.generate_report_data(
        t["latitude"], t["longitude"], t["name"], period, standard
    )
    pdf_bytes = report_service.generate_pdf(report_data)

    resolved_city = t.get("name") or city
    content_disposition = build_pdf_content_disposition(resolved_city, period)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": content_disposition}
    )
