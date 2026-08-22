package documentai

import (
	"context"
	"fmt"
	"strings"
	"time"

	documentai "cloud.google.com/go/documentai/apiv1"
	"cloud.google.com/go/documentai/apiv1/documentaipb"
	"google.golang.org/api/option"
	"portfolio-copilot/pkg/contracts"
)

// GCPW2Parser implements Parser using Google Cloud Document AI API.
type GCPW2Parser struct {
	client      *documentai.DocumentProcessorClient
	projectID   string
	location    string
	processorID string
}

// NewGCPW2Parser initializes a new GCP Document AI W-2 parser client.
func NewGCPW2Parser(ctx context.Context, projectID, location, processorID string) (*GCPW2Parser, error) {
	if projectID == "" {
		return nil, fmt.Errorf("projectID is required for Document AI")
	}
	if processorID == "" {
		return nil, fmt.Errorf("processorID is required for Document AI")
	}
	if location == "" {
		location = "us"
	}

	endpoint := fmt.Sprintf("%s-documentai.googleapis.com:443", location)
	client, err := documentai.NewDocumentProcessorClient(ctx, option.WithEndpoint(endpoint))
	if err != nil {
		return nil, fmt.Errorf("failed to create documentai client: %w", err)
	}

	return &GCPW2Parser{
		client:      client,
		projectID:   projectID,
		location:    location,
		processorID: processorID,
	}, nil
}

// Close closes the underlying Document AI client.
func (p *GCPW2Parser) Close() error {
	if p.client != nil {
		return p.client.Close()
	}
	return nil
}

// ParseW2 processes raw file bytes with Document AI and normalizes the extracted entities.
func (p *GCPW2Parser) ParseW2(ctx context.Context, fileBytes []byte, mimeType string, filename string, userID string) (*contracts.W2Document, error) {
	if len(fileBytes) == 0 {
		return nil, fmt.Errorf("file bytes cannot be empty")
	}
	if mimeType == "" {
		mimeType = "application/pdf"
	}

	processorName := fmt.Sprintf("projects/%s/locations/%s/processors/%s", p.projectID, p.location, p.processorID)
	req := &documentaipb.ProcessRequest{
		Name: processorName,
		Source: &documentaipb.ProcessRequest_RawDocument{
			RawDocument: &documentaipb.RawDocument{
				Content:  fileBytes,
				MimeType: mimeType,
			},
		},
	}

	resp, err := p.client.ProcessDocument(ctx, req)
	if err != nil {
		return nil, fmt.Errorf("Document AI process request failed: %w", err)
	}

	document := resp.GetDocument()
	if document == nil {
		return nil, fmt.Errorf("empty document returned from Document AI")
	}

	nowStr := time.Now().UTC().Format(time.RFC3339)
	docID := fmt.Sprintf("w2-%d", time.Now().UnixNano())

	w2 := &contracts.W2Document{
		ID:         docID,
		UserID:     userID,
		TaxYear:    ParseTaxYear(filename, time.Now().Year()-1),
		Filename:   filename,
		SizeBytes:  int64(len(fileBytes)),
		UploadedAt: nowStr,
		ParsedAt:   nowStr,
		Status:     contracts.W2StatusSuccess,
		Employer:   &contracts.W2Employer{},
		Employee:   &contracts.W2Employee{},
		RawEntities: make(map[string]string),
	}

	var totalConfidence float64
	var entityCount int

	for _, entity := range document.GetEntities() {
		entityType := strings.ToLower(strings.TrimSpace(entity.GetType()))
		textVal := strings.TrimSpace(entity.GetMentionText())
		confidence := float64(entity.GetConfidence())

		if strings.Contains(entityType, "ssn") || strings.Contains(entityType, "social_security_number") {
			textVal = MaskSSN(textVal)
		}

		if textVal != "" {
			w2.RawEntities[entityType] = textVal
			totalConfidence += confidence
			entityCount++
		}

		switch {
		case strings.Contains(entityType, "wagestipsothercompensation") || strings.Contains(entityType, "box1_wages") || entityType == "wages" || entityType == "w2_box1":
			w2.WagesAndCompensation.Box1WagesTipsOtherCompUSD = ParseCurrency(textVal)
		case strings.Contains(entityType, "federalincometaxwithheld") || strings.Contains(entityType, "box2_federal_income_tax") || entityType == "w2_box2":
			amt := ParseCurrency(textVal)
			w2.WagesAndCompensation.Box2FederalIncomeTaxUSD = &amt
		case strings.Contains(entityType, "socialsecuritywages") || strings.Contains(entityType, "box3_social_security_wages") || entityType == "w2_box3":
			amt := ParseCurrency(textVal)
			w2.WagesAndCompensation.Box3SocialSecurityWagesUSD = &amt
		case strings.Contains(entityType, "socialsecuritytaxwithheld") || strings.Contains(entityType, "box4_social_security_tax") || entityType == "w2_box4":
			amt := ParseCurrency(textVal)
			w2.WagesAndCompensation.Box4SocialSecurityTaxUSD = &amt
		case strings.Contains(entityType, "medicarewagesandtips") || strings.Contains(entityType, "box5_medicare_wages") || entityType == "w2_box5":
			amt := ParseCurrency(textVal)
			w2.WagesAndCompensation.Box5MedicareWagesTipsUSD = &amt
		case strings.Contains(entityType, "medicaretaxwithheld") || strings.Contains(entityType, "box6_medicare_tax") || entityType == "w2_box6":
			amt := ParseCurrency(textVal)
			w2.WagesAndCompensation.Box6MedicareTaxWithheldUSD = &amt
		case entityType == "employername" || entityType == "employer_name" || entityType == "w2_employer_name":
			w2.Employer.Name = textVal
		case entityType == "ein" || strings.Contains(entityType, "employer_id") || entityType == "w2_employer_ein":
			w2.Employer.EIN = textVal
		case entityType == "employeraddress" || entityType == "employer_address" || entityType == "w2_employer_address":
			w2.Employer.Address = textVal
		case entityType == "employeename" || entityType == "employee_name" || entityType == "w2_employee_name":
			w2.Employee.Name = textVal
		case entityType == "ssn" || strings.Contains(entityType, "social_security_number") || entityType == "w2_employee_ssn":
			w2.Employee.SSNMasked = textVal
		case entityType == "employeeaddress" || entityType == "employee_address" || entityType == "w2_employee_address":
			w2.Employee.Address = textVal
		case strings.Contains(entityType, "formyear") || strings.Contains(entityType, "tax_year") || entityType == "w2_tax_year":
			w2.TaxYear = ParseTaxYear(textVal, w2.TaxYear)
		case strings.Contains(entityType, "box12") || entityType == "w2_box12":
			w2.Box12Items = append(w2.Box12Items, parseBox12Entity(entity))
		case strings.Contains(entityType, "retirement_plan") || entityType == "w2_box13_retirement_plan":
			if w2.Box13Checkboxes == nil {
				w2.Box13Checkboxes = &contracts.W2Box13Checkboxes{}
			}
			w2.Box13Checkboxes.RetirementPlan = isAffirmative(textVal)
		}
	}

	// Post-process compound names, addresses, Box 12, Box 14, and state/local taxes
	if w2.Employee.Name == "" {
		first := w2.RawEntities["employeename_firstname"]
		middle := w2.RawEntities["employeename_middlename"]
		last := w2.RawEntities["employeename_lastname"]
		var parts []string
		if first != "" {
			parts = append(parts, first)
		}
		if middle != "" {
			parts = append(parts, middle)
		}
		if last != "" {
			parts = append(parts, last)
		}
		if len(parts) > 0 {
			w2.Employee.Name = strings.Join(parts, " ")
		}
	}

	if w2.Employer.Address == "" {
		street := w2.RawEntities["employeraddress_streetaddressorpostalbox"]
		city := w2.RawEntities["employeraddress_city"]
		state := w2.RawEntities["employeraddress_state"]
		zip := w2.RawEntities["employeraddress_zip"]
		w2.Employer.Address = formatAddress(street, city, state, zip)
	}

	if w2.Employee.Address == "" {
		street := w2.RawEntities["employeeaddress_streetaddressorpostalbox"]
		city := w2.RawEntities["employeeaddress_city"]
		state := w2.RawEntities["employeeaddress_state"]
		zip := w2.RawEntities["employeeaddress_zip"]
		w2.Employee.Address = formatAddress(street, city, state, zip)
	}

	// Box 12 lettered entries (a_code/a_value, b_code/b_value, etc.)
	if len(w2.Box12Items) == 0 {
		for _, letter := range []string{"a", "b", "c", "d"} {
			codeKey := letter + "_code"
			valKey := letter + "_value"
			code := strings.TrimSpace(w2.RawEntities[codeKey])
			valStr := strings.TrimSpace(w2.RawEntities[valKey])
			if code != "" && valStr != "" {
				w2.Box12Items = append(w2.Box12Items, contracts.W2Box12Item{
					Code:        strings.ToUpper(code),
					AmountUSD:   ParseCurrency(valStr),
					Description: getBox12Description(strings.ToUpper(code)),
				})
			}
		}
	}

	// Box 14 Other
	if len(w2.Box14Other) == 0 {
		if otherStr, ok := w2.RawEntities["other"]; ok && otherStr != "" {
			w2.Box14Other = append(w2.Box14Other, contracts.W2OtherItem{
				Label:     otherStr,
				AmountUSD: ParseCurrency(otherStr),
			})
		}
	}

	// State taxes (lines 1..4)
	if len(w2.StateTaxes) == 0 {
		for i := 1; i <= 4; i++ {
			stKey := fmt.Sprintf("state_line%d", i)
			idKey := fmt.Sprintf("employerstateidnumber_line%d", i)
			wagesKey := fmt.Sprintf("statewagestipsetc_line%d", i)
			taxKey := fmt.Sprintf("stateincometax_line%d", i)

			st := w2.RawEntities[stKey]
			if st != "" {
				w2.StateTaxes = append(w2.StateTaxes, contracts.W2StateTax{
					State:             st,
					EmployerStateID:   w2.RawEntities[idKey],
					StateWagesUSD:     ParseCurrency(w2.RawEntities[wagesKey]),
					StateIncomeTaxUSD: ParseCurrency(w2.RawEntities[taxKey]),
				})
			}
		}
	}

	// Local taxes (lines 1..4)
	if len(w2.LocalTaxes) == 0 {
		for i := 1; i <= 4; i++ {
			locKey := fmt.Sprintf("localityname_line%d", i)
			wagesKey := fmt.Sprintf("localwagestipsetc_line%d", i)
			taxKey := fmt.Sprintf("localincometax_line%d", i)

			loc := w2.RawEntities[locKey]
			if loc != "" {
				w2.LocalTaxes = append(w2.LocalTaxes, contracts.W2LocalTax{
					LocalityName:      loc,
					LocalWagesUSD:     ParseCurrency(w2.RawEntities[wagesKey]),
					LocalIncomeTaxUSD: ParseCurrency(w2.RawEntities[taxKey]),
				})
			}
		}
	}

	if entityCount > 0 {
		avgConfidence := totalConfidence / float64(entityCount)
		w2.ConfidenceScore = &avgConfidence
	}

	return w2, nil
}

func formatAddress(street, city, state, zip string) string {
	var parts []string
	if street != "" {
		parts = append(parts, street)
	}
	cityState := strings.TrimSpace(city)
	if state != "" {
		if cityState != "" {
			cityState += ", " + state
		} else {
			cityState = state
		}
	}
	if zip != "" {
		if cityState != "" {
			cityState += " " + zip
		} else {
			cityState = zip
		}
	}
	if cityState != "" {
		parts = append(parts, cityState)
	}
	return strings.Join(parts, ", ")
}

func getBox12Description(code string) string {
	switch code {
	case "D":
		return "401(k) elective deferral"
	case "E":
		return "403(b) elective deferral"
	case "G":
		return "457(b) elective deferral"
	case "W":
		return "Employer HSA contribution"
	case "AA":
		return "Roth 401(k) contribution"
	case "BB":
		return "Roth 403(b) contribution"
	case "DD":
		return "Cost of employer-sponsored health coverage"
	case "C":
		return "Taxable group-term life insurance over $50k"
	case "V":
		return "Income from nonstatutory stock options"
	case "Y":
		return "Section 409A deferrals"
	case "Z":
		return "Section 409A income"
	default:
		return "Other tax benefit / deferral"
	}
}

func parseBox12Entity(entity *documentaipb.Document_Entity) contracts.W2Box12Item {
	text := strings.TrimSpace(entity.GetMentionText())
	item := contracts.W2Box12Item{
		Code:      "",
		AmountUSD: 0,
	}

	for _, prop := range entity.GetProperties() {
		pType := strings.ToLower(prop.GetType())
		pText := strings.TrimSpace(prop.GetMentionText())
		if strings.Contains(pType, "code") {
			item.Code = strings.ToUpper(pText)
		} else if strings.Contains(pType, "amount") {
			item.AmountUSD = ParseCurrency(pText)
		}
	}

	// If code was not extracted via sub-properties, parse from mention text e.g. "D 23000" or "W $4,150"
	if item.Code == "" && text != "" {
		fields := strings.Fields(text)
		if len(fields) >= 1 && len(fields[0]) <= 2 {
			item.Code = strings.ToUpper(fields[0])
			if len(fields) >= 2 && item.AmountUSD == 0 {
				item.AmountUSD = ParseCurrency(fields[1])
			}
		}
	}
	if item.AmountUSD == 0 && text != "" {
		item.AmountUSD = ParseCurrency(text)
	}

	switch item.Code {
	case "D":
		item.Description = "401(k) elective deferral"
	case "E":
		item.Description = "403(b) elective deferral"
	case "G":
		item.Description = "457(b) elective deferral"
	case "W":
		item.Description = "Employer HSA contribution"
	case "AA":
		item.Description = "Roth 401(k) contribution"
	case "BB":
		item.Description = "Roth 403(b) contribution"
	case "DD":
		item.Description = "Cost of employer-sponsored health coverage"
	case "C":
		item.Description = "Taxable group-term life insurance over $50k"
	case "V":
		item.Description = "Income from nonstatutory stock options"
	case "Y":
		item.Description = "Section 409A deferrals"
	case "Z":
		item.Description = "Section 409A income"
	}
	return item
}

func isAffirmative(val string) bool {
	v := strings.ToLower(strings.TrimSpace(val))
	return v == "true" || v == "yes" || v == "x" || v == "1" || v == "checked"
}
