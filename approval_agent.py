import json
from typing import List, Dict, Any
from models.schemas import QuotationSummary, ApprovalDocket

class ApprovalAgent:
    """
    Agent kiểm tra Thẩm quyền Phê duyệt & Đề xuất Chiết khấu đặc biệt.
    Thực hiện nhánh quyết định:
    'Có vượt thẩm quyền / Cần chiết khấu đặc biệt?' -> 'Trưởng phòng duyệt'
    """
    def __init__(
        self,
        policies_path: str = "data/policies.json",
        sales_team_path: str = "data/sales_team.json"
    ):
        with open(policies_path, "r", encoding="utf-8") as f:
            self.policies = json.load(f)
        with open(sales_team_path, "r", encoding="utf-8") as f:
            self.team = json.load(f)
        self.manager = self.team["sales_manager"]

    def evaluate_authorization(
        self,
        quotation: QuotationSummary,
        requested_discount_pct: float
    ) -> ApprovalDocket:
        disc_matrix = self.policies["discount_matrix"]
        limits = self.policies["deal_value_limits"]

        trigger_codes = []
        trigger_reasons = []

        # 1. Kiểm tra chiết khấu
        max_rep_hardware_disc = disc_matrix.get("hardware_max_rep_discount_pct", 8.0)
        max_rep_service_disc = disc_matrix.get("services_max_rep_discount_pct", 12.0)

        if requested_discount_pct > max_rep_hardware_disc:
            trigger_codes.append("DISCOUNT_OVER_LIMIT")
            trigger_reasons.append(
                f"Mức chiết khấu đề xuất {requested_discount_pct:.1f}% vượt quá thẩm quyền tối đa của NVKD "
                f"(Phần cứng tối đa {max_rep_hardware_disc}%, Dịch vụ tối đa {max_rep_service_disc}%)."
            )

        # 2. Kiểm tra quy mô deal
        max_rep_deal_val = limits.get("sales_rep_max_deal_vnd", 250000000)
        if quotation.net_before_vat_vnd > max_rep_deal_val:
            trigger_codes.append("DEAL_VALUE_HIGH")
            trigger_reasons.append(
                f"Tổng giá trị cơ hội ({quotation.net_before_vat_vnd:,.0f} VNĐ trước thuế) "
                f"vượt hạn mức tự quyết của NVKD ({max_rep_deal_val:,.0f} VNĐ)."
            )

        # 3. Kiểm tra xung đột thời hạn giao hàng (SLA conflict)
        if quotation.lead_time_status == "CONFLICT":
            trigger_codes.append("RUSH_TIMELINE_CONFLICT")
            trigger_reasons.append(
                f"Tiến độ khách yêu cầu ({quotation.customer_requested_lead_time_days} ngày) "
                f"ngắn hơn thời gian tối thiểu của Vận hành ({quotation.required_lead_time_days} ngày). "
                f"Cần Trưởng phòng kinh doanh chỉ đạo phương án giao hàng từng phần hoặc làm việc với hãng."
            )

        requires_manager = len(trigger_codes) > 0
        status = "ESCALATED_TO_MANAGER" if requires_manager else "AUTO_APPROVED"

        # Tờ trình tóm tắt gửi Trưởng phòng
        justification_lines = []
        if requires_manager:
            justification_lines.append(f"TỜ TRÌNH PHÊ DUYỆT CƠ HỘI BÁN HÀNG VƯỢT THẨM QUYỀN")
            justification_lines.append(f"Kính gửi: {self.manager['name']} - {self.manager['role']}")
            justification_lines.append(f"Mã báo giá: {quotation.quote_id}")
            justification_lines.append(f"Tổng giá trị hợp đồng (gồm VAT): {quotation.grand_total_vnd:,.0f} VNĐ")
            justification_lines.append(f"Lý do cần phê duyệt:")
            for idx, r in enumerate(trigger_reasons, 1):
                justification_lines.append(f"  {idx}. {r}")
            justification_lines.append(f"Đề xuất của hệ thống: Đã kiểm định giá niêm yết và tồn kho. Kính đề nghị Trưởng phòng xem xét chấp thuận.")
        else:
            justification_lines.append("Cơ hội nằm trong hạn mức thẩm quyền của NVKD. Hệ thống tự động xác thực và cho phép gửi báo giá trực tiếp.")

        return ApprovalDocket(
            requires_manager_approval=requires_manager,
            manager_name=self.manager["name"],
            manager_email=self.manager["email"],
            trigger_codes=trigger_codes,
            trigger_reasons=trigger_reasons,
            status=status,
            justification_for_manager="\n".join(justification_lines)
        )

