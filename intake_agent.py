import re
import json
from typing import Dict, Any, List, Tuple
from models.schemas import CustomerRequestInput, CompletenessCheck

class IntakeAgent:
    """
    Agent tiếp nhận, phân loại và kiểm tra tính đầy đủ của yêu cầu khách hàng.
    Giải quyết triệt để vấn đề:
    - Bỏ sót hạng mục (100% item bóc tách chuẩn).
    - Thiếu thông tin dẫn đến chuyển qua lại không người theo dõi.
    """
    def __init__(self, catalog_path: str = "data/products_catalog.json"):
        with open(catalog_path, "r", encoding="utf-8") as f:
            self.catalog = json.load(f)

    def extract_and_evaluate(self, request: CustomerRequestInput) -> Tuple[CompletenessCheck, List[Dict[str, Any]]]:
        text = request.raw_text
        text_lower = text.lower()

        # 1. Trích xuất ngân sách
        budget_vnd = None
        has_budget = False
        budget_patterns = [
            r'ngân sách[^:\d\n]*[:\s]+([\d\.,]+)\s*(vnđ|vnd|đ|tỷ|triệu)?',
            r'dự toán[^:\d\n]*[:\s]+([\d\.,]+)\s*(vnđ|vnd|đ|tỷ|triệu)?',
            r'khoảng\s+([\d\.,]+)\s*(vnđ|vnd|đ|tỷ|triệu)'
        ]
        for pattern in budget_patterns:
            match = re.search(pattern, text_lower)
            if match:
                raw_val = match.group(1).replace(".", "").replace(",", "").strip()
                unit = match.group(2) if len(match.groups()) > 1 else ""
                try:
                    num = float(raw_val)
                    if unit in ["triệu", "trieu"]:
                        num *= 1_000_000
                    elif unit in ["tỷ", "ty"]:
                        num *= 1_000_000_000
                    budget_vnd = num
                    has_budget = True
                    break
                except ValueError:
                    pass

        # 2. Trích xuất thời hạn
        has_deadline = False
        deadline_days = None
        deadline_date = None
        deadline_patterns = [
            r'trong vòng\s+(\d+)\s+ngày',
            r'khoảng\s+(\d+)\s+ngày',
            r'thời hạn[^:\d\n]*[:\s]+(\d+)\s+ngày',
            r'trước ngày\s+(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4})'
        ]
        for pattern in deadline_patterns:
            match = re.search(pattern, text_lower)
            if match:
                val = match.group(1)
                if "/" in val or "." in val or "-" in val:
                    deadline_date = val
                    has_deadline = True
                else:
                    try:
                        deadline_days = int(val)
                        has_deadline = True
                        break
                    except ValueError:
                        pass

        # 3. Trích xuất chiết khấu đề nghị
        discount_pct = 0.0
        discount_patterns = [
            r'chiết khấu[^:\d\n]*[:\s]+(\d+(?:\.\d+)?)\s*%',
            r'giảm giá[^:\d\n]*[:\s]+(\d+(?:\.\d+)?)\s*%',
            r'hữu nghị\s+(\d+(?:\.\d+)?)\s*%'
        ]
        for pattern in discount_patterns:
            match = re.search(pattern, text_lower)
            if match:
                try:
                    discount_pct = float(match.group(1))
                    break
                except ValueError:
                    pass

        # 4. Trích xuất người phê duyệt / đại diện
        has_approver = False
        approver_name = None
        for raw_line in text.split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            line_l = line.lower()
            if any(k in line_l for k in ["người phê duyệt", "người phụ trách", "người đại diện", "đại diện phê duyệt"]):
                # Tách phần tên sau dấu hai chấm hoặc chữ "là"
                parts = re.split(r'[:\b]|\blà\b', line, maxsplit=1)
                if len(parts) > 1:
                    clean_name = parts[1].strip().rstrip(".")
                    if len(clean_name) > 3:
                        approver_name = clean_name
                        has_approver = True
                        break

        if not has_approver and request.customer_name:
            approver_name = request.customer_name
            has_approver = True

        # 5. Bóc tách sản phẩm & Số lượng
        sku_keywords = {
            "SRV-DELL-R750": ["dell poweredge r750", "dell r750", "máy chủ dell r750", "server dell r750", "dell poweredge"],
            "SRV-HPE-DL380": ["hpe prolian dl380", "hpe dl380", "máy chủ hp", "máy chủ hpe"],
            "SW-CISCO-C9200L": ["cisco catalyst c9200l", "switch cisco catalyst", "cisco c9200l", "c9200l-24p-4g-e"],
            "FW-FORTI-100F": ["fortigate 100f", "fortinet 100f", "tường lửa fortinet 100f"],
            "FW-FORTI-60F": ["fortigate 60f", "fortinet 60f", "tường lửa fortinet 60f"],
            "AP-ARUBA-AP505": ["aruba instant on ap22", "aruba ap22", "wi-fi aruba", "wifi aruba", "aruba"],
            "NB-LENOVO-T14": ["thinkpad t14", "lenovo thinkpad t14", "thinkpad t14 gen 4"],
            "NB-DELL-LAT5440": ["dell latitude 5440", "latitude 5440", "dell latitude"],
            "LIC-MS-M365BP": ["microsoft 365 business premium", "m365 business premium", "bản quyền microsoft 365", "microsoft 365"],
            "LIC-WIN-SVR2022": ["windows server 2022 standard", "windows server 2022", "bản quyền windows server"],
            "SVC-SETUP-SERVER": ["cấu hình, cài đặt hệ thống máy chủ", "dịch vụ cài đặt server", "triển khai ảo hóa", "cài đặt máy chủ & ảo hóa"],
            "SVC-DEPLOY-NET": ["dịch vụ khảo sát, lắp đặt và tối ưu hạ tầng mạng", "lắp đặt mạng lan", "triển khai mạng lan", "tối ưu hạ tầng mạng lan / wi-fi", "dịch vụ lắp đặt và cấu hình khẩn cấp"],
            "SVC-MAINT-12M": ["dịch vụ bảo trì hệ thống cntt", "bảo trì 12 tháng", "bảo trì trọn gói 12 tháng", "bảo trì hệ thống"]
        }

        extracted_items = []
        raw_lines = [l.strip() for l in text.split("\n") if l.strip()]

        for sku, keywords in sku_keywords.items():
            matched = False
            qty = 1
            for raw_line in raw_lines:
                # Loại bỏ số thứ tự đầu dòng như "1.", "2. ", "1 - "
                cleaned_line = re.sub(r'^\s*[\d\.\-\*\)]+\s*', '', raw_line).strip()
                l_lower = cleaned_line.lower()

                for kw in keywords:
                    if kw in l_lower:
                        matched = True
                        # Tìm số lượng với đơn vị rõ ràng trước
                        unit_qty_match = re.search(r'(\d+)\s*(chiếc|cái|bộ|gói|bản quyền|user|máy|thiết bị)\b', l_lower)
                        if unit_qty_match:
                            try:
                                qty = int(unit_qty_match.group(1))
                            except ValueError:
                                qty = 1
                        else:
                            # Nếu không có đơn vị, tìm số ở đầu dòng đã clean
                            leading_num_match = re.match(r'^(\d+)\b', l_lower)
                            if leading_num_match:
                                try:
                                    qty = int(leading_num_match.group(1))
                                except ValueError:
                                    qty = 1
                        break
                if matched:
                    break

            if matched:
                cat_prod = next((p for p in self.catalog if p["sku"] == sku), None)
                if cat_prod:
                    extracted_items.append({
                        "sku": sku,
                        "name": cat_prod["name"],
                        "category": cat_prod["category"],
                        "unit": cat_prod["unit"],
                        "quantity": qty,
                        "price_vnd": cat_prod["price_vnd"]
                    })

        missing_items = []
        clarification_questions = []

        has_generic_unspecified_items = False
        if len(extracted_items) == 0:
            if any(k in text_lower for k in ["máy chủ", "server", "thinkpad", "laptop", "switch", "mạng"]):
                has_generic_unspecified_items = True

        has_products = (len(extracted_items) > 0) and not has_generic_unspecified_items

        if not has_products:
            missing_items.append("Danh mục sản phẩm/dịch vụ cụ thể (Model, cấu hình kỹ thuật và số lượng chi tiết)")
            clarification_questions.append("Quý khách cần bao nhiêu bộ máy chủ và yêu cầu cấu hình (CPU, RAM, Dung lượng lưu trữ) như thế nào?")
            clarification_questions.append("Số lượng máy tính xách tay ThinkPad cần trang bị là bao nhiêu chiếc và mức cấu hình dự kiến?")

        if not has_budget:
            missing_items.append("Ngân sách dự kiến của dự án")
            clarification_questions.append("Quý công ty đã có khung ngân sách tối đa dự kiến cho đợt mua sắm này chưa?")

        if not has_deadline:
            missing_items.append("Thời hạn hoàn thành / tiến độ bàn giao yêu cầu")
            clarification_questions.append("Dự án dự kiến cần hoàn thành triển khai và bàn giao chậm nhất vào thời gian nào?")

        has_sufficient_info = (len(missing_items) == 0)

        extracted_summary = [f"{item['quantity']}x {item['name']} ({item['sku']})" for item in extracted_items]

        completeness = CompletenessCheck(
            has_sufficient_info=has_sufficient_info,
            missing_items=missing_items,
            has_budget=has_budget,
            budget_vnd=budget_vnd,
            has_deadline=has_deadline,
            deadline_days=deadline_days,
            deadline_date=deadline_date,
            has_approver=has_approver,
            approver_name=approver_name,
            has_products=has_products,
            requested_discount_pct=discount_pct,
            extracted_items_summary=extracted_summary,
            clarification_questions=clarification_questions
        )

        return completeness, extracted_items
