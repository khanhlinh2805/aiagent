import json
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from models.schemas import CustomerRequestInput
from agents.orchestrator import MinhAnSalesOrchestrator

def create_app() -> FastAPI:
    app = FastAPI(title="Minh An Sales AI Agent System", version="1.0.0")
    orchestrator = MinhAnSalesOrchestrator()

    with open("data/sample_requests.json", "r", encoding="utf-8") as f:
        sample_requests = json.load(f)

    with open("data/sales_team.json", "r", encoding="utf-8") as f:
        sales_team = json.load(f)

    with open("data/products_catalog.json", "r", encoding="utf-8") as f:
        catalog = json.load(f)

    @app.get("/api/samples")
    def get_samples():
        return sample_requests

    @app.get("/api/team")
    def get_team():
        return sales_team

    @app.get("/api/catalog")
    def get_catalog():
        return catalog

    @app.post("/api/process")
    async def process_request(req_data: dict):
        try:
            req_input = CustomerRequestInput(
                id=req_data.get("id", "REQ-CUSTOM"),
                customer_name=req_data.get("customer_name", "Khách hàng Doanh nghiệp"),
                customer_company=req_data.get("customer_company", "Công ty Đối tác"),
                customer_email=req_data.get("customer_email", "contact@doitac.com"),
                received_date=req_data.get("received_date", "2026-11-11"),
                raw_text=req_data.get("raw_text", "")
            )
            result = orchestrator.process_request(req_input)
            return JSONResponse(content=result.model_dump())
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})

    @app.get("/", response_class=HTMLResponse)
    def index():
        with open("web/index.html", "r", encoding="utf-8") as f:
            return f.read()

    return app

