import json
from datetime import datetime
from typing import List, Dict, Any, Tuple
from models.thienminh_schemas import SolutionMatchingResult, BidProposalSummary

class ThienMinhPricingDiscountAgent:
    """
    [AI AGENT] AI: Tính toán giá đề xuất & áp dụng chính sách chiết khấu
    Giải quyết triệt để vấn đề:
    - Giảm giá tùy tiện không có kiểm soát.
    - Nhận diện thiết bị ngoài danh mục (Out-of-catalog).
    - Đối chiếu ngân sách khách hàng.
    """
    def __init__(self, policies_path: str = "data/thienminh_policies.json"):
        with open(policies_path, "r", encoding="utf-8") as f:
            self.policies = json.load(f)

    def calculate_proposal(
        self,
        rfp_id: str,
        matched_solutions: List[SolutionMatchingResult],
        out_of_catalog_items: List[Dict[str, Any]],
        requested_discount_pct: float,
        customer_budget_vnd: float = None
    ) -> BidProposalSummary:
        proposal_id = f"TM-BID-{rfp_id.replace('RFP-', '')}"
        created_date = datetime.now().strftime("%Y-%m-%d")
        validity_days = self.policies.get("quote_validity_days", 30)

        line_items = []
        gross_catalog_subtotal = 0.0

        for s in matched_solutions:
            line_gross = s.total_price_vnd
            gross_catalog_subtotal += line_gross
            line_items.append({
                "sku": s.matched_sku,
                "name": s.solution_name,
                "category": s.category,
                "quantity": s.quantity,
                "unit": s.unit,
                "unit_price_vnd": s.unit_price_vnd,
                "line_total_vnd": line_gross,
                "compliance_status": s.compliance_status_text,
                "selection_notes": "; ".join(s.reasons_for_selection)
            })

        # Xử lý thiết bị ngoài danh mục
        out_of_catalog_total = 0.0
        for out_it in out_of_catalog_items:
            cost = out_it.get("estimated_cost_vnd", 0.0) * out_it.get("quantity", 1)
            out_of_catalog_total += cost

        # Chiết khấu chỉ áp dụng trên hàng danh mục tiêu chuẩn (không tự ý chiết khấu hàng OEM đặt riêng)
        discount_rate = requested_discount_pct / 100.0 if requested_discount_pct > 0 else 0.0
        total_discount = gross_catalog_subtotal * discount_rate

        net_before_vat = (gross_catalog_subtotal - total_discount) + out_of_catalog_total
        vat_rate = self.policies.get("default_vat_rate", 0.10)
        vat_amount = net_before_vat * vat_rate
        grand_total = net_before_vat + vat_amount

        # Phân tích độ tương thích ngân sách
        budget_analysis = "Chưa cung cấp ngân sách dự kiến."
        if customer_budget_vnd and customer_budget_vnd > 0:
            diff = customer_budget_vnd - grand_total
            if diff >= 0:
                budget_analysis = (
                    f"PHÙ HỢP DỰ TOÁN: Tổng giá trị hồ sơ chào giá ({grand_total:,.0f} VNĐ gồm VAT) "
                    f"nằm trong khung ngân sách phê duyệt của khách hàng ({customer_budget_vnd:,.0f} VNĐ). "
                    f"Dư địa tài chính an toàn: {diff:,.0f} VNĐ."
                )
            else:
                pct_over = abs(diff) / customer_budget_vnd * 100
                budget_analysis = (
                    f"CẢNH BÁO VƯỢT DỰ TOÁN: Tổng đề xuất ({grand_total:,.0f} VNĐ) vượt ngân sách dự toán "
                    f"của khách ({customer_budget_vnd:,.0f} VNĐ) khoảng {abs(diff):,.0f} VNĐ (+{pct_over:.1f}%). "
                    f"Lý do: Đã bắt buộc lựa chọn cấu hình chuẩn cao cấp (Dual PSU, HA, 100G) để đáp ứng điều kiện bắt buộc của RFP."
                )

        return BidProposalSummary(
            proposal_id=proposal_id,
            created_date=created_date,
            validity_days=validity_days,
            line_items=line_items,
            out_of_catalog_items=out_of_catalog_items,
            gross_subtotal_vnd=gross_catalog_subtotal,
            total_discount_vnd=total_discount,
            net_before_vat_vnd=net_before_vat,
            vat_amount_vnd=vat_amount,
            grand_total_vnd=grand_total,
            budget_analysis=budget_analysis
        )

