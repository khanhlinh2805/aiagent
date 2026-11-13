from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class MandatoryCriterion(BaseModel):
    code: str
    description: str
    target_spec_key: str
    required_value: Any
    is_met: bool = False
    evidence: str = ""

class ExtractedRFPData(BaseModel):
    has_sufficient_info: bool
    missing_fields: List[str] = Field(default_factory=list)
    clarification_questions: List[str] = Field(default_factory=list)
    has_budget: bool
    budget_vnd: Optional[float] = None
    has_deadline: bool
    deadline_days: Optional[int] = None
    deadline_date: Optional[str] = None
    has_contact: bool
    contact_person: Optional[str] = None
    requested_discount_pct: float = 0.0
    detected_mandatory_criteria: List[MandatoryCriterion] = Field(default_factory=list)
    extracted_standard_items: List[Dict[str, Any]] = Field(default_factory=list)
    out_of_catalog_items: List[Dict[str, Any]] = Field(default_factory=list)

class SolutionMatchingResult(BaseModel):
    matched_sku: str
    solution_name: str
    category: str
    unit: str
    quantity: int
    unit_price_vnd: float
    total_price_vnd: float
    is_fully_compliant: bool
    compliance_status_text: str
    reasons_for_selection: List[str] = Field(default_factory=list)
    rejected_cheaper_options: List[Dict[str, Any]] = Field(default_factory=list)
    technical_specs: Dict[str, Any] = Field(default_factory=dict)

class DeploymentFeasibility(BaseModel):
    status: str  # FEASIBLE, CONFLICT_BLACKOUT, TIGHT
    earliest_available_start_date: str
    total_mandays_required: int
    schedule_analysis: str
    customer_requested_date_or_days: str
    resolution_proposal: str

class ComplianceMatrixRow(BaseModel):
    stt: int
    rfp_requirement: str
    mandatory_criteria: str
    offered_solution: str
    compliance_status: str  # TUÂN THỦ HOÀN TOÀN (COMPLIANT), NGOẠI LỆ / TÙY BIẾN (CUSTOM), KHÔNG ĐẠT (NON-COMPLIANT)
    notes_and_evidence: str

class BidProposalSummary(BaseModel):
    proposal_id: str
    created_date: str
    validity_days: int
    line_items: List[Dict[str, Any]]
    out_of_catalog_items: List[Dict[str, Any]] = Field(default_factory=list)
    gross_subtotal_vnd: float
    total_discount_vnd: float
    net_before_vat_vnd: float
    vat_amount_vnd: float
    grand_total_vnd: float
    budget_analysis: str

class HITLReviewCheck(BaseModel):
    review_status: str  # DAT, CAN_CHINH_SUA
    sales_rep_approved: bool
    technical_lead_approved: bool
    operations_lead_approved: bool
    boundary_checks: List[Dict[str, Any]]
    feedback_notes: List[str] = Field(default_factory=list)

class ApprovalEscalation(BaseModel):
    requires_escalation: bool
    escalation_tier: str  # NONE, SALES_MANAGER, BOARD_OF_DIRECTORS
    approver_name: str
    approver_email: str
    escalation_codes: List[str] = Field(default_factory=list)
    escalation_reasons: List[str] = Field(default_factory=list)
    executive_docket: str

class FinalBidOutput(BaseModel):
    action_type: str  # CLARIFICATION_REQUEST, BID_PROPOSAL_DISPATCH
    recipient: str
    subject: str
    compliance_matrix_markdown: str
    pricing_table_markdown: str
    executive_summary_markdown: str
    full_email_body_markdown: str

class ThienMinhPipelineResult(BaseModel):
    rfp_id: str
    customer_company: str
    workflow_steps: List[Dict[str, Any]]
    extracted_rfp: ExtractedRFPData
    matched_solutions: List[SolutionMatchingResult] = Field(default_factory=list)
    deployment_feasibility: Optional[DeploymentFeasibility] = None
    compliance_matrix: List[ComplianceMatrixRow] = Field(default_factory=list)
    proposal_summary: Optional[BidProposalSummary] = None
    hitl_review: Optional[HITLReviewCheck] = None
    approval_escalation: Optional[ApprovalEscalation] = None
    final_output: FinalBidOutput
    current_status: str

