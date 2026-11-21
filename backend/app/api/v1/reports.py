from fastapi import APIRouter, Query, Response, HTTPException
from app.services.report_service import report_service
from app.services.providers.manager import data_manager

router = APIRouter(prefix="/reports", tags=["Environmental Reports"])

@router.get("/data")
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

@router.get("/export/pdf")
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
    
    filename = f"AeroSense_{city.replace(' ', '_')}_{period.replace(' ', '_')}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
