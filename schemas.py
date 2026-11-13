from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class LineItemDetail(BaseModel):
    sku: str
    product_name: str
    category: str
    unit: str
    quantity: int
    unit_price_vnd: float
    discount_pct: float
    discount_amount_vnd: float
    final_unit_price_vnd: float
    line_total_vnd: float
    on_hand_stock: int
    available_stock: int
    is_in_stock: bool
    item_lead_time_days: int
    notes: Optional[str] = None

class CustomerRequestInput(BaseModel):
    id: str
    customer_name: str
    customer_company: str
    customer_email: str
    received_date: str
    raw_text: str

class CompletenessCheck(BaseModel):
    has_sufficient_info: bool
    missing_items: List[str] = Field(default_factory=list)
    has_budget: bool
    budget_vnd: Optional[float] = None
    has_deadline: bool
    deadline_days: Optional[int] = None
    deadline_date: Optional[str] = None
    has_approver: bool
    approver_name: Optional[str] = None
    has_products: bool
    requested_discount_pct: Optional[float] = None
    extracted_items_summary: List[str] = Field(default_factory=list)
    clarification_questions: List[str] = Field(default_factory=list)

class AssignedSalesRep(BaseModel):
    id: str
    name: str
    email: str
    specialty: List[str]
    current_active_leads: int
    assignment_reason: str

class QuotationSummary(BaseModel):
    quote_id: str
    created_date: str
    validity_days: int
    items: List[LineItemDetail]
    gross_subtotal_vnd: float
    total_discount_vnd: float
    net_before_vat_vnd: float
    vat_rate: float
    vat_amount_vnd: float
    grand_total_vnd: float
    customer_budget_vnd: Optional[float] = None
    budget_comparison: str
    required_lead_time_days: int
    customer_requested_lead_time_days: Optional[int] = None
    lead_time_status: str
    lead_time_explanation: str

class ApprovalDocket(BaseModel):
    requires_manager_approval: bool
    manager_name: str
    manager_email: str
    trigger_codes: List[str] = Field(default_factory=list)
    trigger_reasons: List[str] = Field(default_factory=list)
    status: str
    justification_for_manager: str

class ResponseDraft(BaseModel):
    action_type: str
    recipient_email: str
    recipient_name: str
    cc: List[str] = Field(default_factory=list)
    subject: str
    body_markdown: str

class OpportunityRecord(BaseModel):
    opp_id: str
    created_at: str
    customer_name: str
    customer_company: str
    customer_email: str
    contact_person: str
    assigned_rep: Optional[AssignedSalesRep] = None
    current_stage: str
    estimated_value_vnd: float = 0.0
    sla_response_hours: int = 4
    notes: List[str] = Field(default_factory=list)

class PipelineExecutionResult(BaseModel):
    request_id: str
    workflow_steps: List[Dict[str, Any]]
    completeness: CompletenessCheck
    opportunity_record: Optional[OpportunityRecord] = None
    quotation: Optional[QuotationSummary] = None
    approval: Optional[ApprovalDocket] = None
    response_draft: ResponseDraft
    final_status: str

