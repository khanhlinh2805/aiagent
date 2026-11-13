from typing import Dict, Any, List
from models.schemas import (
    CustomerRequestInput,
    PipelineExecutionResult,
    OpportunityRecord,
    QuotationSummary,
    ApprovalDocket,
    ResponseDraft
)
from agents.intake_agent import IntakeAgent
from agents.opportunity_agent import OpportunityAgent
from agents.fulfillment_agent import FulfillmentAgent
from agents.pricing_agent import PricingAgent
from agents.approval_agent import ApprovalAgent
from agents.response_agent import ResponseAgent

class MinhAnSalesOrchestrator:
    """
    Quy trình xử lý Cơ hội Bán hàng B2B - Minh An Company
    Thực thi chính xác theo sơ đồ luồng quy trình của Ban Giám đốc:
    1. Bắt đầu: Tiếp nhận yêu cầu
    2. Phân loại & Kiểm tra thông tin
    3. Rẽ nhánh: Có đủ thông tin?
       - Không -> Yêu cầu KH làm rõ / bổ sung -> Chờ tiếp nhận lại
       - Có:
         4. Tạo Hồ sơ Cơ hội & Gắn người phụ trách (NVKD)
         5. Thẩm định tồn kho & giá (NVKD & Bộ phận Vận hành)
         6. Lập Báo giá & Dự thảo đề xuất
         7. Rẽ nhánh: Có vượt thẩm quyền / Cần chiết khấu đặc biệt?
            - Có -> Trưởng phòng duyệt -> Kết thúc: Cập nhật & Theo dõi
            - Không -> Kết thúc: Cập nhật & Theo dõi
    """
    def __init__(
        self,
        catalog_path: str = "data/products_catalog.json",
        inventory_path: str = "data/inventory.json",
        policies_path: str = "data/policies.json",
        sales_team_path: str = "data/sales_team.json"
    ):
        self.intake_agent = IntakeAgent(catalog_path)
        self.opportunity_agent = OpportunityAgent(sales_team_path)
        self.fulfillment_agent = FulfillmentAgent(inventory_path)
        self.pricing_agent = PricingAgent(catalog_path, policies_path)
        self.approval_agent = ApprovalAgent(policies_path, sales_team_path)
        self.response_agent = ResponseAgent()

    def process_request(self, request: CustomerRequestInput) -> PipelineExecutionResult:
        steps_log: List[Dict[str, Any]] = []

        # BƯỚC 1: Bắt đầu - Tiếp nhận yêu cầu
        steps_log.append({
            "step_id": 1,
            "step_name": "Bắt đầu: Tiếp nhận yêu cầu",
            "status": "COMPLETED",
            "details": f"Tiếp nhận yêu cầu {request.id} từ khách hàng {request.customer_name} ({request.customer_company}) qua Email/Form."
        })

        # BƯỚC 2 & 3: Phân loại & Kiểm tra thông tin
        completeness, extracted_items = self.intake_agent.extract_and_evaluate(request)
        
        steps_log.append({
            "step_id": 2,
            "step_name": "Phân loại & Kiểm tra thông tin",
            "status": "COMPLETED",
            "details": (
                f"Đã trích xuất {len(extracted_items)} hạng mục sản phẩm/dịch vụ. "
                f"Ngân sách: {'Có' if completeness.has_budget else 'Chưa có'}. "
                f"Thời hạn: {'Có' if completeness.has_deadline else 'Chưa có'}."
            )
        })

        # NHÁNH: CÓ ĐỦ THÔNG TIN?
        if not completeness.has_sufficient_info:
            steps_log.append({
                "step_id": 3,
                "step_name": "Kiểm tra thông tin: KHÔNG ĐỦ",
                "status": "BRANCH_TAKEN",
                "details": f"Thiếu các thông tin bắt buộc: {', '.join(completeness.missing_items)}."
            })

            # Tạo hồ sơ tạm để theo dõi, tránh thất lạc
            opportunity = self.opportunity_agent.create_opportunity(request, completeness, extracted_items)

            # Soạn email yêu cầu KH làm rõ / bổ sung
            steps_log.append({
                "step_id": 31,
                "step_name": "Yêu cầu KH làm rõ / bổ sung",
                "status": "COMPLETED",
                "details": f"Đã sinh bản nháp email đề nghị khách hàng bổ sung {len(completeness.clarification_questions)} thông tin còn thiếu."
            })

            draft = self.response_agent.generate_draft(
                request=request,
                completeness=completeness,
                opportunity=opportunity
            )

            return PipelineExecutionResult(
                request_id=request.id,
                workflow_steps=steps_log,
                completeness=completeness,
                opportunity_record=opportunity,
                quotation=None,
                approval=None,
                response_draft=draft,
                final_status="WAITING_CLARIFICATION"
            )

        # CÓ ĐỦ THÔNG TIN:
        steps_log.append({
            "step_id": 3,
            "step_name": "Kiểm tra thông tin: ĐỦ THÔNG TIN",
            "status": "BRANCH_TAKEN",
            "details": "Yêu cầu đầy đủ hạng mục, số lượng, thời hạn và thông tin người liên hệ."
        })

        # BƯỚC 4: Tạo Hồ sơ Cơ hội & Gắn người phụ trách
        opportunity = self.opportunity_agent.create_opportunity(request, completeness, extracted_items)
        rep = opportunity.assigned_rep
        steps_log.append({
            "step_id": 4,
            "step_name": "Tạo Hồ sơ Cơ hội & Gắn người phụ trách",
            "status": "COMPLETED",
            "details": f"Đã tạo hồ sơ {opportunity.opp_id}, phân công NVKD {rep.name} ({rep.email}) phụ trách. Lý do: {rep.assignment_reason}"
        })

        # BƯỚC 5: Thẩm định tồn kho & giá (NVKD & Bộ phận Vận hành)
        verified_items, lead_days, lead_status, lead_explanation = self.fulfillment_agent.verify_stock_and_sla(
            extracted_items=extracted_items,
            customer_deadline_days=completeness.deadline_days
        )
        steps_log.append({
            "step_id": 5,
            "step_name": "Thẩm định tồn kho & giá (Bộ phận Vận hành)",
            "status": "COMPLETED",
            "details": f"Tồn kho & SLA: {lead_status}. Tổng thời gian khả thi: {lead_days} ngày. {lead_explanation}"
        })

        # BƯỚC 6: Lập Báo giá & Dự thảo đề xuất
        quotation = self.pricing_agent.generate_quotation(
            opp_id=opportunity.opp_id,
            verified_items=verified_items,
            requested_discount_pct=completeness.requested_discount_pct or 0.0,
            customer_budget_vnd=completeness.budget_vnd,
            required_lead_time_days=lead_days,
            customer_requested_lead_days=completeness.deadline_days,
            lead_time_status=lead_status,
            lead_time_explanation=lead_explanation
        )
        opportunity.estimated_value_vnd = quotation.grand_total_vnd

        steps_log.append({
            "step_id": 6,
            "step_name": "Lập Báo giá & Dự thảo đề xuất",
            "status": "COMPLETED",
            "details": f"Đã lập Báo giá {quotation.quote_id}: Tổng tiền {quotation.grand_total_vnd:,.0f} VNĐ (VAT 10%). {quotation.budget_comparison}"
        })

        # BƯỚC 7: Kiểm tra vượt thẩm quyền / Cần chiết khấu đặc biệt
        approval = self.approval_agent.evaluate_authorization(
            quotation=quotation,
            requested_discount_pct=completeness.requested_discount_pct or 0.0
        )

        if approval.requires_manager_approval:
            steps_log.append({
                "step_id": 7,
                "step_name": "Có vượt thẩm quyền / Cần chiết khấu đặc biệt: CÓ",
                "status": "BRANCH_TAKEN",
                "details": f"Cần Trưởng phòng ({approval.manager_name}) phê duyệt do: {'; '.join(approval.trigger_reasons)}"
            })
            steps_log.append({
                "step_id": 71,
                "step_name": "Trưởng phòng duyệt",
                "status": "ESCALATED",
                "details": f"Hồ sơ chuyển đến hộp thư của Trưởng phòng: {approval.manager_email}. Tờ trình đã được sinh tự động."
            })
            opportunity.current_stage = "CHO_TRUONG_PHONG_DUYET"
        else:
            steps_log.append({
                "step_id": 7,
                "step_name": "Có vượt thẩm quyền / Cần chiết khấu đặc biệt: KHÔNG",
                "status": "BRANCH_TAKEN",
                "details": "Nằm trong hạn mức phê duyệt của NVKD. Tự động thông qua."
            })
            opportunity.current_stage = "HOAN_TAT_SAN_SANG_GUI_KH"

        # BƯỚC 8: Sinh Bản nháp phản hồi khách hàng & Kết thúc: Cập nhật & Theo dõi
        draft = self.response_agent.generate_draft(
            request=request,
            completeness=completeness,
            opportunity=opportunity,
            quotation=quotation,
            approval=approval
        )

        steps_log.append({
            "step_id": 8,
            "step_name": "Kết thúc: Cập nhật & Theo dõi",
            "status": "COMPLETED",
            "details": f"Đã lưu Hồ sơ Cơ hội {opportunity.opp_id} vào hệ thống CRM, kích hoạt đồng hồ đếm ngược SLA ({opportunity.sla_response_hours}h) và chuẩn bị sẵn Bản nháp phản hồi khách hàng."
        })

        final_status = "PENDING_APPROVAL" if approval.requires_manager_approval else "READY_TO_SEND"

        return PipelineExecutionResult(
            request_id=request.id,
            workflow_steps=steps_log,
            completeness=completeness,
            opportunity_record=opportunity,
            quotation=quotation,
            approval=approval,
            response_draft=draft,
            final_status=final_status
        )

