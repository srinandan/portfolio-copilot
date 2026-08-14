package contracts

// CategorySpending represents spending summary for a specific category.
type CategorySpending struct {
	Category          string   `json:"category" firestore:"category"`
	AmountUSD         float64  `json:"amount_usd" firestore:"amount_usd"`
	PercentOfTotal    float64  `json:"percent_of_total" firestore:"percent_of_total"`
	MonthlyAverageUSD *float64 `json:"monthly_average_usd,omitempty" firestore:"monthly_average_usd,omitempty"`
}

// SpendingAnomaly represents a detected spending anomaly in a category.
type SpendingAnomaly struct {
	Category           string  `json:"category" firestore:"category"`
	AmountUSD          float64 `json:"amount_usd" firestore:"amount_usd"`
	TrailingAverageUSD float64 `json:"trailing_average_usd" firestore:"trailing_average_usd"`
	Description        string  `json:"description" firestore:"description"`
	Date               string  `json:"date" firestore:"date"`
}

// SpendingReport represents a comprehensive spending analysis report.
type SpendingReport struct {
	UserID            string             `json:"user_id" firestore:"user_id"`
	TotalIncomeUSD    float64            `json:"total_income_usd" firestore:"total_income_usd"`
	TotalOutflowUSD   float64            `json:"total_outflow_usd" firestore:"total_outflow_usd"`
	SavingsRate       float64            `json:"savings_rate" firestore:"savings_rate"`
	ReserveMonths     float64            `json:"reserve_months" firestore:"reserve_months"`
	CategoryBreakdown []CategorySpending `json:"category_breakdown" firestore:"category_breakdown"`
	Anomalies         []SpendingAnomaly  `json:"anomalies" firestore:"anomalies"`
	NarrativeSummary  string             `json:"narrative_summary" firestore:"narrative_summary"`
}

// DriftBandItem represents asset class allocation status and drift metrics against target bands.
type DriftBandItem struct {
	AssetClass         string  `json:"asset_class" firestore:"asset_class"`
	CurrentPercent     float64 `json:"current_percent" firestore:"current_percent"`
	TargetPercent      float64 `json:"target_percent" firestore:"target_percent"`
	MinPercent         float64 `json:"min_percent" firestore:"min_percent"`
	MaxPercent         float64 `json:"max_percent" firestore:"max_percent"`
	InBand             bool    `json:"in_band" firestore:"in_band"`
	DriftAmountPercent float64 `json:"drift_amount_percent" firestore:"drift_amount_percent"`
}

// DriftReport represents a comprehensive drift analysis report across all target asset classes.
type DriftReport struct {
	AsOf                 string          `json:"as_of" firestore:"as_of"`
	Bands                []DriftBandItem `json:"bands" firestore:"bands"`
	UnclassifiedValueUSD float64         `json:"unclassified_value_usd" firestore:"unclassified_value_usd"`
	RebalanceRecommended bool            `json:"rebalance_recommended" firestore:"rebalance_recommended"`
	HasActiveIPS         bool            `json:"has_active_ips" firestore:"has_active_ips"`
}

// DocumentItem represents uploaded document metadata.
type DocumentItem struct {
	ID            string  `json:"id" firestore:"id"`
	UserID        string  `json:"user_id" firestore:"user_id"`
	Filename      string  `json:"filename" firestore:"filename"`
	AccountType   string  `json:"account_type,omitempty" firestore:"account_type,omitempty"`
	TargetTable   string  `json:"target_table,omitempty" firestore:"target_table,omitempty"`
	SizeBytes     int64   `json:"size_bytes" firestore:"size_bytes"`
	UploadedAt    string  `json:"uploaded_at" firestore:"uploaded_at"`
	Status        string  `json:"status" firestore:"status"`
	RecordsParsed *int    `json:"records_parsed,omitempty" firestore:"records_parsed,omitempty"`
	ErrorMessage  *string `json:"error_message,omitempty" firestore:"error_message,omitempty"`
}
