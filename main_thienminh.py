import os
import sys
import json
import argparse
from typing import Dict, Any
from agents.thienminh_orchestrator import ThienMinhSalesOrchestrator
from models.thienminh_schemas import ThienMinhPipelineResult

def print_thienminh_banner():
    banner = """
================================================================================
   HỆ THỐNG AI AGENT ĐÁNH GIÁ YÊU CẦU CHÀO GIÁ DỰ ÁN - THIÊN MINH COMPANY
   Quy trình chuẩn hóa: Tiếp nhận -> Trích xuất -> Đối chiếu Kỹ thuật/Lịch
   -> Tính giá & Chiết khấu -> Ma trận Đáp ứng -> HITL Duyệt -> Phê duyệt
================================================================================
"""
    print(banner)

def format_currency(val: float) -> str:
    return f"{val:,.0f} VNĐ"

def display_thienminh_result(result: ThienMinhPipelineResult):
    print("--------------------------------------------------------------------------------")
    print(f"📋 MÃ DỰ ÁN: {result.rfp_id} | KHÁCH HÀNG: {result.customer_company}")
    print(f"📌 TRẠNG THÁI CUỐI: {result.current_status}")
    print("--------------------------------------------------------------------------------")

    print("\n🔄 CÁC BƯỚC ĐÃ THỰC THI THEO SƠ ĐỒ QUY TRÌNH:")
    for step in result.workflow_steps:
        icon = "✅" if step["status"] == "COMPLETED" else ("🔀" if step["status"] == "BRANCH_TAKEN" else ("⚠️" if step["status"] == "ESCALATED" else "ℹ️"))
        print(f"  {icon} [{step['step_name']}]: {step['details']}")

    # 1. Trích xuất & Điều kiện bắt buộc
    ext = result.extracted_rfp
    print("\n🔍 KẾT QUẢ PHÂN RÃ YÊU CẦU (RFP Decomposition):")
    print(f"  - Đủ thông tin chuẩn bị chào giá: {'CÓ (Tiếp tục)' if ext.has_sufficient_info else 'KHÔNG (Phải làm rõ trước)'}")
    if not ext.has_sufficient_info:
        print(f"  - Các trường còn thiếu: {', '.join(ext.missing_fields)}")
        print("  - Câu hỏi gửi khách hàng để làm rõ:")
        for q in ext.clarification_questions:
            print(f"    * {q}")
    else:
        print(f"  - Ngân sách trần: {format_currency(ext.budget_vnd) if ext.budget_vnd else 'Không nêu'}")
        print(f"  - Thời hạn yêu cầu: {ext.deadline_date or (f'{ext.deadline_days} ngày' if ext.deadline_days else 'Không nêu')}")
        print(f"  - Chiết khấu đề nghị: {ext.requested_discount_pct:.1f}%")
        print(f"  - Điều kiện kỹ thuật BẮT BUỘC nhận diện được ({len(ext.detected_mandatory_criteria)} tiêu chí):")
        for crit in ext.detected_mandatory_criteria:
            print(f"    * [{crit.code}] {crit.description}")
        if ext.out_of_catalog_items:
            print(f"  - ⚠️ CẢNH BÁO: Phát hiện {len(ext.out_of_catalog_items)} thiết bị NGOÀI DANH MỤC tiêu chuẩn:")
            for o in ext.out_of_catalog_items:
                print(f"    * {o['name']} (Dự toán chi phí: {format_currency(o.get('estimated_cost_vnd', 0))})")

    # 2. Đối chiếu giải pháp & Loại bỏ gói giá thấp thiếu tính năng
    if result.matched_solutions:
        print("\n⚙️ ĐỐI CHIẾU GIẢI PHÁP KỸ THUẬT (Spec Matching):")
        for s in result.matched_solutions:
            print(f"  👉 Chọn: {s.solution_name} ({s.matched_sku}) - SL: {s.quantity} {s.unit}")
            for r in s.reasons_for_selection:
                print(f"     + Điểm đạt: {r}")
            if s.rejected_cheaper_options:
                for rej in s.rejected_cheaper_options:
                    print(f"     ❌ ĐÃ LOẠI BỎ MÃ RẺ HƠN: {rej['sku']} - Lý do: {rej['reason']}")

    # 3. Năng lực & Lịch triển khai
    if result.deployment_feasibility:
        feas = result.deployment_feasibility
        status_icon = "🟢" if feas.status == "FEASIBLE" else ("🔴" if feas.status == "CONFLICT_BLACKOUT" else "🟡")
        print(f"\n📅 THẨM ĐỊNH NĂNG LỰC & LỊCH TRIỂN KHAI: {status_icon} [{feas.status}]")
        print(f"  - Phân tích: {feas.schedule_analysis}")
        print(f"  - Giải pháp: {feas.resolution_proposal}")

    # 4. Ma trận đáp ứng kỹ thuật (Compliance Matrix)
    if result.compliance_matrix:
        print(f"\n📋 MA TRẬN ĐÁP ỨNG KỸ THUẬT (Compliance Matrix - {len(result.compliance_matrix)} hạng mục):")
        print(f"  {'STT':<4} {'Yêu cầu RFP':<32} {'Giải pháp Thiên Minh':<34} {'Mức độ đáp ứng':<20} {'Ghi chú'}")
        print("  " + "-" * 115)
        for r in result.compliance_matrix:
            rfp_trunc = r.rfp_requirement[:30] + ".." if len(r.rfp_requirement) > 32 else r.rfp_requirement
            sol_trunc = r.offered_solution[:32] + ".." if len(r.offered_solution) > 34 else r.offered_solution
            notes_trunc = r.notes_and_evidence[:40] + ".." if len(r.notes_and_evidence) > 42 else r.notes_and_evidence
            print(f"  {r.stt:<4} {rfp_trunc:<32} {sol_trunc:<34} {r.compliance_status:<20} {notes_trunc}")
        print("  " + "-" * 115)

    # 5. Giá & Ngân sách
    if result.proposal_summary:
        prop = result.proposal_summary
        print(f"\n💰 DỰ TOÁN BÁO GIÁ [{prop.proposal_id}]:")
        print(f"  - Tổng niêm yết danh mục : {format_currency(prop.gross_subtotal_vnd)}")
        print(f"  - Chiết khấu dự án       : -{format_currency(prop.total_discount_vnd)}")
        if prop.out_of_catalog_items:
            o_sum = sum(it.get('estimated_cost_vnd', 0) for it in prop.out_of_catalog_items)
            print(f"  - Thiết bị ngoài danh mục : +{format_currency(o_sum)}")
        print(f"  - Tiền trước thuế VAT    : {format_currency(prop.net_before_vat_vnd)}")
        print(f"  - Thuế VAT (10%)         : {format_currency(prop.vat_amount_vnd)}")
        print(f"  👉 TỔNG CHÀO GIÁ CUỐI    : {format_currency(prop.grand_total_vnd)}")
        print(f"  - Đối chiếu ngân sách    : {prop.budget_analysis}")

    # 6. Kiểm tra ranh giới dữ liệu HITL & Phê duyệt
    if result.hitl_review:
        hitl = result.hitl_review
        print(f"\n👥 KIỂM TRA RANH GIỚI DỮ LIỆU HITL (Con người duyệt cuối):")
        print(f"  - Trạng thái thẩm định: {hitl.review_status}")
        for b in hitl.boundary_checks:
            p_icon = "✅" if b["passed"] else "⚠️"
            print(f"    {p_icon} [{b['department']}]: {b['notes']}")

    if result.approval_escalation:
        app = result.approval_escalation
        print(f"\n⚖️ THẨM QUYỀN PHÊ DUYỆT (Escalation Gate):")
        if app.requires_escalation:
            print(f"  ⚠️ CẦN PHÊ DUYỆT CẤP CAO: {app.approver_name} ({app.escalation_tier})")
            for r in app.escalation_reasons:
                print(f"    - {r}")
            print("\n  📄 TRÍCH YẾU TỜ TRÌNH LÃNH ĐẠO:")
            for l in app.executive_docket.split("\n"):
                print(f"    {l}")
        else:
            print(f"  ✅ TỰ ĐỘNG THÔNG QUA (Trong hạn mức thẩm quyền của NVKD)")

    print(f"\n✉️ BẢN NHÁP PHẢN HỒI ({result.final_output.action_type}):")
    print(f"  Gửi đến : {result.final_output.recipient}")
    print(f"  Tiêu đề : {result.final_output.subject}")
    lines = result.final_output.full_email_body_markdown.split("\n")[:6]
    for l in lines:
        print(f"    {l}")
    print("    ... [Xem toàn văn trong Web Dashboard / Export file] ...")
    print("================================================================================\n")

def run_thienminh_demo():
    print_thienminh_banner()
    orchestrator = ThienMinhSalesOrchestrator()
    with open("data/thienminh_rfp_samples.json", "r", encoding="utf-8") as f:
        rfp_list = json.load(f)

    print(f"Tìm thấy {len(rfp_list)} bộ hồ sơ RFP/RFQ kiểm thử toàn diện các vấn đề của Thiên Minh Company:\n")
    for idx, r in enumerate(rfp_list, 1):
        print(f"[{idx}] {r['title']}")

    print("\nBắt đầu chạy tuần tự quy trình AI Agent qua cả 4 kịch bản:\n")

    for idx, rfp in enumerate(rfp_list, 1):
        print(f"\n>>> ĐANG XỬ LÝ HỒ SƠ {idx}: {rfp['title']}")
        res = orchestrator.process_rfp(rfp)
        display_thienminh_result(res)

def start_thienminh_server(port: int = 8000):
    import uvicorn
    from web.server_thienminh import create_thienminh_app
    app = create_thienminh_app()
    print(f"\n🚀 Đang khởi động Thiên Minh Sales AI Agent Web Dashboard tại: http://localhost:{port}")
    print(f"👉 Mở trình duyệt và truy cập: http://localhost:{port} để trải nghiệm giao diện trực quan.\n")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Thiên Minh Company Sales AI Agent Runner")
    parser.add_argument("--demo", action="store_true", help="Chạy demo 4 kịch bản kiểm thử dòng lệnh")
    parser.add_argument("--serve", action="store_true", help="Chạy Web Dashboard trực quan")
    parser.add_argument("--port", type=int, default=8000, help="Cổng chạy Web server")
    args = parser.parse_args()

    if args.serve:
        start_thienminh_server(args.port)
    elif args.demo:
        run_thienminh_demo()
    else:
        run_thienminh_demo()
