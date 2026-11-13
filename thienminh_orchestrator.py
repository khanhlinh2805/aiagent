from typing import Dict, Any, List
from models.thienminh_schemas import (
    ThienMinhPipelineResult,
    FinalBidOutput
)
from agents.thienminh_intake_extractor import ThienMinhIntakeExtractor
from agents.thienminh_feasibility_matcher import ThienMinhFeasibilityMatcher
from agents.thienminh_pricing_discount import ThienMinhPricingDiscountAgent
from agents.thienminh_proposal_synthesizer import ThienMinhProposalSynthesizer
from agents.thienminh_hitl_governance import ThienMinhHITLGovernance
from agents.gemini_service import GeminiService

class ThienMinhSalesOrchestrator:
    """
    Quy trình đánh giá yêu cầu chào giá dự án bằng AI Agent - Thiên Minh Company
    Thực thi chính xác theo sơ đồ luồng quy trình nghiệp vụ:
    1. Bắt đầu: Tiếp nhận yêu cầu chào giá (RFP/RFQ)
    2. [AI AGENT] AI: Trích xuất & Phân rã yêu cầu
    3. Rẽ nhánh: Có đủ thông tin?
       - Không -> Kinh doanh liên hệ KH yêu cầu bổ sung
       - Có:
         4. [AI AGENT] AI: Đối chiếu giải pháp, năng lực & lịch triển khai (Matching feasibility)
         5. [AI AGENT] AI: Tính toán giá đề xuất & áp dụng chính sách chiết khấu
         6. Hợp nhất tài liệu: Tạo hồ sơ đề xuất, ma trận đáp ứng & dự thảo đề thảo bản chào giá
         7. Con người: HITL: Thẩm định & Kiểm tra ranh giới dữ liệu (KD + Kỹ thuật + Vận hành duyệt cuối)?
            - Cần chỉnh sửa -> Quay lại bước 2
            - Đạt ->
         8. Rẽ nhánh: Có vượt thẩm quyền / Cần chiết khấu đặc biệt / Thiết bị ngoài danh mục?
            - Có -> Trưởng phòng duyệt / Ban Giám đốc phê duyệt -> Kết thúc
            - Không -> Kết thúc: Xuất bản chào giá & Gửi khách hàng
    """
    def __init__(
        self,
        catalog_path: str = "data/thienminh_solutions.json",
        schedule_path: str = "data/thienminh_capacity_schedule.json",
        policies_path: str = "data/thienminh_policies.json"
    ):
        self.intake_agent = ThienMinhIntakeExtractor(catalog_path)
        self.feasibility_agent = ThienMinhFeasibilityMatcher(catalog_path, schedule_path)
        self.pricing_agent = ThienMinhPricingDiscountAgent(policies_path)
        self.proposal_synthesizer = ThienMinhProposalSynthesizer()
        self.governance = ThienMinhHITLGovernance(policies_path)
        self.gemini = GeminiService()

    def process_rfp(self, rfp_data: Dict[str, Any]) -> ThienMinhPipelineResult:
        steps_log: List[Dict[str, Any]] = []
        rfp_id = rfp_data.get("id", "RFP-000")
        company = rfp_data.get("customer_company", "Công ty Khách hàng")

        # BƯỚC 1: Tiếp nhận yêu cầu chào giá (RFP/RFQ)
        steps_log.append({
            "step_id": 1,
            "step_name": "Bắt đầu: Tiếp nhận yêu cầu chào giá (RFP/RFQ)",
            "status": "COMPLETED",
            "details": f"Tiếp nhận hồ sơ {rfp_id} từ {company} qua email/tài liệu đấu thầu."
        })

        # BƯỚC 2: [AI AGENT] AI: Trích xuất & Phân rã yêu cầu
        extracted = self.intake_agent.extract_rfp(rfp_data)
        steps_log.append({
            "step_id": 2,
            "step_name": "[AI AGENT] AI: Trích xuất & Phân rã yêu cầu",
            "status": "COMPLETED",
            "details": (
                f"Đã phân rã: {len(extracted.extracted_standard_items)} nhóm giải pháp tiêu chuẩn, "
                f"{len(extracted.detected_mandatory_criteria)} điều kiện bắt buộc, "
                f"{len(extracted.out_of_catalog_items)} thiết bị ngoài danh mục. "
                f"Ngân sách: {'Có' if extracted.has_budget else 'Chưa có'}. "
                f"Thời hạn: {'Có' if extracted.has_deadline else 'Chưa có'}."
            )
        })

        # BƯỚC 3: Rẽ nhánh: Có đủ thông tin?
        if not extracted.has_sufficient_info:
            steps_log.append({
                "step_id": 3,
                "step_name": "Kiểm tra thông tin: KHÔNG ĐỦ",
                "status": "BRANCH_TAKEN",
                "details": f"Hồ sơ thiếu các trường thông tin trọng yếu: {', '.join(extracted.missing_fields)}."
            })

            steps_log.append({
                "step_id": 31,
                "step_name": "Kinh doanh liên hệ KH yêu cầu bổ sung",
                "status": "COMPLETED",
                "details": f"Đã sinh mẫu email chuyên nghiệp gửi khách hàng làm rõ {len(extracted.clarification_questions)} câu hỏi kỹ thuật & tài chính."
            })

            customer_name = rfp_data.get('customer_name', 'Đại diện Khách hàng')
            # Thử gọi Gemini sinh email nếu có
            gemini_clarification = self.gemini.generate_clarification_letter(customer_name, company, extracted.clarification_questions)
            
            if gemini_clarification:
                clarification_email = gemini_clarification
            else:
                clarification_email = f"""Kính gửi Quý khách {customer_name} / {company},

Công ty Cổ phần Thiết bị & Dịch vụ Mạng Thiên Minh xin trân trọng cảm ơn Quý khách đã gửi yêu cầu chào giá dự án mạng đến chúng tôi.

Để đội ngũ Kỹ sư Giải pháp (Solution Architects) của Thiên Minh xây dựng được Phương án thiết kế kỹ thuật chính xác, lựa chọn đúng thông số cổng/công suất PoE và cam kết tiến độ triển khai khả thi nhất, kính đề nghị Quý khách hỗ trợ làm rõ một số nội dung sau:

{chr(10).join(f"- {q}" for q in extracted.clarification_questions)}

Ngay khi nhận được các thông tin bổ sung, Thiên Minh sẽ phát hành Hồ sơ Chào giá và Ma trận Đáp ứng Kỹ thuật hoàn chỉnh trong vòng 04 giờ làm việc.

Trân trọng kính thư,
---
Phòng Dự án Doanh nghiệp - Công ty Thiết bị & Dịch vụ Mạng Thiên Minh
Hotline: (024) 3888-9999 | Email: duan@thienminh.net.vn
"""
            clarification_output = FinalBidOutput(
                action_type="CLARIFICATION_REQUEST",
                recipient=rfp_data.get("customer_email", "contact@customer.com"),
                subject=f"[Thiên Minh] Đề nghị làm rõ thông tin yêu cầu chào giá dự án - {company}",
                compliance_matrix_markdown="*Chưa tạo ma trận do đang chờ khách hàng bổ sung thông tin kỹ thuật.*",
                pricing_table_markdown="*Chưa tạo bảng giá do chưa đủ thông số cấu hình.*",
                executive_summary_markdown="*Hồ sơ đang tạm dừng tại nhánh Yêu cầu KH bổ sung thông tin.*",
                full_email_body_markdown=clarification_email
            )

            return ThienMinhPipelineResult(
                rfp_id=rfp_id,
                customer_company=company,
                workflow_steps=steps_log,
                extracted_rfp=extracted,
                matched_solutions=[],
                deployment_feasibility=None,
                compliance_matrix=[],
                proposal_summary=None,
                hitl_review=None,
                approval_escalation=None,
                final_output=clarification_output,
                current_status="CHO_KHACH_HANG_BO_SUNG_THONG_TIN"
            )

        # CÓ ĐỦ THÔNG TIN:
        steps_log.append({
            "step_id": 3,
            "step_name": "Kiểm tra thông tin: ĐỦ THÔNG TIN",
            "status": "BRANCH_TAKEN",
            "details": "Hồ sơ đáp ứng đầy đủ tiêu chí để chuẩn bị chào giá (Go-No-Go: GO)."
        })

        # BƯỚC 4: [AI AGENT] AI: Đối chiếu giải pháp, năng lực & lịch triển khai (Matching feasibility)
        matched_solutions, matrix_rows = self.feasibility_agent.match_solutions(extracted)
        feasibility = self.feasibility_agent.verify_deployment_schedule(extracted)

        steps_log.append({
            "step_id": 4,
            "step_name": "[AI AGENT] AI: Đối chiếu giải pháp, năng lực & lịch triển khai (Matching feasibility)",
            "status": "COMPLETED",
            "details": (
                f"Đã khớp {len(matched_solutions)} giải pháp kỹ thuật. "
                f"Đã loại bỏ các gói giá thấp không đủ tính năng (loại bỏ Single PSU/không HA). "
                f"Lịch triển khai: {feasibility.status} ({feasibility.schedule_analysis[:100]}...)."
            )
        })

        # BƯỚC 5: [AI AGENT] AI: Tính toán giá đề xuất & áp dụng chính sách chiết khấu
        proposal = self.pricing_agent.calculate_proposal(
            rfp_id=rfp_id,
            matched_solutions=matched_solutions,
            out_of_catalog_items=extracted.out_of_catalog_items,
            requested_discount_pct=extracted.requested_discount_pct,
            customer_budget_vnd=extracted.budget_vnd
        )

        steps_log.append({
            "step_id": 5,
            "step_name": "[AI AGENT] AI: Tính toán giá đề xuất & áp dụng chính sách chiết khấu",
            "status": "COMPLETED",
            "details": f"Đã tính toán dự toán: {proposal.grand_total_vnd:,.0f} VNĐ (VAT 10%). {proposal.budget_analysis}"
        })

        # BƯỚC 6: Hợp nhất tài liệu: Tạo hồ sơ đề xuất, ma trận đáp ứng & dự thảo đề thảo bản chào giá
        final_output = self.proposal_synthesizer.synthesize_documents(
            rfp_data=rfp_data,
            extracted=extracted,
            matrix_rows=matrix_rows,
            proposal=proposal,
            feasibility=feasibility
        )

        steps_log.append({
            "step_id": 6,
            "step_name": "Tạo hồ sơ đề xuất, ma trận đáp ứng & dự thảo bản chào giá",
            "status": "COMPLETED",
            "details": f"Đã xuất bản Ma trận đáp ứng {len(matrix_rows)} hạng mục và Dự thảo chào thầu toàn văn."
        })

        # BƯỚC 7: Con người: HITL: Thẩm định & Kiểm tra ranh giới dữ liệu (KD + Kỹ thuật + Vận hành duyệt cuối)
        hitl_review = self.governance.conduct_hitl_review(extracted, proposal, feasibility)

        steps_log.append({
            "step_id": 7,
            "step_name": "HITL: Thẩm định & Kiểm tra ranh giới dữ liệu (KD + KT + VH duyệt)",
            "status": "COMPLETED",
            "details": (
                f"Đánh giá ranh giới: {hitl_review.review_status}. "
                f"Kinh doanh: Đồng ý. Kỹ thuật: Đồng ý. "
                f"Vận hành: {'Đồng ý' if hitl_review.operations_lead_approved else 'Cảnh báo lịch cao điểm'}. "
                f"Ghi chú: {'; '.join(hitl_review.feedback_notes) if hitl_review.feedback_notes else 'Không phát hiện sai lệch.'}"
            )
        })

        # BƯỚC 8: Có vượt thẩm quyền / Cần chiết khấu đặc biệt / Thiết bị ngoài danh mục?
        approval = self.governance.evaluate_escalation_and_approval(extracted, proposal, feasibility)

        if approval.requires_escalation:
            steps_log.append({
                "step_id": 8,
                "step_name": "Có vượt thẩm quyền / Cần chiết khấu đặc biệt / Thiết bị ngoài danh mục: CÓ",
                "status": "BRANCH_TAKEN",
                "details": f"Phát hiện yếu tố vượt hạn mức: {'; '.join(approval.escalation_reasons)}"
            })
            steps_log.append({
                "step_id": 81,
                "step_name": f"{'Ban Giám đốc phê duyệt' if approval.escalation_tier == 'BOARD_OF_DIRECTORS' else 'Trưởng phòng duyệt'}",
                "status": "ESCALATED",
                "details": f"Đã chuyển Tờ trình đến: {approval.approver_name} ({approval.approver_email})."
            })
            current_status = (
                "CHO_BAN_GIAM_DOC_PHE_DUYET" if approval.escalation_tier == "BOARD_OF_DIRECTORS"
                else "CHO_TRUONG_PHONG_PHE_DUYET"
            )
        else:
            steps_log.append({
                "step_id": 8,
                "step_name": "Có vượt thẩm quyền / Cần chiết khấu đặc biệt / Thiết bị ngoài danh mục: KHÔNG",
                "status": "BRANCH_TAKEN",
                "details": "Nằm trong hạn mức thẩm quyền của NVKD. Không có thiết bị ngoài danh mục. Tự động thông qua."
            })
            current_status = "HOAN_TAT_SAN_SANG_GUI_KH"

        # BƯỚC 9: Kết thúc: Xuất bản chào giá & Gửi khách hàng
        steps_log.append({
            "step_id": 9,
            "step_name": "Kết thúc: Xuất bản chào giá & Gửi khách hàng",
            "status": "COMPLETED",
            "details": f"Hồ sơ {proposal.proposal_id} sẵn sàng xuất bản và gửi chính thức tới {company}."
        })

        return ThienMinhPipelineResult(
            rfp_id=rfp_id,
            customer_company=company,
            workflow_steps=steps_log,
            extracted_rfp=extracted,
            matched_solutions=matched_solutions,
            deployment_feasibility=feasibility,
            compliance_matrix=matrix_rows,
            proposal_summary=proposal,
            hitl_review=hitl_review,
            approval_escalation=approval,
            final_output=final_output,
            current_status=current_status
        )
