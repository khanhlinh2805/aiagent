import json
from typing import List, Dict, Any, Tuple
from models.schemas import LineItemDetail

class FulfillmentAgent:
    """
    Agent thẩm định Tồn kho & Thời gian triển khai cùng Bộ phận Vận hành.
    Giải quyết triệt để vấn đề:
    - Hứa thời hạn không đáp ứng được cho khách hàng.
    - Đảm bảo biết chính xác số lượng tồn kho khả dụng và lead time nhập hàng thực tế.
    """
    def __init__(self, inventory_path: str = "data/inventory.json"):
        with open(inventory_path, "r", encoding="utf-8") as f:
            self.inventory_data = json.load(f)
        self.items_stock = self.inventory_data["inventory_items"]
        self.qc_buffer_days = 2  # Thời gian kiểm định QA/QC trước khi xuất xưởng

    def verify_stock_and_sla(
        self,
        extracted_items: List[Dict[str, Any]],
        customer_deadline_days: int = None
    ) -> Tuple[List[Dict[str, Any]], int, str, str]:
        verified_items = []
        max_hardware_lead_days = 0
        total_service_days = 0
        stock_shortage_items = []

        for item in extracted_items:
            sku = item["sku"]
            qty = item["quantity"]
            stock_info = self.items_stock.get(sku, {})

            is_service = stock_info.get("is_service", False)
            if is_service:
                tech_days = stock_info.get("technician_capacity_days", 2)
                sched_days = stock_info.get("scheduling_lead_time_days", 2)
                item_lead = sched_days + tech_days
                total_service_days = max(total_service_days, item_lead)

                verified_items.append({
                    **item,
                    "on_hand": 999,
                    "available": 999,
                    "is_in_stock": True,
                    "item_lead_days": item_lead,
                    "stock_status_text": f"Dịch vụ kỹ thuật (SLA bố trí nhân sự: {item_lead} ngày làm việc)"
                })
            else:
                on_hand = stock_info.get("on_hand", 0)
                available = stock_info.get("available", 0)
                prep_days = stock_info.get("dispatch_prep_days", 1)
                out_of_stock_lead = stock_info.get("lead_time_days_if_out_of_stock", 14)

                if available >= qty:
                    is_in_stock = True
                    item_lead = prep_days
                    status_text = f"Sẵn sàng trong kho ({available} khả dụng)"
                else:
                    is_in_stock = False
                    item_lead = out_of_stock_lead + prep_days
                    status_text = f"Hết hàng / Thiếu {qty - available} cái (Cần nhập khẩu {out_of_stock_lead} ngày)"
                    stock_shortage_items.append(f"{item['name']} (thiếu {qty - available})")

                max_hardware_lead_days = max(max_hardware_lead_days, item_lead)

                verified_items.append({
                    **item,
                    "on_hand": on_hand,
                    "available": available,
                    "is_in_stock": is_in_stock,
                    "item_lead_days": item_lead,
                    "stock_status_text": status_text
                })

        # Tổng thời gian triển khai cam kết của Vận hành
        total_required_lead_days = max_hardware_lead_days + (self.qc_buffer_days if max_hardware_lead_days > 0 else 0) + total_service_days
        # Đảm bảo tối thiểu 3 ngày chuẩn bị chứng từ và vận chuyển
        total_required_lead_days = max(total_required_lead_days, 3)

        # Đánh giá tính khả thi so với thời hạn khách yêu cầu
        lead_time_status = "FEASIBLE"
        lead_time_explanation = ""

        if customer_deadline_days is not None:
            if customer_deadline_days < total_required_lead_days:
                lead_time_status = "CONFLICT"
                lead_time_explanation = (
                    f"CẢNH BÁO XUNG ĐỘT TIẾN ĐỘ: Khách hàng yêu cầu hoàn thành trong {customer_deadline_days} ngày, "
                    f"nhưng tổng thời gian tối thiểu của Vận hành là {total_required_lead_days} ngày "
                    f"(Do: {', '.join(stock_shortage_items) if stock_shortage_items else 'Thời gian kiểm định QC và triển khai kỹ thuật'}). "
                    f"ĐỀ XUẤT: Không cam kết bừa. Cần đàm phán mốc {total_required_lead_days} ngày hoặc đề xuất giao trước các thiết bị có sẵn."
                )
            elif customer_deadline_days <= total_required_lead_days + 3:
                lead_time_status = "TIGHT"
                lead_time_explanation = (
                    f"TIẾN ĐỘ SÁT NÚT: Yêu cầu {customer_deadline_days} ngày, năng lực đáp ứng {total_required_lead_days} ngày. "
                    f"Cần Vận hành ưu tiên xử lý đơn hàng này ngay khi ký hợp đồng."
                )
            else:
                lead_time_status = "FEASIBLE"
                lead_time_explanation = (
                    f"TIẾN ĐỘ KHẢ THI HOÀN TOÀN: Khách hàng cho phép {customer_deadline_days} ngày, "
                    f"Minh An đáp ứng trong {total_required_lead_days} ngày."
                )
        else:
            lead_time_status = "FEASIBLE"
            lead_time_explanation = f"Thời gian tiêu chuẩn cam kết: {total_required_lead_days} ngày làm việc."

        return verified_items, total_required_lead_days, lead_time_status, lead_time_explanation

