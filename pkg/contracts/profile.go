package contracts

// FamilyMember represents a family member or dependent of the user.
type FamilyMember struct {
	Name         string `json:"name" firestore:"name"`
	Relationship string `json:"relationship" firestore:"relationship"`
	Age          int    `json:"age" firestore:"age"`
}

// UserProfile represents user personal, demographic, and financial background details.
type UserProfile struct {
	UserID                  string         `json:"user_id" firestore:"user_id"`
	FullName                string         `json:"full_name,omitempty" firestore:"full_name,omitempty"`
	Email                   string         `json:"email,omitempty" firestore:"email,omitempty"`
	DateOfBirth             string         `json:"date_of_birth,omitempty" firestore:"date_of_birth,omitempty"`
	Age                     int            `json:"age,omitempty" firestore:"age,omitempty"`
	MaritalStatus           string         `json:"marital_status,omitempty" firestore:"marital_status,omitempty"`
	DependentsCount         int            `json:"dependents_count,omitempty" firestore:"dependents_count,omitempty"`
	FamilyMembers           []FamilyMember `json:"family_members,omitempty" firestore:"family_members,omitempty"`
	EmploymentStatus        string         `json:"employment_status,omitempty" firestore:"employment_status,omitempty"`
	Occupation              string         `json:"occupation,omitempty" firestore:"occupation,omitempty"`
	AnnualIncomeUSD         float64        `json:"annual_income_usd,omitempty" firestore:"annual_income_usd,omitempty"`
	TargetRetirementAge     int            `json:"target_retirement_age,omitempty" firestore:"target_retirement_age,omitempty"`
	MonthlyHousingPaymentUSD float64       `json:"monthly_housing_payment_usd,omitempty" firestore:"monthly_housing_payment_usd,omitempty"`
	RiskToleranceNotes      string         `json:"risk_tolerance_notes,omitempty" firestore:"risk_tolerance_notes,omitempty"`
	FinancialGoalsNotes     string         `json:"financial_goals_notes,omitempty" firestore:"financial_goals_notes,omitempty"`
	UpdatedAt               string         `json:"updated_at,omitempty" firestore:"updated_at,omitempty"`
}
