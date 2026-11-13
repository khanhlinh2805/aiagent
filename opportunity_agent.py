import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from models.schemas import OpportunityRecord, AssignedSalesRep, CompletenessCheck, CustomerRequestInput

class OpportunityAgent:
    """
    Agent khởi tạo Hồ sơ Cơ hội và Phân công Nhân viên Kinh doanh phụ trách.
    Giải quyết triệt để vấn đề:
    - Hồ sơ bị chuyển qua lại mà không có người theo dõi.
    - Đảm bảo mỗi cơ hội có Ticket ID duy nhất, người sở hữu cụ thể (Account Owner) và hạn SLA xử lý.
    """
    def __init__(self, sales_team_path: str = "data/sales_team.json"):
        with open(sales_team_path, "r", encoding="utf-8") as f:
            self.team_data = json.load(f)
        self.reps = self.team_data["sales_representatives"]
        self.manager = self.team_data["sales_manager"]

    def assign_sales_rep(self, extracted_items: List[Dict[str, Any]]) -> AssignedSalesRep:
        # Xác định nhóm danh mục chủ đạo của yêu cầu
        category_counts = {}
        for item in extracted_items:
            cat = item.get("category", "Khác")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        primary_category = "Giải pháp Tổng thể B2B"
        if len(category_counts) == 1:
            primary_category = list(category_counts.keys())[0]
        elif len(category_counts) > 2:
            primary_category = "Giải pháp Tổng thể B2B"
        elif len(category_counts) > 0:
            primary_category = max(category_counts, key=category_counts.get)

        # Lọc danh sách NVKD có chuyên môn phù hợp
        matching_reps = []
        for rep in self.reps:
            if rep["status"] != "active":
                continue
            is_match = any(primary_category.lower() in spec.lower() for spec in rep["specialty"])
            if is_match or primary_category == "Giải pháp Tổng thể B2B":
                matching_reps.append(rep)

        if not matching_reps:
            matching_reps = [r for r in self.reps if r["status"] == "active"]

        # Chọn NVKD có khối lượng công việc hiện tại (workload) thấp nhất
        selected_rep = min(matching_reps, key=lambda r: r["current_active_leads"])

        assignment_reason = (
            f"Phù hợp chuyên môn nhóm sản phẩm '{primary_category}' "
            f"và có số lượng việc đang xử lý thấp nhất ({selected_rep['current_active_leads']} leads)."
        )

        return AssignedSalesRep(
            id=selected_rep["id"],
            name=selected_rep["name"],
            email=selected_rep["email"],
            specialty=selected_rep["specialty"],
            current_active_leads=selected_rep["current_active_leads"],
            assignment_reason=assignment_reason
        )

    def create_opportunity(
        self,
        request: CustomerRequestInput,
        completeness: CompletenessCheck,
        extracted_items: List[Dict[str, Any]]
    ) -> OpportunityRecord:
        opp_id = f"OPP-2026-{request.id.replace('REQ-', '')}"
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        assigned_rep = None
        if completeness.has_sufficient_info:
            assigned_rep = self.assign_sales_rep(extracted_items)

        current_stage = (
            "KHOI_TAO_THANH_CONG" if completeness.has_sufficient_info
            else "CHO_KHACH_HANG_BO_SUNG_THONG_TIN"
        )

        contact_person = completeness.approver_name or request.customer_name or "Đại diện Quý khách hàng"

        notes = [
            f"Kênh tiếp nhận: Email / Web Form",
            f"Ngày nhận: {request.received_date}",
            f"Trạng thái thông tin: {'Đầy đủ tiêu chuẩn' if completeness.has_sufficient_info else 'Thiếu thông tin quan trọng'}"
        ]

        if not completeness.has_sufficient_info:
            notes.append(f"Mục còn thiếu: {', '.join(completeness.missing_items)}")

        estimated_val = completeness.budget_vnd if completeness.budget_vnd else 0.0

        return OpportunityRecord(
            opp_id=opp_id,
            created_at=created_at,
            customer_name=request.customer_name,
            customer_company=request.customer_company,
            customer_email=request.customer_email,
            contact_person=contact_person,
            assigned_rep=assigned_rep,
            current_stage=current_stage,
            estimated_value_vnd=estimated_val,
            sla_response_hours=4,
            notes=notes
        )

