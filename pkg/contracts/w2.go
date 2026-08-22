package contracts

// W2Status defines the lifecycle status of an ingested W-2 document.
type W2Status string

const (
	W2StatusSuccess       W2Status = "SUCCESS"
	W2StatusFailed        W2Status = "FAILED"
	W2StatusPendingReview W2Status = "PENDING_REVIEW"
)

// W2Employer represents employer information on IRS Form W-2.
type W2Employer struct {
	Name    string `json:"name,omitempty" firestore:"name,omitempty"`
	EIN     string `json:"ein,omitempty" firestore:"ein,omitempty"`
	Address string `json:"address,omitempty" firestore:"address,omitempty"`
}

// W2Employee represents employee identification and demographics.
type W2Employee struct {
	Name      string `json:"name,omitempty" firestore:"name,omitempty"`
	SSNMasked string `json:"ssn_masked,omitempty" firestore:"ssn_masked,omitempty"`
	Address   string `json:"address,omitempty" firestore:"address,omitempty"`
}

// W2Wages represents federal wages, compensation, and tax withholdings (Boxes 1-11).
type W2Wages struct {
	Box1WagesTipsOtherCompUSD     float64  `json:"box1_wages_tips_other_comp_usd" firestore:"box1_wages_tips_other_comp_usd"`
	Box2FederalIncomeTaxUSD       *float64 `json:"box2_federal_income_tax_withheld_usd,omitempty" firestore:"box2_federal_income_tax_withheld_usd,omitempty"`
	Box3SocialSecurityWagesUSD     *float64 `json:"box3_social_security_wages_usd,omitempty" firestore:"box3_social_security_wages_usd,omitempty"`
	Box4SocialSecurityTaxUSD       *float64 `json:"box4_social_security_tax_withheld_usd,omitempty" firestore:"box4_social_security_tax_withheld_usd,omitempty"`
	Box5MedicareWagesTipsUSD       *float64 `json:"box5_medicare_wages_and_tips_usd,omitempty" firestore:"box5_medicare_wages_and_tips_usd,omitempty"`
	Box6MedicareTaxWithheldUSD     *float64 `json:"box6_medicare_tax_withheld_usd,omitempty" firestore:"box6_medicare_tax_withheld_usd,omitempty"`
	Box7SocialSecurityTipsUSD      *float64 `json:"box7_social_security_tips_usd,omitempty" firestore:"box7_social_security_tips_usd,omitempty"`
	Box8AllocatedTipsUSD           *float64 `json:"box8_allocated_tips_usd,omitempty" firestore:"box8_allocated_tips_usd,omitempty"`
	Box10DependentCareBenefitsUSD  *float64 `json:"box10_dependent_care_benefits_usd,omitempty" firestore:"box10_dependent_care_benefits_usd,omitempty"`
	Box11NonqualifiedPlansUSD      *float64 `json:"box11_nonqualified_plans_usd,omitempty" firestore:"box11_nonqualified_plans_usd,omitempty"`
}

// W2Box12Item represents elective deferrals and benefits reported in Box 12 (e.g. 401k, HSA).
type W2Box12Item struct {
	Code        string  `json:"code" firestore:"code"`
	Description string  `json:"description,omitempty" firestore:"description,omitempty"`
	AmountUSD   float64 `json:"amount_usd" firestore:"amount_usd"`
}

// W2Box13Checkboxes represents statutory checkboxes on IRS Form W-2.
type W2Box13Checkboxes struct {
	StatutoryEmployee bool `json:"statutory_employee,omitempty" firestore:"statutory_employee,omitempty"`
	RetirementPlan    bool `json:"retirement_plan,omitempty" firestore:"retirement_plan,omitempty"`
	ThirdPartySickPay bool `json:"third_party_sick_pay,omitempty" firestore:"third_party_sick_pay,omitempty"`
}

// W2OtherItem represents other miscellaneous items reported in Box 14.
type W2OtherItem struct {
	Label     string  `json:"label" firestore:"label"`
	AmountUSD float64 `json:"amount_usd" firestore:"amount_usd"`
}

// W2StateTax represents state wage and tax withholdings (Boxes 15-17).
type W2StateTax struct {
	State              string  `json:"state" firestore:"state"`
	EmployerStateID    string  `json:"employer_state_id,omitempty" firestore:"employer_state_id,omitempty"`
	StateWagesUSD      float64 `json:"state_wages_usd" firestore:"state_wages_usd"`
	StateIncomeTaxUSD  float64 `json:"state_income_tax_usd" firestore:"state_income_tax_usd"`
}

// W2LocalTax represents local wage and tax withholdings (Boxes 18-20).
type W2LocalTax struct {
	LocalityName      string  `json:"locality_name" firestore:"locality_name"`
	LocalWagesUSD     float64 `json:"local_wages_usd" firestore:"local_wages_usd"`
	LocalIncomeTaxUSD float64 `json:"local_income_tax_usd" firestore:"local_income_tax_usd"`
}

// W2Document represents a structured IRS Form W-2 parsed by Document AI and stored in Firestore.
type W2Document struct {
	ID                   string             `json:"id" firestore:"id"`
	UserID               string             `json:"user_id" firestore:"user_id"`
	TaxYear              int                `json:"tax_year" firestore:"tax_year"`
	DocumentID           string             `json:"document_id,omitempty" firestore:"document_id,omitempty"`
	Filename             string             `json:"filename,omitempty" firestore:"filename,omitempty"`
	SizeBytes            int64              `json:"size_bytes,omitempty" firestore:"size_bytes,omitempty"`
	UploadedAt           string             `json:"uploaded_at" firestore:"uploaded_at"`
	ParsedAt             string             `json:"parsed_at,omitempty" firestore:"parsed_at,omitempty"`
	ConfidenceScore      *float64           `json:"confidence_score,omitempty" firestore:"confidence_score,omitempty"`
	Status               W2Status           `json:"status" firestore:"status"`
	ErrorMessage         *string            `json:"error_message,omitempty" firestore:"error_message,omitempty"`
	Employer             *W2Employer        `json:"employer,omitempty" firestore:"employer,omitempty"`
	Employee             *W2Employee        `json:"employee,omitempty" firestore:"employee,omitempty"`
	WagesAndCompensation W2Wages            `json:"wages_and_compensation" firestore:"wages_and_compensation"`
	Box12Items           []W2Box12Item      `json:"box12_items,omitempty" firestore:"box12_items,omitempty"`
	Box13Checkboxes      *W2Box13Checkboxes `json:"box13_checkboxes,omitempty" firestore:"box13_checkboxes,omitempty"`
	Box14Other           []W2OtherItem      `json:"box14_other,omitempty" firestore:"box14_other,omitempty"`
	StateTaxes           []W2StateTax       `json:"state_taxes,omitempty" firestore:"state_taxes,omitempty"`
	LocalTaxes           []W2LocalTax       `json:"local_taxes,omitempty" firestore:"local_taxes,omitempty"`
	RawEntities          map[string]string  `json:"raw_entities,omitempty" firestore:"raw_entities,omitempty"`
}

// Validate checks basic sanity constraints on a W2Document.
func (w *W2Document) Validate() bool {
	if w.ID == "" || w.UserID == "" || w.TaxYear < 1990 || w.TaxYear > 2100 || w.UploadedAt == "" {
		return false
	}
	if w.WagesAndCompensation.Box1WagesTipsOtherCompUSD < 0 {
		return false
	}
	switch w.Status {
	case W2StatusSuccess, W2StatusFailed, W2StatusPendingReview:
	default:
		return false
	}
	return true
}
