from typing import List, Dict, Any
from models.thienminh_schemas import (
    ComplianceMatrixRow,
    BidProposalSummary,
    DeploymentFeasibility,
    ExtractedRFPData,
    FinalBidOutput
)
from agents.gemini_service import GeminiService

class ThienMinhProposalSynthesizer:
    """
    Hợp nhất tài liệu:
    Tạo hồ sơ đề xuất, ma trận đáp ứng kỹ thuật (Compliance Matrix) và dự thảo bản chào giá.
    Tích hợp Google Gemini LLM để cá nhân hóa thư chào thầu cho từng khách hàng.
    """
    def __init__(self):
        self.gemini = GeminiService()

    def synthesize_documents(
        self,
        rfp_data: Dict[str, Any],
        extracted: ExtractedRFPData,
        matrix_rows: List[ComplianceMatrixRow],
        proposal: BidProposalSummary,
        feasibility: DeploymentFeasibility
    ) -> FinalBidOutput:
        customer_company = rfp_data.get("customer_company", "Quý Đối tác Doanh nghiệp")
        customer_name = rfp_data.get("customer_name", "Đại diện Quý khách hàng")
        contact_person = extracted.contact_person or customer_name
        rfp_id = rfp_data.get("id", "RFP-000")

        # 1. Bảng Ma trận đáp ứng kỹ thuật (Compliance Matrix)
        matrix_lines = [
            "| STT | Yêu cầu Kỹ thuật trong RFP | Tiêu chí Bắt buộc | Giải pháp Đề xuất Thiên Minh | Mức độ Đáp ứng | Bằng chứng Kỹ thuật & Ghi chú |",
            "|:---:|---|---|---|:---:|---|"
        ]
        for row in matrix_rows:
            matrix_lines.append(
                f"| {row.stt} | {row.rfp_requirement} | {row.mandatory_criteria} | {row.offered_solution} | **{row.compliance_status}** | {row.notes_and_evidence} |"
            )
        compliance_matrix_md = "\n".join(matrix_lines)

        # 2. Bảng chào giá chi tiết (Pricing Table)
        price_lines = [
            "| STT | Tên Giải pháp / Thiết bị | Mã SKU | Số lượng | Đơn giá niêm yết (VNĐ) | Thành tiền (VNĐ) | Ghi chú lựa chọn |",
            "|:---:|---|:---:|:---:|---:|---:|---|"
        ]
        for idx, item in enumerate(proposal.line_items, 1):
            price_lines.append(
                f"| {idx} | {item['name']} | {item['sku']} | {item['quantity']} {item['unit']} | {item['unit_price_vnd']:,.0f} | {item['line_total_vnd']:,.0f} | {item['selection_notes']} |"
            )
        
        # Nếu có thiết bị ngoài danh mục
        if proposal.out_of_catalog_items:
            for out_it in proposal.out_of_catalog_items:
                idx = len(price_lines) - 1
                price_lines.append(
                    f"| {idx} | *[NGOÀI DANH MỤC]* {out_it['name']} | OEM-CUSTOM | {out_it.get('quantity', 1)} Hệ thống | {out_it.get('estimated_cost_vnd', 0):,.0f} | {out_it.get('estimated_cost_vnd', 0):,.0f} | {out_it.get('notes', '')} |"
                )

        price_table_md = "\n".join(price_lines)

        # 3. Tạo Executive Summary qua Gemini nếu có
        highlights = [
            f"Giải pháp tuân thủ 100% tiêu chí kỹ thuật ({len(matrix_rows)} hạng mục)",
            f"Cam kết tiến độ: {feasibility.schedule_analysis[:120]}",
            "Đội ngũ kỹ sư bậc cao CCIE/CCNP trực tiếp chủ trì triển khai"
        ]
        gemini_summary = self.gemini.enhance_executive_summary(customer_company, rfp_data.get("raw_text", "")[:300], highlights)
        
        summary_intro = gemini_summary if gemini_summary else "Thiên Minh cam kết mang lại giải pháp mạng doanh nghiệp tin cậy, vận hành liên tục 24/7 và tuân thủ tuyệt đối các ràng buộc kỹ thuật của hồ sơ mời thầu."

        summary_md = f"""### TỔNG QUAN HỒ SƠ ĐỀ XUẤT DỰ ÁN [{proposal.proposal_id}]
> **Lời ngỏ từ Ban Giải pháp Thiên Minh (AI Generated):**  
> *{summary_intro}*

- **Khách hàng đối tác:** {customer_company}
- **Đại diện phê duyệt:** {contact_person}
- **Tổng giá trị đề xuất (đã gồm VAT 10%):** **{proposal.grand_total_vnd:,.0f} VNĐ**
- **Đánh giá ngân sách:** {proposal.budget_analysis}
- **Tiến độ thi công & Lịch Kỹ thuật:** {feasibility.schedule_analysis}
- **Thời hạn hiệu lực hồ sơ chào giá:** {proposal.validity_days} ngày kể từ ngày phát hành ({proposal.created_date}).
"""

        # 4. Toàn văn Thư chào thầu
        body_md = f"""Kính gửi: **{customer_name}** - {contact_person}
**{customer_company}**

Công ty Cổ phần Thiết bị & Dịch vụ Mạng Thiên Minh xin gửi lời chào trân trọng và lời cảm ơn sâu sắc tới Ban Lãnh đạo Quý công ty đã tin tưởng gửi Thư mời chào giá dự án hạ tầng mạng doanh nghiệp tới Thiên Minh.

{summary_intro}

Căn cứ vào các yêu cầu kỹ thuật và điều kiện ràng buộc trong hồ sơ mời thầu **{rfp_id}**, Thiên Minh trân trọng gửi tới Quý khách hàng Hồ sơ Kỹ thuật & Bảng Chào giá Toàn diện số **{proposal.proposal_id}** với các nội dung chi tiết như sau:

---

### PHẦN I: MA TRẬN ĐÁP ỨNG TIÊU CHÍ KỸ THUẬT (COMPLIANCE MATRIX)
*Cam kết không bỏ sót điều kiện bắt buộc, đảm bảo hệ thống vận hành liên tục và ổn định tuyệt đối:*

{compliance_matrix_md}

---

### PHẦN II: BẢNG GIÁ DỰ TOÁN VÀ ĐIỀU KIỆN THƯƠNG MẠI

{price_table_md}

**TỔNG HỢP GIÁ TRỊ TÀI CHÍNH:**
- **Tổng giá trị thiết bị & dịch vụ danh mục:** {proposal.gross_subtotal_vnd:,.0f} VNĐ
- **Chiết khấu dự án ưu đãi:** -{proposal.total_discount_vnd:,.0f} VNĐ
- **Thiết bị chuyên dụng ngoài danh mục (nếu có):** {sum(it.get('estimated_cost_vnd', 0) for it in proposal.out_of_catalog_items):,.0f} VNĐ
- **Giá trị trước thuế VAT:** {proposal.net_before_vat_vnd:,.0f} VNĐ
- **Thuế giá trị gia tăng (VAT 10%):** {proposal.vat_amount_vnd:,.0f} VNĐ
- 👉 **TỔNG CỘNG GIÁ TRỊ CHÀO GIÁ (ĐÃ GỒM VAT):** **{proposal.grand_total_vnd:,.0f} VNĐ**

*(Bằng chữ: Việt Nam Đồng)*

**Đối chiếu Ngân sách Dự toán:**
> {proposal.budget_analysis}

---

### PHẦN III: KẾ HOẠCH BÀN GIAO & CAM KẾT NĂNG LỰC TRIỂN KHAI
- **Năng lực kỹ thuật:** Đội ngũ Kỹ sư Trưởng sở hữu chứng chỉ quốc tế CCIE/CCNP trực tiếp thiết kế, cấu hình kiểm thử tải trước khi đóng điện.
- **Tiến độ triển khai:** {feasibility.schedule_analysis}
- **Phương án giải quyết:** {feasibility.resolution_proposal}
- **Tiêu chuẩn bảo hành:** Thiết bị bảo hành chính hãng từ 24 đến 36 tháng. Hỗ trợ sự cố khẩn cấp theo gói cam kết SLA.

Chúng tôi rất mong có cơ hội được trình bày chi tiết giải pháp tại trụ sở của Quý công ty.

Trân trọng kính thư,

---
**CÔNG TY CỔ PHẦN THIẾT BỊ VÀ DỊCH VỤ MẠNG THIÊN MINH**  
Trụ sở: Tòa nhà Công nghệ Thiên Minh, Duy Tân, Cầu Giấy, Hà Nội  
Hotline Dự án: (024) 3888-9999 | Email: duan@thienminh.net.vn  
"""

        subject = f"[Thiên Minh] Hồ sơ Đề xuất Kỹ thuật & Bảng Chào giá Dự án [{proposal.proposal_id}] - {customer_company}"

        return FinalBidOutput(
            action_type="BID_PROPOSAL_DISPATCH",
            recipient=rfp_data.get("customer_email", "contact@customer.com"),
            subject=subject,
            compliance_matrix_markdown=compliance_matrix_md,
            pricing_table_markdown=price_table_md,
            executive_summary_markdown=summary_md,
            full_email_body_markdown=body_md
        )
