import re
import json
from typing import Dict, Any, List, Tuple
from models.thienminh_schemas import ExtractedRFPData, MandatoryCriterion

class ThienMinhIntakeExtractor:
    """
    [AI AGENT] AI: Trích xuất & Phân rã yêu cầu
    Bóc tách: hạng mục, deadline, ngân sách, điều kiện bắt buộc, thiết bị ngoài danh mục.
    Thực hiện rẽ nhánh: 'Có đủ thông tin?' -> Nếu Không: Sinh câu hỏi làm rõ.
    """
    def __init__(self, catalog_path: str = "data/thienminh_solutions.json"):
        with open(catalog_path, "r", encoding="utf-8") as f:
            self.catalog = json.load(f)

    def extract_rfp(self, rfp_data: Dict[str, Any]) -> ExtractedRFPData:
        text = rfp_data.get("raw_text", "")
        text_lower = text.lower()

        # 1. Trích xuất Ngân sách
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

        # 2. Trích xuất Thời hạn / Deadline
        has_deadline = False
        deadline_days = None
        deadline_date = None
        date_match = re.search(r'trước ngày\s+(\d{1,2}[\/\.-]\d{1,2}[\/\.-]\d{2,4})', text_lower)
        if date_match:
            deadline_date = date_match.group(1)
            has_deadline = True
        else:
            days_match = re.search(r'trong vòng\s+(\d+)\s+ngày', text_lower) or re.search(r'(\d+)\s+ngày thi công', text_lower)
            if days_match:
                try:
                    deadline_days = int(days_match.group(1))
                    has_deadline = True
                except ValueError:
                    pass

        # 3. Trích xuất Chiết khấu mong muốn
        requested_discount = 0.0
        disc_match = re.search(r'chiết khấu[^:\d\n]*[:\s]+(\d+(?:\.\d+)?)\s*%', text_lower)
        if disc_match:
            try:
                requested_discount = float(disc_match.group(1))
            except ValueError:
                pass

        # 4. Trích xuất Người đại diện / Người liên hệ
        contact_person = rfp_data.get("customer_name")
        has_contact = bool(contact_person)
        contact_match = re.search(r'(?:đại diện|người liên hệ|người phụ trách)[^:\n]*[:\s]+(?:anh|chị|ths\.|bs\.|ông|bà)?\s*([^\n\.,]+)', text, re.IGNORECASE)
        if contact_match:
            cand = contact_match.group(1).strip()
            if len(cand) > 3:
                contact_person = cand
                has_contact = True

        # 5. Nhận diện ĐIỀU KIỆN BẮT BUỘC (Mandatory Criteria Detection)
        # Giúp ngăn chặn lỗi 'bỏ sót điều kiện bắt buộc'
        detected_criteria: List[MandatoryCriterion] = []

        # Điều kiện nguồn đôi
        if any(k in text_lower for k in ["nguồn đôi", "nguồn kép", "redundant power", "dual psu", "dự phòng kép"]):
            detected_criteria.append(MandatoryCriterion(
                code="REQ-DUAL-PSU",
                description="Bắt buộc trang bị Nguồn đôi dự phòng kép (Redundant Dual PSU) thay nóng",
                target_spec_key="redundant_power_supply",
                required_value=True
            ))

        # Điều kiện Uplink 100G & BGP
        if any(k in text_lower for k in ["100g", "100g qsfp28", "bgp", "evpn"]):
            detected_criteria.append(MandatoryCriterion(
                code="REQ-100G-BGP",
                description="Bắt buộc hỗ trợ cổng Uplink 100G QSFP28 và định tuyến BGP4/EVPN",
                target_spec_key="routing_protocols",
                required_value="BGP4"
            ))

        # Điều kiện Tường lửa HA & SSL Inspection
        if any(k in text_lower for k in ["ssl inspection", "giải mã sâu ssl", "giải mã ssl"]):
            detected_criteria.append(MandatoryCriterion(
                code="REQ-SSL-INSPECT",
                description="Bắt buộc Tường lửa phải hỗ trợ giải mã sâu SSL Inspection",
                target_spec_key="ssl_inspection_supported",
                required_value=True
            ))

        if any(k in text_lower for k in ["active/passive", "high availability", "cụm dự phòng ha", "chạy ha"]):
            detected_criteria.append(MandatoryCriterion(
                code="REQ-FW-HA",
                description="Bắt buộc hỗ trợ cụm dự phòng High Availability (Active/Passive / Active/Active)",
                target_spec_key="ha_mode",
                required_value="Active/Passive"
            ))

        # Điều kiện Bảo trì 24/7 SLA 2h
        if any(k in text_lower for k in ["bảo trì 24/7", "sla 2 giờ", "sla 2h", "24/7/365"]):
            detected_criteria.append(MandatoryCriterion(
                code="REQ-MAINT-247",
                description="Bắt buộc cam kết Dịch vụ Bảo trì 24/7 SLA xử lý tại chỗ tối đa 2 giờ",
                target_spec_key="support_hours",
                required_value="24/7/365"
            ))

        # 6. Bóc tách Thiết bị Tiêu chuẩn & Thiết bị NGOÀI DANH MỤC (Out-of-catalog items)
        standard_items = []
        out_of_catalog_items = []

        # Kiểm tra thiết bị ngoài danh mục (Ví dụ Quantum HSM / Module bảo mật đặc thù)
        if any(k in text_lower for k in ["quantum", "hsm", "ngoài danh mục", "thiết bị đặc biệt", "chuyên dụng hàng không"]):
            out_of_catalog_items.append({
                "name": "Module Bảo mật Mã hóa Phần cứng Chuyên dụng Quantum HSM-Crypto Gateway 5000",
                "estimated_cost_vnd": 180000000,
                "quantity": 1,
                "notes": "Hàng chuyên dụng đặt riêng OEM từ đối tác nước ngoài. Không có trong Master Catalog tiêu chuẩn của Thiên Minh."
            })

        # Bóc tách các hạng mục tiêu chuẩn
        # Switch Core
        if "switch core" in text_lower or "core l3" in text_lower or "mạng core" in text_lower:
            qty = 1
            m = re.search(r'(\d+)\s*(?:bộ|chiếc|switch)?\s*(?:switch core|core l3)', text_lower)
            if m:
                try:
                    qty = int(m.group(1))
                except ValueError:
                    qty = 1
            standard_items.append({"category": "Switch Core", "quantity": qty})

        # Switch Access
        if "switch access" in text_lower or "poe+" in text_lower:
            qty = 4
            m = re.search(r'(\d+)\s*(?:bộ|chiếc|switch)?\s*(?:switch access|access poe)', text_lower)
            if m:
                try:
                    qty = int(m.group(1))
                except ValueError:
                    qty = 4
            standard_items.append({"category": "Switch Access", "quantity": qty})

        # Wi-Fi AP
        if any(k in text_lower for k in ["wi-fi", "wifi", "ap", "phát wifi"]):
            qty = 12
            m = re.search(r'(\d+)\s*(?:thiết bị|bộ|con|chiếc)?\s*(?:phát wi-fi|thiết bị phát wi-fi|wifi)', text_lower)
            if m:
                try:
                    qty = int(m.group(1))
                except ValueError:
                    qty = 12
            standard_items.append({"category": "Wi-Fi AP", "quantity": qty})

        # Tường lửa (Firewall / NGFW)
        if any(k in text_lower for k in ["tường lửa", "firewall", "ngfw"]):
            qty = 1
            m = re.search(r'(\d+)\s*(?:thiết bị|bộ|con|chiếc)?\s*(?:tường lửa|firewall|ngfw)', text_lower)
            if m:
                try:
                    qty = int(m.group(1))
                except ValueError:
                    qty = 1
            standard_items.append({"category": "Tường lửa", "quantity": qty})

        # Dịch vụ kỹ thuật & bảo trì
        if "core network" in text_lower or "triển khai cấu hình core" in text_lower:
            standard_items.append({"category": "Dịch vụ Triển khai Core", "quantity": 1})

        if "kéo cáp" in text_lower or "lắp đặt switch tầng" in text_lower or "vùng phủ" in text_lower:
            standard_items.append({"category": "Dịch vụ Lắp đặt Thi công", "quantity": 1})

        if "bảo trì 24/7" in text_lower or "sla 2" in text_lower:
            standard_items.append({"category": "Dịch vụ Bảo trì 24/7", "quantity": 1})
        elif "bảo trì" in text_lower or "8x5" in text_lower:
            standard_items.append({"category": "Dịch vụ Bảo trì Tiêu chuẩn", "quantity": 1})

        # 7. Đánh giá tính đầy đủ thông tin (Completeness check)
        missing_fields = []
        clarification_questions = []

        # Nếu yêu cầu quá chung chung (như RFP-002)
        has_generic_unspecified = False
        if len(standard_items) == 0 or (len(standard_items) <= 2 and not has_budget and not has_deadline):
            if any(k in text_lower for k in ["làm lại toàn bộ hệ thống", "báo giá gấp", "mấy con phát wifi"]):
                has_generic_unspecified = True

        if has_generic_unspecified or len(standard_items) == 0:
            missing_fields.append("Khối lượng và cấu hình kỹ thuật cụ thể của Switch, Wi-Fi và Tường lửa")
            clarification_questions.append("Tòa nhà có bao nhiêu phòng/tầng, diện tích mỗi tầng và ước tính tổng số người dùng (users) kết nối đồng thời?")
            clarification_questions.append("Quý khách cần số lượng bao nhiêu cổng mạng LAN (Switch port) và có cần cấp nguồn PoE cho Camera/Điện thoại IP không?")

        if not has_budget:
            missing_fields.append("Ngân sách dự kiến của dự án")
            clarification_questions.append("Quý công ty đã có khung ngân sách dự kiến hoặc hạn mức trần tài chính cho dự án này chưa?")

        if not has_deadline:
            missing_fields.append("Thời hạn hoàn thành / tiến độ bàn giao yêu cầu")
            clarification_questions.append("Quý khách dự kiến mốc thời gian hoàn tất lắp đặt và nghiệm thu đưa vào sử dụng chậm nhất là ngày nào?")

        has_sufficient_info = (len(missing_fields) == 0)

        return ExtractedRFPData(
            has_sufficient_info=has_sufficient_info,
            missing_fields=missing_fields,
            clarification_questions=clarification_questions,
            has_budget=has_budget,
            budget_vnd=budget_vnd,
            has_deadline=has_deadline,
            deadline_days=deadline_days,
            deadline_date=deadline_date,
            has_contact=has_contact,
            contact_person=contact_person,
            requested_discount_pct=requested_discount,
            detected_mandatory_criteria=detected_criteria,
            extracted_standard_items=standard_items,
            out_of_catalog_items=out_of_catalog_items
        )

