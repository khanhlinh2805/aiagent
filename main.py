import os
import sys
import json
import argparse
from typing import Optional
from models.schemas import CustomerRequestInput, PipelineExecutionResult
from agents.orchestrator import MinhAnSalesOrchestrator

def print_banner():
    banner = """
================================================================================
   HỆ THỐNG AI AGENT XỬ LÝ CƠ HỘI BÁN HÀNG B2B - MINH AN COMPANY
   Tự động hóa luồng: Tiếp nhận -> Thẩm định -> Báo giá -> Duyệt -> Phản hồi
================================================================================
"""
    print(banner)

def format_currency(amount: float) -> str:
    return f"{amount:,.0f} VNĐ"

def display_result(result: PipelineExecutionResult):
    print("--------------------------------------------------------------------------------")
    print(f"📌 MÃ YÊU CẦU: {result.request_id} | TRẠNG THÁI CUỐI: {result.final_status}")
    print("--------------------------------------------------------------------------------")
    
    print("\n🔄 CÁC BƯỚC ĐÃ THỰC THI THEO SƠ ĐỒ QUY TRÌNH:")
    for step in result.workflow_steps:
        icon = "✅" if step["status"] == "COMPLETED" else ("🔀" if step["status"] == "BRANCH_TAKEN" else "⚠️")
        print(f"  {icon} [{step['step_name']}]: {step['details']}")

    # 1. Kiểm tra tính đầy đủ
    comp = result.completeness
    print("\n🔍 KẾT QUẢ KIỂM TRA THÔNG TIN (Intake Check):")
    print(f"  - Đủ thông tin tiêu chuẩn: {'CÓ' if comp.has_sufficient_info else 'KHÔNG (Cần làm rõ)'}")
    if not comp.has_sufficient_info:
        print(f"  - Các mục bị thiếu: {', '.join(comp.missing_items)}")
        print("  - Câu hỏi cần làm rõ gửi khách hàng:")
        for q in comp.clarification_questions:
            print(f"    * {q}")

    # 2. Hồ sơ cơ hội
    if result.opportunity_record:
        opp = result.opportunity_record
        print(f"\n📁 HỒ SƠ CƠ HỘI (CRM Card) [{opp.opp_id}]:")
        print(f"  - Khách hàng: {opp.customer_name} ({opp.customer_company})")
        print(f"  - Email: {opp.customer_email} | Người liên hệ: {opp.contact_person}")
        if opp.assigned_rep:
            print(f"  - NVKD phụ trách: {opp.assigned_rep.name} ({opp.assigned_rep.email})")
            print(f"  - Chuyên môn: {', '.join(opp.assigned_rep.specialty)}")
            print(f"  - Lý do phân bổ: {opp.assigned_rep.assignment_reason}")
        print(f"  - Trạng thái hiện tại: {opp.current_stage}")
        print(f"  - Cam kết SLA phản hồi: {opp.sla_response_hours} giờ làm việc")

    # 3. Báo giá & Tồn kho
    if result.quotation:
        q = result.quotation
        print(f"\n📊 BẢNG BÁO GIÁ CHI TIẾT [{q.quote_id}]:")
        print(f"  {'STT':<4} {'Mã SKU':<18} {'Tên sản phẩm / Dịch vụ':<38} {'SL':<4} {'Đơn giá':<14} {'CK':<6} {'Thành tiền':<16} {'Tồn kho / SLA'}")
        print("  " + "-" * 115)
        for idx, item in enumerate(q.items, 1):
            name_trunc = item.product_name[:35] + ".." if len(item.product_name) > 37 else item.product_name
            print(f"  {idx:<4} {item.sku:<18} {name_trunc:<38} {item.quantity:<4} {format_currency(item.unit_price_vnd):<14} {item.discount_pct:<6.1f} {format_currency(item.line_total_vnd):<16} {item.notes}")
        print("  " + "-" * 115)
        print(f"  Tổng trước chiết khấu : {format_currency(q.gross_subtotal_vnd)}")
        print(f"  Tổng tiền chiết khấu  : -{format_currency(q.total_discount_vnd)}")
        print(f"  Tiền sau chiết khấu   : {format_currency(q.net_before_vat_vnd)}")
        print(f"  Thuế VAT (10%)        : {format_currency(q.vat_amount_vnd)}")
        print(f"  👉 TỔNG CỘNG PHẢI THU : {format_currency(q.grand_total_vnd)}")
        print(f"  Đánh giá ngân sách    : {q.budget_comparison}")
        print(f"  Thời hạn cam kết      : {q.required_lead_time_days} ngày làm việc ({q.lead_time_status})")
        print(f"  Chi tiết tiến độ      : {q.lead_time_explanation}")

    # 4. Phê duyệt
    if result.approval:
        app = result.approval
        print(f"\n⚖️ THẨM ĐỊNH PHÊ DUYỆT (Approval Matrix):")
        if app.requires_manager_approval:
            print(f"  ⚠️ CẦN TRƯỞNG PHÒNG DUYỆT: {app.manager_name} ({app.manager_email})")
            for r in app.trigger_reasons:
                print(f"    - {r}")
        else:
            print("  ✅ TỰ ĐỘNG PHÊ DUYỆT (Trong hạn mức thẩm quyền của NVKD)")

    # 5. Bản nháp email gửi khách
    draft = result.response_draft
    print(f"\n✉️ BẢN NHÁP EMAIL PHẢN HỒI KHÁCH HÀNG ({draft.action_type}):")
    print(f"  Gửi tới : {draft.recipient_name} <{draft.recipient_email}>")
    print(f"  Đồng kính gửi (CC): {', '.join(draft.cc)}")
    print(f"  Tiêu đề : {draft.subject}")
    print("  Nội dung tóm tắt:")
    preview_lines = draft.body_markdown.split("\n")[:8]
    for line in preview_lines:
        print(f"    {line}")
    print("    ... [Xem toàn bộ nội dung trong giao diện Web / Output file] ...")
    print("================================================================================\n")

def run_demo():
    print_banner()
    orchestrator = MinhAnSalesOrchestrator()
    with open("data/sample_requests.json", "r", encoding="utf-8") as f:
        samples = json.load(f)

    print(f"Tìm thấy {len(samples)} kịch bản kiểm thử mô phỏng các vấn đề thực tế của Minh An Company:\n")
    for idx, sample in enumerate(samples, 1):
        print(f"[{idx}] {sample['title']}")

    print("\nBắt đầu chạy tuần tự quy trình AI Agent qua cả 5 kịch bản:\n")

    for idx, s in enumerate(samples, 1):
        req = CustomerRequestInput(
            id=s["id"],
            customer_name=s["customer_name"],
            customer_company=s["customer_company"],
            customer_email=s["customer_email"],
            received_date=s["received_date"],
            raw_text=s["raw_text"]
        )
        print(f"\n>>> ĐANG XỬ LÝ KỊCH BẢN {idx}: {s['title']}")
        result = orchestrator.process_request(req)
        display_result(result)

def start_server(port: int = 8000):
    import uvicorn
    from web.server import create_app
    app = create_app()
    print(f"\n🚀 Đang khởi động Minh An Sales AI Agent Web Dashboard tại: http://localhost:{port}")
    print(f"👉 Mở trình duyệt và truy cập: http://localhost:{port} để trải nghiệm giao diện trực quan.\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Minh An Sales AI Agent System")
    parser.add_argument("--demo", action="store_true", help="Chạy demo 5 kịch bản mẫu qua dòng lệnh")
    parser.add_argument("--serve", action="store_true", help="Chạy Web Dashboard")
    parser.add_argument("--port", type=int, default=8000, help="Cổng chạy Web Dashboard")
    args = parser.parse_args()

    if args.serve:
        start_server(args.port)
    elif args.demo:
        run_demo()
    else:
        # Mặc định chạy demo để xác thực
        run_demo()

