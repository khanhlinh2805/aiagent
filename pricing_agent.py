import json
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
from models.schemas import LineItemDetail, QuotationSummary

class PricingAgent:
    """
    Agent tính toán giá, chiết khấu và lập Báo giá đề xuất.
    Giải quyết triệt để vấn đề:
    - Dùng giá cũ (luôn lấy giá niêm yết hiện hành mới nhất từ Master Catalog).
    - Tính toán chiết khấu minh bạch và đối chiếu ngân sách khách hàng.
    """
    def __init__(
        self,
        catalog_path: str = "data/products_catalog.json",
        policies_path: str = "data/policies.json"
    ):
        with open(catalog_path, "r", encoding="utf-8") as f:
            self.catalog = {p["sku"]: p for p in json.load(f)}
        with open(policies_path, "r", encoding="utf-8") as f:
            self.policies = json.load(f)

    def generate_quotation(
        self,
        opp_id: str,
        verified_items: List[Dict[str, Any]],
        requested_discount_pct: float,
        customer_budget_vnd: Optional[float],
        required_lead_time_days: int,
        customer_requested_lead_days: Optional[int],
        lead_time_status: str,
        lead_time_explanation: str
    ) -> QuotationSummary:
        quote_id = f"BG-{opp_id.replace('OPP-', '')}"
        created_date = datetime.now().strftime("%Y-%m-%d")
        validity_days = self.policies.get("quote_validity_days", 15)

        line_items: List[LineItemDetail] = []
        gross_subtotal = 0.0
        total_discount = 0.0

        for item in verified_items:
            sku = item["sku"]
            qty = item["quantity"]
            cat_item = self.catalog.get(sku, {})
            current_unit_price = cat_item.get("price_vnd", item.get("price_vnd", 0))

            # Xác định mức chiết khấu áp dụng cho item
            applied_discount_pct = requested_discount_pct if requested_discount_pct > 0 else 0.0

            discount_per_unit = current_unit_price * (applied_discount_pct / 100.0)
            final_unit_price = current_unit_price - discount_per_unit
            line_gross = current_unit_price * qty
            line_discount = discount_per_unit * qty
            line_total = final_unit_price * qty

            gross_subtotal += line_gross
            total_discount += line_discount

            line_items.append(LineItemDetail(
                sku=sku,
                product_name=cat_item.get("name", item.get("name", sku)),
                category=cat_item.get("category", "Chung"),
                unit=cat_item.get("unit", "Cái"),
                quantity=qty,
                unit_price_vnd=current_unit_price,
                discount_pct=applied_discount_pct,
                discount_amount_vnd=line_discount,
                final_unit_price_vnd=final_unit_price,
                line_total_vnd=line_total,
                on_hand_stock=item.get("on_hand", 0),
                available_stock=item.get("available", 0),
                is_in_stock=item.get("is_in_stock", True),
                item_lead_time_days=item.get("item_lead_days", 1),
                notes=item.get("stock_status_text")
            ))

        net_before_vat = gross_subtotal - total_discount
        vat_rate = self.policies.get("vat_rate_default", 0.10)
        vat_amount = net_before_vat * vat_rate
        grand_total = net_before_vat + vat_amount

        # So sánh ngân sách
        budget_comparison = "Chưa cung cấp ngân sách cụ thể"
        if customer_budget_vnd and customer_budget_vnd > 0:
            diff = customer_budget_vnd - grand_total
            if diff >= 0:
                budget_comparison = (
                    f"PHÙ HỢP NGÂN SÁCH: Tổng báo giá ({grand_total:,.0f} VNĐ đã gồm VAT) "
                    f"thấp hơn hoặc bằng ngân sách dự kiến của khách ({customer_budget_vnd:,.0f} VNĐ). "
                    f"Dư địa tiết kiệm: {diff:,.0f} VNĐ."
                )
            else:
                pct_over = abs(diff) / customer_budget_vnd * 100
                budget_comparison = (
                    f"VƯỢT NGÂN SÁCH DỰ KIẾN: Tổng báo giá ({grand_total:,.0f} VNĐ đã gồm VAT) "
                    f"vượt ngân sách dự kiến ({customer_budget_vnd:,.0f} VNĐ) khoảng {abs(diff):,.0f} VNĐ (+{pct_over:.1f}%). "
                    f"Đề xuất: NVKD chủ động tư vấn phương án tinh giản cấu hình hoặc chia kỳ đầu tư."
                )

        return QuotationSummary(
            quote_id=quote_id,
            created_date=created_date,
            validity_days=validity_days,
            items=line_items,
            gross_subtotal_vnd=gross_subtotal,
            total_discount_vnd=total_discount,
            net_before_vat_vnd=net_before_vat,
            vat_rate=vat_rate,
            vat_amount_vnd=vat_amount,
            grand_total_vnd=grand_total,
            customer_budget_vnd=customer_budget_vnd,
            budget_comparison=budget_comparison,
            required_lead_time_days=required_lead_time_days,
            customer_requested_lead_time_days=customer_requested_lead_days,
            lead_time_status=lead_time_status,
            lead_time_explanation=lead_time_explanation
        )

