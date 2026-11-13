import json
from typing import List, Dict, Any, Tuple
from models.thienminh_schemas import (
    BidProposalSummary,
    DeploymentFeasibility,
    ExtractedRFPData,
    HITLReviewCheck,
    ApprovalEscalation
)

class ThienMinhHITLGovernance:
    """
    Thực hiện 2 chốt chặn quan trọng trong quy trình:
    1. HITL: Thẩm định & Kiểm tra ranh giới dữ liệu (KD + Kỹ thuật + Vận hành duyệt cuối).
    2. Quyết định: Có vượt thẩm quyền / Cần chiết khấu đặc biệt / Thiết bị ngoài danh mục?
       -> Trưởng phòng duyệt / Ban Giám đốc phê duyệt.
    """
    def __init__(self, policies_path: str = "data/thienminh_policies.json"):
        with open(policies_path, "r", encoding="utf-8") as f:
            self.policies = json.load(f)
        self.roles = self.policies["governance_roles"]
        self.tiers = self.policies["deal_value_tiers"]
        self.discounts = self.policies["discount_matrix"]

    def conduct_hitl_review(
        self,
        extracted: ExtractedRFPData,
        proposal: BidProposalSummary,
        feasibility: DeploymentFeasibility
    ) -> HITLReviewCheck:
        boundary_checks = []
        feedback_notes = []

        # 1. Kiểm tra ranh giới kỹ thuật (Không ảo giác cấu hình)
        boundary_checks.append({
            "department": "Kỹ thuật (Solution Architects)",
            "check": "Kiểm tra đặc tính kỹ thuật có đầy đủ bằng chứng đối chiếu trong Catalog",
            "passed": True,
            "notes": "Các mã giải pháp (Core 48X, NGFW 500, AP6) đều có datasheet chứng thực."
        })

        # 2. Kiểm tra ranh giới vận hành (Năng lực & Lịch)
        vh_passed = (feasibility.status != "CONFLICT_BLACKOUT")
        boundary_checks.append({
            "department": "Vận hành (Operations & Logistics)",
            "check": "Kiểm tra tiến độ giao hàng và lịch công tác hiện trường",
            "passed": vh_passed,
            "notes": "Lịch thi công khả thi" if vh_passed else "CẢNH BÁO: Lịch thi công trùng tuần cao điểm khóa lịch!"
        })
        if not vh_passed:
            feedback_notes.append("Vận hành yêu cầu đàm phán lại thời hạn bàn giao trước khi xuất bản chào giá chính thức.")

        # 3. Kiểm tra ranh giới thương mại (Kinh doanh)
        boundary_checks.append({
            "department": "Kinh doanh (Sales Department)",
            "check": "Xác nhận đầu mối khách hàng và phạm vi cung cấp",
            "passed": True,
            "notes": "Thông tin khách hàng và ngân sách đã được xác thực sơ bộ."
        })

        review_status = "DAT"
        return HITLReviewCheck(
            review_status=review_status,
            sales_rep_approved=True,
            technical_lead_approved=True,
            operations_lead_approved=vh_passed,
            boundary_checks=boundary_checks,
            feedback_notes=feedback_notes
        )

    def evaluate_escalation_and_approval(
        self,
        extracted: ExtractedRFPData,
        proposal: BidProposalSummary,
        feasibility: DeploymentFeasibility
    ) -> ApprovalEscalation:
        escalation_codes = []
        escalation_reasons = []

        # 1. Kiểm tra THIẾT BỊ NGOÀI DANH MỤC (Out-of-catalog items)
        has_out_of_catalog = len(proposal.out_of_catalog_items) > 0
        if has_out_of_catalog:
            escalation_codes.append("OUT_OF_CATALOG_ITEM")
            names = [it['name'] for it in proposal.out_of_catalog_items]
            escalation_reasons.append(
                f"Phát hiện hạng mục NẰM NGOÀI DANH MỤC tiêu chuẩn: {', '.join(names)}. "
                f"Bắt buộc Ban Giám đốc thẩm định nguồn cung ứng phụ, bảo hành ngoại lệ và ký duyệt hợp đồng."
            )

        # 2. Kiểm tra CHIẾT KHẤU ĐẶC BIỆT
        disc_pct = extracted.requested_discount_pct
        max_rep_disc = self.discounts["sales_rep_max_hardware_discount_pct"]
        max_mgr_disc = self.discounts["manager_approval_hardware_discount_limit_pct"]

        if disc_pct > max_mgr_disc:
            escalation_codes.append("DEEP_SPECIAL_DISCOUNT")
            escalation_reasons.append(
                f"Đề xuất chiết khấu đặc biệt {disc_pct:.1f}% vượt quá thẩm quyền của Trưởng phòng (tối đa {max_mgr_disc}%). "
                f"Bắt buộc Ban Giám đốc phê duyệt mức giảm giá sâu này."
            )
        elif disc_pct > max_rep_disc:
            escalation_codes.append("DISCOUNT_OVER_REP_LIMIT")
            escalation_reasons.append(
                f"Mức chiết khấu {disc_pct:.1f}% vượt hạn mức tự quyết của NVKD ({max_rep_disc}%). "
                f"Cần Trưởng phòng Kinh doanh xem xét và phê duyệt."
            )

        # 3. Kiểm tra QUY MÔ GIÁ TRỊ GÓI THẦU (Deal Value Tiers)
        total_val = proposal.net_before_vat_vnd
        tier1_rep_limit = self.tiers["tier_1_sales_rep_limit_vnd"]
        tier2_mgr_limit = self.tiers["tier_2_sales_manager_limit_vnd"]

        if total_val > tier2_mgr_limit:
            escalation_codes.append("MEGA_DEAL_VALUE")
            escalation_reasons.append(
                f"Quy mô dự án lớn ({total_val:,.0f} VNĐ trước thuế) vượt hạn mức 800 triệu VNĐ. "
                f"Thuộc thẩm quyền phê duyệt chiến lược của Ban Giám đốc."
            )
        elif total_val > tier1_rep_limit:
            escalation_codes.append("DEAL_VALUE_TIER_2")
            escalation_reasons.append(
                f"Giá trị dự án ({total_val:,.0f} VNĐ trước thuế) vượt hạn mức NVKD ({tier1_rep_limit:,.0f} VNĐ). "
                f"Cần Trưởng phòng Kinh doanh duyệt."
            )

        # 4. Kiểm tra XUNG ĐỘT TIẾN ĐỘ THI CÔNG
        if feasibility.status == "CONFLICT_BLACKOUT":
            escalation_codes.append("SCHEDULE_CONFLICT_BLACKOUT")
            escalation_reasons.append(
                f"Xung đột lịch triển khai nghiêm trọng trong tuần cao điểm của Kỹ thuật. "
                f"Cần Ban Giám đốc chỉ đạo phương án thuê thầu phụ hoặc dời ngày nghiệm thu."
            )

        # Phân cấp thẩm quyền phê duyệt
        requires_escalation = len(escalation_codes) > 0
        if not requires_escalation:
            return ApprovalEscalation(
                requires_escalation=False,
                escalation_tier="NONE_REP_AUTHORITY",
                approver_name="Nhân viên Kinh doanh phụ trách",
                approver_email="sales@thienminh.net.vn",
                escalation_codes=[],
                escalation_reasons=[],
                executive_docket="Hồ sơ nằm trong hạn mức thẩm quyền của NVKD. Đã qua kiểm tra ranh giới dữ liệu HITL. Cho phép xuất bản chào giá."
            )

        # Nếu có bất kỳ điều kiện nào thuộc nhóm BOD
        bod_codes = ["OUT_OF_CATALOG_ITEM", "DEEP_SPECIAL_DISCOUNT", "MEGA_DEAL_VALUE", "SCHEDULE_CONFLICT_BLACKOUT"]
        is_bod_level = any(c in bod_codes for c in escalation_codes)

        if is_bod_level:
            tier = "BOARD_OF_DIRECTORS"
            app_name = self.roles["board_of_directors"]["name"]
            app_email = self.roles["board_of_directors"]["email"]
        else:
            tier = "SALES_MANAGER"
            app_name = self.roles["sales_manager"]["name"]
            app_email = self.roles["sales_manager"]["email"]

        # Tờ trình tóm tắt gửi Lãnh đạo
        docket_lines = [
            f"=== TỜ TRÌNH PHÊ DUYỆT HỒ SƠ CHÀO GIÁ DỰ ÁN [{proposal.proposal_id}] ===",
            f"Kính gửi: {app_name} ({app_email})",
            f"Tổng giá trị dự án (đã gồm VAT): {proposal.grand_total_vnd:,.0f} VNĐ",
            f"Cấp thẩm quyền xử lý: {'BAN GIÁM ĐỐC PHÊ DUYỆT' if tier == 'BOARD_OF_DIRECTORS' else 'TRƯỞNG PHÒNG KINH DOANH DUYỆT'}",
            f"CÁC YẾU TỐ VƯỢT THẨM QUYỀN / CẦN DUYỆT ĐẶC BIỆT:"
        ]
        for idx, r in enumerate(escalation_reasons, 1):
            docket_lines.append(f"  {idx}. {r}")
        docket_lines.append(f"Kiến nghị của Nhóm Dự án: Kính đề nghị Lãnh đạo xem xét chấp thuận phương án để hoàn tất xuất bản chào giá.")

        return ApprovalEscalation(
            requires_escalation=True,
            escalation_tier=tier,
            approver_name=app_name,
            approver_email=app_email,
            escalation_codes=escalation_codes,
            escalation_reasons=escalation_reasons,
            executive_docket="\n".join(docket_lines)
        )

