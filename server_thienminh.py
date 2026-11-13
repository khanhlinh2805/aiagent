import os
import json
import uuid
from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from agents.thienminh_orchestrator import ThienMinhSalesOrchestrator
from agents.gemini_service import GeminiService
from agents.sheets_analytics_agent import SheetsAnalyticsAgent

def create_thienminh_app() -> FastAPI:
    app = FastAPI(title="Thiên Minh AI Agent — Data Analytics & B2B Solutions", version="2.0.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    orchestrator = ThienMinhSalesOrchestrator()
    gemini_svc = GeminiService()
    sheets_agent = SheetsAnalyticsAgent()

    # Tạo thư mục xuất file nếu chưa có
    os.makedirs("exports", exist_ok=True)

    # Đọc dữ liệu mẫu Sheets
    sheets_samples = []
    if os.path.exists("data/sheets_samples.json"):
        with open("data/sheets_samples.json", "r", encoding="utf-8") as f:
            sheets_samples = json.load(f)

    with open("data/thienminh_rfp_samples.json", "r", encoding="utf-8") as f:
        samples = json.load(f)

    with open("data/thienminh_solutions.json", "r", encoding="utf-8") as f:
        catalog = json.load(f)

    with open("data/thienminh_capacity_schedule.json", "r", encoding="utf-8") as f:
        schedule = json.load(f)

    with open("data/thienminh_policies.json", "r", encoding="utf-8") as f:
        policies = json.load(f)

    # Cache bộ nhớ tạm cho session hiện tại
    session_store = {
        "current_cleaned_data": None,
        "current_analysis": None
    }

    # =========================================================================
    # CÁC ENDPOINT CHO QUY TRÌNH SHEETS ANALYTICS CỦA KHÁCH HÀNG
    # =========================================================================

    @app.get("/api/sheets/samples")
    def get_sheets_samples():
        return sheets_samples

    @app.post("/api/sheets/validate")
    async def validate_sheets(request: Request):
        """
        Bước 1: Khách hàng gửi sheets dữ liệu.
        Nếu không phải sheets -> báo lỗi và yêu cầu gửi lại.
        """
        body = await request.json()
        filename = body.get("filename", "")
        url = body.get("url", "")
        validation = sheets_agent.validate_file_or_link(filename=filename, url=url)
        return JSONResponse(content=validation)

    @app.post("/api/sheets/clean")
    async def clean_sheets(request: Request):
        """
        Bước 2: Hệ thống làm sạch sheets.
        Nếu sheets chưa ổn -> báo lỗi và yêu cầu gửi lại.
        Nếu ổn -> trả về kết quả làm sạch và preview.
        """
        body = await request.json()
        raw_data = body.get("data", [])
        metadata = body.get("metadata", {})
        result = sheets_agent.clean_sheet_data(raw_data=raw_data, metadata=metadata)
        if result.get("is_clean_success"):
            session_store["current_cleaned_data"] = result.get("all_data", [])
        return JSONResponse(content=result)

    @app.post("/api/sheets/analyze")
    async def analyze_sheets(request: Request):
        """
        Bước 3: Phân tích data & gửi bản xác nhận.
        Nếu có feedback từ khách hàng -> phân tích lại theo feedback.
        """
        body = await request.json()
        cleaned_data = body.get("cleaned_data") or session_store.get("current_cleaned_data") or []
        feedback = body.get("feedback")
        result = sheets_agent.analyze_data(cleaned_data=cleaned_data, feedback=feedback)
        session_store["current_analysis"] = result
        return JSONResponse(content=result)

    @app.post("/api/sheets/confirm")
    async def confirm_analysis(request: Request):
        """
        Khách hàng xác nhận hoặc từ chối.
        """
        body = await request.json()
        confirmed = body.get("confirmed", True)
        feedback = body.get("feedback", "")
        if confirmed:
            return JSONResponse(content={
                "status": "CONFIRMED",
                "message": "✅ Khách hàng đã xác nhận phân tích ổn. Tiến hành mở khóa xuất Báo cáo và Dashboard!"
            })
        else:
            # Phân tích lại theo feedback
            cleaned_data = session_store.get("current_cleaned_data") or []
            new_analysis = sheets_agent.analyze_data(cleaned_data=cleaned_data, feedback=feedback)
            session_store["current_analysis"] = new_analysis
            return JSONResponse(content={
                "status": "RE_ANALYZED",
                "message": f"🔄 Đã ghi nhận phản hồi: '{feedback}'. Hệ thống đã hiệu chỉnh phân tích lại thành công!",
                "new_analysis": new_analysis
            })

    @app.get("/api/sheets/export/docx")
    def export_docx():
        """
        Bước 4: Xuất file báo cáo dạng .docx
        """
        analysis = session_store.get("current_analysis")
        if not analysis:
            # Phân tích mặc định nếu chưa chạy
            sample = sheets_samples[0]["data"]
            clean_res = sheets_agent.clean_sheet_data(sample)
            analysis = sheets_agent.analyze_data(clean_res["all_data"])

        file_id = str(uuid.uuid4())[:8]
        filepath = f"exports/Bao_Cao_Phan_Tich_Du_Lieu_{file_id}.docx"
        sheets_agent.generate_docx_report(analysis, filepath)
        return FileResponse(
            path=filepath,
            filename="Bao_Cao_Phan_Tich_Doanh_Nghiep.docx",
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        )

    @app.get("/api/sheets/export/html")
    def export_html():
        """
        Bước 4: Xuất Dashboard tương tác dạng HTML độc lập
        """
        analysis = session_store.get("current_analysis")
        if not analysis:
            sample = sheets_samples[0]["data"]
            clean_res = sheets_agent.clean_sheet_data(sample)
            analysis = sheets_agent.analyze_data(clean_res["all_data"])

        file_id = str(uuid.uuid4())[:8]
        filepath = f"exports/Dashboard_Tuong_Tac_{file_id}.html"
        sheets_agent.generate_html_dashboard(analysis, filepath)
        return FileResponse(
            path=filepath,
            filename="Dashboard_Doanh_Nghiep.html",
            media_type="text/html"
        )

    @app.post("/api/chatbot/message")
    async def chatbot_chat(request: Request):
        """
        Mục Chatbot hỗ trợ tương tác với khách hàng
        """
        body = await request.json()
        message = body.get("message", "")
        reply = sheets_agent.get_chatbot_reply(message, session_store)
        return JSONResponse(content={"reply": reply})

    # =========================================================================
    # CÁC ENDPOINT CŨ CHO HỆ THỐNG
    # =========================================================================

    @app.get("/api/gemini-status")
    def get_gemini_status():
        return {
            "is_active": gemini_svc.is_active,
            "primary_model": gemini_svc.primary_model,
            "fallback_model": gemini_svc.fallback_model,
            "provider": "Google AI Studio / Gemini API"
        }

    @app.get("/api/samples")
    def get_samples():
        return samples

    @app.get("/api/catalog")
    def get_catalog():
        return catalog

    @app.get("/api/schedule")
    def get_schedule():
        return schedule

    @app.get("/api/policies")
    def get_policies():
        return policies

    @app.post("/api/process")
    async def process_rfp(rfp_data: dict):
        try:
            result = orchestrator.process_rfp(rfp_data)
            return JSONResponse(content=result.model_dump())
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})

    @app.post("/api/hitl-action")
    async def hitl_action(action_data: dict):
        action = action_data.get("action")
        rfp_id = action_data.get("rfp_id")
        notes = action_data.get("notes", "")

        if action == "APPROVE_HITL":
            return JSONResponse(content={
                "status": "SUCCESS",
                "message": f"Hồ sơ {rfp_id} đã được Hội đồng liên bộ phận đồng thuận phê chuẩn ĐẠT ranh giới dữ liệu.",
                "action": "HITL_APPROVED"
            })
        elif action == "REQUEST_REVISION":
            return JSONResponse(content={
                "status": "REVISION_REQUESTED",
                "message": f"Hồ sơ {rfp_id} đã được gửi phản hồi yêu cầu điều chỉnh: '{notes}'. Luồng chuyển lại bước Trích xuất & Đối chiếu.",
                "action": "REVISION_LOOP"
            })
        elif action == "BOD_APPROVE":
            return JSONResponse(content={
                "status": "BOD_APPROVED",
                "message": f"Ban Giám Đốc đã phê duyệt tờ trình cho dự án {rfp_id}.",
                "action": "BOD_APPROVED"
            })
        return JSONResponse(content={"status": "UNKNOWN_ACTION"})

    @app.get("/", response_class=HTMLResponse)
    def index():
        with open("web/index_thienminh.html", "r", encoding="utf-8") as f:
            return f.read()

    return app
