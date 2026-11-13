import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, Optional, List

class GeminiService:
    """
    Dịch vụ tích hợp Google Gemini API cho Công ty Thiên Minh.
    Sử dụng Gemini 3.8 Flash (kèm fallback Gemini 3.5 Flash Lite) để:
    - Hiểu sâu văn bản hồ sơ mời thầu (RFP/RFQ NLP).
    - Soạn thảo thư chào thầu B2B chuyên nghiệp, thuyết phục.
    - Soạn thảo email yêu cầu khách hàng bổ sung thông tin chuẩn mực.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not self.api_key and os.path.exists(".env"):
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("GEMINI_API_KEY="):
                        self.api_key = line.strip().split("=", 1)[1]
                        break

        self.primary_model = os.environ.get("GEMINI_MODEL", "gemini-3.8-flash")
        self.fallback_model = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")
        self.is_active = bool(self.api_key)

    def generate_text(self, prompt: str, system_instruction: Optional[str] = None, timeout: int = 15) -> Optional[str]:
        if not self.is_active:
            return None

        models_to_try = [self.fallback_model, self.primary_model]  # Ưu tiên model phản hồi nhanh flash-lite

        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": self.api_key
            }

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 2048
                }
            }
            if system_instruction:
                payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

            body = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(url, data=body, headers=headers)

            try:
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = json.loads(resp.read().decode())
                    parts = data.get("candidates", [])[0].get("content", {}).get("parts", [])
                    # Lấy text part (bỏ qua thought part nếu có)
                    for p in parts:
                        if "text" in p and not p.get("thought", False):
                            return p["text"].strip()
                    if parts and "text" in parts[0]:
                        return parts[0]["text"].strip()
            except Exception as e:
                # Thử model tiếp theo
                continue

        return None

    def enhance_executive_summary(self, customer_company: str, rfp_summary: str, key_highlights: List[str]) -> str:
        """Sử dụng Gemini để viết tóm tắt giải pháp sắc sảo cho Ban Giám đốc Khách hàng."""
        if not self.is_active:
            return ""

        prompt = f"""Bạn là Giám đốc Giải pháp Công nghệ của Công ty Cổ phần Thiết bị và Dịch vụ Mạng Thiên Minh.
Hãy viết một đoạn Tóm tắt Đề xuất Điều hành (Executive Summary) dài khoảng 3-4 câu, văn phong cực kỳ chuyên nghiệp, đĩnh đạc và thuyết phục gửi tới Ban Lãnh đạo {customer_company}.
Dữ liệu dự án:
- Nhu cầu khách hàng: {rfp_summary}
- Điểm vượt trội của Thiên Minh: {'; '.join(key_highlights)}
Hãy nhấn mạnh cam kết an toàn vận hành, dự phòng lỗi và SLA hỗ trợ kỹ thuật tại chỗ."""

        res = self.generate_text(prompt, system_instruction="Bạn là chuyên gia tư vấn giải pháp mạng doanh nghiệp cao cấp.")
        return res or ""

    def generate_clarification_letter(self, customer_name: str, company: str, questions: List[str]) -> str:
        """Sử dụng Gemini để soạn email xin làm rõ lịch thiệp, chu đáo."""
        if not self.is_active:
            return ""

        prompt = f"""Soạn thảo một email gửi khách hàng {customer_name} thuộc {company}.
Họ vừa gửi yêu cầu chào giá hệ thống mạng nhưng còn thiếu các thông tin kỹ thuật sau:
{chr(10).join(f"- {q}" for q in questions)}

Yêu cầu:
- Thư cảm ơn khách hàng đã quan tâm đến Thiên Minh.
- Giải thích vì sao cần các thông tin trên (để tránh sai sót cấu hình cổng, công suất PoE, và cam kết đúng lịch bàn giao).
- Trình bày các câu hỏi bằng gạch đầu dòng rõ ràng, dễ trả lời.
- Cam kết phát hành Hồ sơ chào giá hoàn chỉnh trong vòng 4 giờ ngay khi nhận đủ thông tin.
- Ký tên: Phòng Tư vấn Dự án Doanh nghiệp - Công ty Thiết bị và Dịch vụ Mạng Thiên Minh."""

        res = self.generate_text(prompt)
        return res or ""

