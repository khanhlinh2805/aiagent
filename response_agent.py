from typing import Optional
from models.schemas import (
    CustomerRequestInput,
    CompletenessCheck,
    OpportunityRecord,
    QuotationSummary,
    ApprovalDocket,
    ResponseDraft
)

class ResponseAgent:
    """
    Agent soạn thảo Bản nháp phản hồi khách hàng (Customer Draft Response)
    và chuẩn bị kết thúc luồng với cơ chế Cập nhật & Theo dõi.
    """
    def generate_draft(
        self,
        request: CustomerRequestInput,
        completeness: CompletenessCheck,
        opportunity: OpportunityRecord,
        quotation: Optional[QuotationSummary] = None,
        approval: Optional[ApprovalDocket] = None
    ) -> ResponseDraft:
        
        # Trường hợp 1: Thiếu thông tin -> Soạn email yêu cầu KH làm rõ / bổ sung
        if not completeness.has_sufficient_info:
            subject = f"[Minh An Co.] Phản hồi yêu cầu tư vấn giải pháp CNTT - {request.customer_company}"
            
            body = f"""Kính gửi Quý khách {request.customer_name} / {request.customer_company},

Lời đầu tiên, Công ty Cổ phần Công nghệ Minh An xin trân trọng cảm ơn Quý khách đã quan tâm và gửi yêu cầu tư vấn giải pháp thiết bị & dịch vụ công nghệ đến chúng tôi.

Để đội ngũ kỹ sư giải pháp của Minh An có thể thẩm định chính xác cấu hình, kiểm tra năng lực tồn kho tức thời và gửi đến Quý công ty bảng báo giá tối ưu nhất, kính đề nghị Quý khách hỗ trợ làm rõ một số nội dung sau:

{chr(10).join(f"- {q}" for q in completeness.clarification_questions)}

Ngay khi nhận được các thông tin bổ sung trên, Minh An cam kết sẽ phát hành Hồ sơ Đề xuất kỹ thuật và Bảng báo giá chi tiết trong vòng 04 giờ làm việc.

Nếu cần trao đổi trực tiếp, Quý khách vui lòng liên hệ Bộ phận Kinh doanh Minh An qua Hotline: (024) 7300-8888 hoặc phản hồi trực tiếp email này.

Kính chúc Quý công ty luôn phát triển và thành công!

Trân trọng,
---
Bộ phận Tư vấn Giải pháp B2B
CÔNG TY CỔ PHẦN CÔNG NGHỆ MINH AN
Địa chỉ: Tầng 8, Tòa nhà Công nghệ Minh An, Cầu Giấy, Hà Nội
Hotline: (024) 7300-8888 | Email: sales@minhan.com.vn | Website: https://minhan.com.vn
"""
            return ResponseDraft(
                action_type="CLARIFICATION_EMAIL",
                recipient_email=request.customer_email,
                recipient_name=request.customer_name,
                cc=["sales@minhan.com.vn"],
                subject=subject,
                body_markdown=body
            )

        # Trường hợp 2: Đủ thông tin -> Soạn email Dự thảo đề xuất & Báo giá chính thức
        rep_name = opportunity.assigned_rep.name if opportunity.assigned_rep else "Đội ngũ Kinh doanh B2B"
        rep_email = opportunity.assigned_rep.email if opportunity.assigned_rep else "sales@minhan.com.vn"

        subject = f"[Minh An Co.] Báo giá & Dự thảo đề xuất kỹ thuật [{quotation.quote_id}] - {request.customer_company}"

        # Bảng markdown chi tiết sản phẩm
        table_rows = []
        for idx, it in enumerate(quotation.items, 1):
            table_rows.append(
                f"| {idx} | {it.product_name} | {it.sku} | {it.quantity} {it.unit} | {it.unit_price_vnd:,.0f} | {it.discount_pct:.1f}% | {it.line_total_vnd:,.0f} | {it.notes} |"
            )
        table_md = (
            "| STT | Tên hàng hóa / Dịch vụ | Mã SKU | Số lượng | Đơn giá niêm yết (VNĐ) | CK (%) | Thành tiền (VNĐ) | Tình trạng tồn kho & SLA |\n"
            "|---|---|---|:---:|:---:|:---:|:---:|---|\n"
            + "\n".join(table_rows)
        )

        approval_note = ""
        if approval and approval.requires_manager_approval:
            approval_note = f"\n> **Ghi chú nội bộ:** Báo giá này đã được trình Trưởng phòng Kinh doanh ({approval.manager_name}) phê duyệt do: {'; '.join(approval.trigger_reasons)}.\n"

        lead_time_commitment = ""
        if quotation.lead_time_status == "CONFLICT":
            lead_time_commitment = (
                f"**Kế hoạch bàn giao & Lưu ý tiến độ:**\n"
                f"- Theo yêu cầu của Quý khách: {quotation.customer_requested_lead_time_days} ngày.\n"
                f"- Khảo sát thực tế tồn kho & kỹ thuật: Minh An đáp ứng tiêu chuẩn trong **{quotation.required_lead_time_days} ngày làm việc**.\n"
                f"- *Phương án đề xuất linh hoạt:* Minh An có thể tiến hành bàn giao trước các thiết bị sẵn có trong kho (Switch/AP) trong vòng 2 ngày để phục vụ đi dây mạng trước, và bàn giao thiết bị nhập khẩu ngay khi thông quan để đảm bảo tiến độ chung cho Quý khách."
            )
        else:
            lead_time_commitment = (
                f"**Cam kết tiến độ bàn giao & triển khai:**\n"
                f"- Toàn bộ thiết bị và dịch vụ sẽ được hoàn tất bàn giao trong vòng **{quotation.required_lead_time_days} ngày làm việc** kể từ ngày hai bên ký kết hợp đồng và xác nhận đơn hàng."
            )

        body = f"""Kính gửi Quý khách {request.customer_name} / {request.customer_company},

Công ty Cổ phần Công nghệ Minh An xin gửi lời chào trân trọng và chân thành cảm ơn Quý khách đã tin tưởng lựa chọn Minh An làm đối tác cung cấp thiết bị và giải pháp công nghệ.

Căn cứ vào yêu cầu từ Quý công ty, chúng tôi trân trọng gửi tới Quý khách Bảng báo giá chi tiết và Phương án triển khai số **{quotation.quote_id}** như sau:

### 1. BẢNG BÁO GIÁ CHI TIẾT
{table_md}

### 2. TỔNG HỢP GIÁ TRỊ VÀ CHÍNH SÁCH THƯƠNG MẠI
- **Tổng giá trị niêm yết (chưa VAT):** {quotation.gross_subtotal_vnd:,.0f} VNĐ
- **Tổng giá trị chiết khấu thương mại:** -{quotation.total_discount_vnd:,.0f} VNĐ
- **Giá trị sau chiết khấu (chưa VAT):** {quotation.net_before_vat_vnd:,.0f} VNĐ
- **Thuế giá trị gia tăng (VAT 10%):** {quotation.vat_amount_vnd:,.0f} VNĐ
- **TỔNG CỘNG THANH TOÁN (ĐÃ GỒM VAT):** **{quotation.grand_total_vnd:,.0f} VNĐ**

*(Bằng chữ: Việt Nam Đồng)*

**Đối chiếu ngân sách dự kiến:**
{quotation.budget_comparison}

### 3. TIẾN ĐỘ & PHƯƠNG ÁN TRIỂN KHAI
{lead_time_commitment}

### 4. ĐIỀU KHOẢN THƯƠNG MẠI
- **Hiệu lực báo giá:** {quotation.validity_days} ngày kể từ ngày phát hành ({quotation.created_date}).
- **Bảo hành:** Theo tiêu chuẩn chính hãng của nhà sản xuất (Dell, Cisco, Fortinet, Aruba, Lenovo) và cam kết hỗ trợ kỹ thuật 24/7 từ Minh An.
- **Phương thức thanh toán:** Chuyển khoản ngân hàng (Tạm ứng 30% khi ký hợp đồng, 70% sau khi nghiệm thu bàn giao).

{approval_note}
Kính mong Quý khách xem xét phương án trên. Tôi là **{rep_name}** - Chuyên viên phụ trách trực tiếp tài khoản của Quý công ty, sẽ liên hệ lại với Quý khách trong ngày hôm nay để giải đáp thêm thắc mắc và hỗ trợ các thủ tục tiếp theo.

Trân trọng kính thư,

---
**{rep_name}**  
Chuyên viên Tư vấn Giải pháp B2B - Công ty Cổ phần Công nghệ Minh An  
Di động / Zalo: 0912.xxx.888 | Email: {rep_email}  
Website: https://minhan.com.vn | Trụ sở: Tòa nhà Minh An, Cầu Giấy, Hà Nội
"""
        return ResponseDraft(
            action_type="PROPOSAL_EMAIL",
            recipient_email=request.customer_email,
            recipient_name=request.customer_name,
            cc=[rep_email, "nam.nh@minhan.com.vn"],
            subject=subject,
            body_markdown=body
        )

