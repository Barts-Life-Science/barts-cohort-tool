import './App.css';
import React, { useState, useEffect } from 'react';
import { BrowserRouter as Router, Routes, Route, useNavigate } from "react-router-dom";
import { Button, Form, Spinner, Modal } from "react-bootstrap";
import SnomedSearch from "./components/SnomedSearch";
import logo from './assets/Barts_logo.svg';

import { ethnicityOptions, genderOptions, defaultAgeRange } from './config/formOptions';

import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  PieChart, Pie, Cell, ResponsiveContainer
} from 'recharts';

// --- Cohort Form Page ---
function CohortForm() {
  const [demo, setDemo] = useState(false);
  const navigate = useNavigate();
  const [title, setTitle] = useState("");
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const titleRegex = /^[a-zA-Z0-9 _-]+$/;
  const isTitleValid =
    title.trim().length > 4 && titleRegex.test(title);
    
  // Email: standard email validation (simple & safe)
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const isEmailValid =
    email.trim().length > 0 && emailRegex.test(email); 
  const isAllowedEmail =
          isEmailValid &&
          (
            email.trim().toLowerCase().endsWith("@qmul.ac.uk") ||
            email.trim().toLowerCase().endsWith("@nhs.net")
          );
  const [selectedGenders, setSelectedGenders] = useState([]);
  const [minAge, setMinAge] = useState(defaultAgeRange.min);
  const [maxAge, setMaxAge] = useState(defaultAgeRange.max);
  const [ethnicity, setEthnicity] = useState([]);
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");
  const [mustHaveFindings, setMustHaveFindings] = useState([]);
  const [mustNotHaveFindings, setMustNotHaveFindings] = useState([]);
  const [includeChildCodesHave, setIncludeChildCodesHave] = useState(true);
  const [includeChildCodesNotHave, setIncludeChildCodesNotHave] = useState(true);
  const [loading, setLoading] = useState(false);
  const [showConfirm, setShowConfirm] = useState(false);
  const [invalidAdmissionDateRange, setInvalidAdmissionDateRange] = useState(false);
  const noCriteriaSelected =
      selectedGenders.length === 0 &&
      minAge === defaultAgeRange.min &&
      maxAge === defaultAgeRange.max &&
      ethnicity.length === 0 &&
      !startDate &&
      !endDate &&
      mustHaveFindings.length === 0 &&
      mustNotHaveFindings.length === 0;
   


  useEffect(() => {
  fetch("/api/config")
    .then((response) => response.json())
    .then((config) => {
      setDemo(config.demo);

      if (config.demo) {
        document.title = "Patient Cohorting Tool [DEMO]";
      } else {
        document.title = "Patient Cohorting Tool";
      }
    });
}, []);

  const handleEthnicityChange = (code, label) => {
    setEthnicity(prev => {
      const ethnicityItem = { code, display: label };
      return prev.some(item => item.code === code) ? prev.filter(item => item.code !== code) : [...prev, ethnicityItem];
    });
  };

  const handleGenderChange = (code, label) => {
    setSelectedGenders(prev => {
      const genderItem = { code, display: label };
      return prev.some(item => item.code === code) ? prev.filter(item => item.code !== code) : [...prev, genderItem];
    });
  };

  const handleSubmit = (event) => {
          event.preventDefault();
        
          if (!demo && !isAllowedEmail) {
            return;
          }
        
          if (noCriteriaSelected) {
            alert(
              "Please select at least one cohort criterion before submitting your request."
            );
            return;
          }
        
          setShowConfirm(true);
        };
        
        
        const confirmSubmit = async () => {
        
          setShowConfirm(false);
          setLoading(true);
        
          // Helper: keep only the main code if child codes not included
          const processFindings = (findings, includeChildren) => {
            return findings.map(item => {
              if (includeChildren) {
                // keep full object as-is
                return item;
              } else {
                // keep the original structure, but only the main code in codesWithDetails
                const mainCode = Array.isArray(item.code) ? item.code[0] : item.code;
        
                return {
                  ...item,
                  count: item.count,
                  codesWithDetails: mainCode
                    ? [{
                        code: mainCode.code,
                        display: mainCode.display,
                        count: 1
                      }]
                    : [],
                };
              }
            });
          };
        
          const cohortDefinition = {
            title,
            ...(demo ? {} : { email }),
            gender: selectedGenders.length === 0 ? "ALL" : selectedGenders,
            ageRange: { min: minAge, max: maxAge },
            ethnicity: ethnicity.length === 0 ? "ALL" : ethnicity,
            timeRange: {
              ...(startDate && { start: startDate }),
              ...(endDate && { end: endDate }),
            },
            mustHaveFindings: processFindings(
              mustHaveFindings,
              includeChildCodesHave
            ),
            mustNotHaveFindings: processFindings(
              mustNotHaveFindings,
              includeChildCodesNotHave
            ),
          };
        
          try {
        
            const response = await fetch('/api/cohort/select', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(cohortDefinition)
            });
        
            if (!response.ok) {
              throw new Error('Network response was not ok');
            }
        
            if (demo) {
        
              // Demo version: backend returns the results immediately
              const data = await response.json();
        
              sessionStorage.setItem(
                "resultsData",
                JSON.stringify(data)
              );
        
              sessionStorage.setItem(
                "cohortTitle",
                title
              );
        
              window.open("/results", "_blank");
        
            } else {
        
              // Production version: backend processes in the background
              console.log("Setting submitted to true");
              setSubmitted(true);
        
            }
        
          } catch (error) {
        
            console.error('Error:', error);
            alert("There was an error processing your request.");
        
          } finally {
        
            setLoading(false);
        
          }
        };

  return (
    <>
    <div style={{ position: "fixed", top: "20px", right: "20px", zIndex: 1000 }}>
      <img
        src={logo}
        alt="Logo"
        style={{  width: "15vw", minWidth: "80px", maxWidth: "250px", height: "auto" }}
        />
    </div>
    
    <div style={{ margin: '20px 0 20px 20px', maxWidth: '1200px', width: '95%' }}> 
         {submitted && !demo ? (
               <div
                 style={{
                   marginTop: '60px',
                   padding: '30px',
                   display: 'block',
                   maxWidth: '800px',
                   width: '100%',
                   border: '1px solid #b6d4fe',
                   backgroundColor: '#e7f3ff',
                   borderRadius: '8px',
                   color: '#084298',
                   boxSizing: 'border-box',
                 }}
               >
                 {isAllowedEmail ? (
                   <>
                     <h2>Submission received.</h2>
             
                     <p>
                       The results will be sent to the email address provided when ready.
                     </p>
             
                     <p>
                       If you have any issues, feedback, or comments, please email <br />
                       the Barts Life Sciences data science team at<br />
                       <a href="mailto:bartshealth.bls.cohortingtool@nhs.net">
                         bartshealth.bls.cohortingtool@nhs.net
                       </a>
                     </p>
             
                     <p>
                       You can now close this page.
                     </p>
                   </>
                 ) : (
                   <>
                     <h2>Email address not eligible.</h2>
             
                     <p>
                       Requests can be submitted using a QMUL or NHS email address.
                     </p>
             
                     <p>
                       To run a query with any other email address or to get more information, please contact the
                       Barts Life Sciences data science team at&nbsp;
                       <a href="mailto:bartshealth.bls.cohortingtool@nhs.net">
                         bartshealth.bls.cohortingtool@nhs.net
                       </a>
                     </p>
                   </>
                 )}
               </div>
          ) : (
              <div style={{ margin: '20px 0 20px 20px', maxWidth: '1200px', width: '95%' }}>
                  {demo ? (
                      <>
                       
                      <h1>Cohort Builder [DEMO]</h1> 
                      <p style={{ textDecoration: "underline" }}>
                          This is a demonstration version of the app. The results displayed are for illustrative purposes only and are not real clinical data.
                      </p> 
                        
                      <p>Use this form to create a cohort by defining the selection criteria. </p>
                      <p>
                          If you have any issues, feedback, or comments, or if you would like to use the Cohort Builder with real clinical data please email the Barts Life Sciences team at&nbsp;  
                          <a href="mailto:bartshealth.bls.cohortingtool@nhs.net">bartshealth.bls.cohortingtool@nhs.net</a>
                      </p>
                      </>
                    ) : (
                     <>
                        <h1>Cohort Builder</h1>
                        <p
                            style={{
                              fontSize: "1.1rem",
                              fontWeight: "600",
                              marginBottom: "8px",
                            }}
                          >
                           Supporting research cohort discovery and feasibility. </p>
                        <p> Use this form to create a cohort by defining the selection criteria. </p>
                        <p>
                          If you have any issues, feedback, or comments, please email the Barts Life Sciences team at&nbsp;  
                          <a href="mailto:bartshealth.bls.cohortingtool@nhs.net">bartshealth.bls.cohortingtool@nhs.net</a>
                        </p>
                        
                    </>
                    )}
                    
                    
                    <Form
                      onSubmit={handleSubmit}
                      style={{ textAlign: 'left', marginTop: '20px' }}
                    >
                      <Form.Group className="mb-3" controlId="title">
                        <Form.Label style={{ marginBottom: "1px" }}>
                          Cohort Title (Required)
                        </Form.Label>
                
                        <Form.Text
                          className="text-muted"
                          style={{
                            fontSize: "0.85em",
                            display: "block",
                            marginTop: "0.1px",
                            marginBottom: "5px"
                          }}
                        >
                          Title must be at least 5 characters.
                          <br />
                          Only letters, numbers, spaces, hyphens (-) and underscores (_).
                        </Form.Text>
                
                        <Form.Control
                          type="text"
                          placeholder="Title"
                          value={title}
                          onChange={(e) => setTitle(e.target.value)}
                          isInvalid={title.length > 0 && !isTitleValid}
                        />
                
                        <Form.Control.Feedback
                          type="invalid"
                          style={{ marginTop: "2px", whiteSpace: "pre-line" }}
                        >
                          {title.trim().length > 0 && title.trim().length < 5
                            ? "Title must be at least 5 characters."
                            : "Only letters, numbers, spaces, hyphens (-) and underscores (_) are allowed."}
                        </Form.Control.Feedback>
                      </Form.Group>
                
                      {!demo && (
                        <Form.Group className="mb-3" controlId="email">
                          <Form.Label style={{ marginBottom: "1px" }}>
                            Email address (Required)
                          </Form.Label>
                
                          <Form.Text
                            className="text-muted"
                            style={{
                              fontSize: "0.85em",
                              display: "block",
                              marginTop: "0.5px",
                              marginBottom: "5px"
                            }}
                          >
                            The results will be sent to the email address provided once ready.
                          </Form.Text>
                
                          <Form.Control
                            type="email"
                            placeholder="name.surname@nhs.net"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            isInvalid={email.length > 0 && !isEmailValid}
                          />
                
                          <Form.Control.Feedback
                            type="invalid"
                            style={{ marginTop: "2px" }}
                          >
                            Please enter a valid email address.
                          </Form.Control.Feedback>
                        </Form.Group>
                      )}
                
            <Form.Group className="mb-3" controlId="gender">
              <Form.Label>Gender (Optional — if none selected, all categories will be considered)</Form.Label>
              {genderOptions.map(({ code, label }) => (
                <Form.Check
                  key={code}
                  type="checkbox"
                  label={label}
                  checked={selectedGenders.some(item => item.code === code)}
                  onChange={() => handleGenderChange(code, label)}
                />
              ))}
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Minimum Age: {minAge}</Form.Label>
              <Form.Range min={18} max={120} value={minAge} onChange={(e) => setMinAge(Number(e.target.value))} />
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Maximum Age: {maxAge}</Form.Label>
              <Form.Range min={18} max={120} value={maxAge} onChange={(e) => setMaxAge(Number(e.target.value))} />
            </Form.Group>

            <Form.Group className="mb-3" controlId="ethnicity">
              <Form.Label>Ethnicity (Optional — if none selected, all categories will be considered)</Form.Label>
              {ethnicityOptions.map(({ code, label }) => (
                <Form.Check
                  key={code}
                  type="checkbox"
                  label={label}
                  checked={ethnicity.some(item => item.code === code)}
                  onChange={() => handleEthnicityChange(code, label)}
                />
              ))}
            </Form.Group>

            <Form.Group className="mb-3">
              <Form.Label>Admission Time Range (Optional)</Form.Label>
            
              <Form.Control
                  type="date"
                  value={startDate}
                  onChange={(e) => {
                    setStartDate(e.target.value);
                    setInvalidAdmissionDateRange(false);
                  }}
                />
                
                <Form.Control
                  type="date"
                  value={endDate}
                  onChange={(e) => {
                    setEndDate(e.target.value);
                    setInvalidAdmissionDateRange(false);
                  }}
                  onBlur={() => {
                    if (startDate && endDate && startDate > endDate) {
                      setInvalidAdmissionDateRange(true);
                
                      setTimeout(() => {
                        setStartDate("");
                        setEndDate("");
                      }, 1500);
                    }
                  }}
                  style={{ marginTop: "5px" }}
                />
            
              {invalidAdmissionDateRange && (
                <Form.Text
                  className="text-danger"
                  style={{
                    fontSize: "0.85em",
                    display: "block",
                    width: "100%",
                    marginTop: "0px",
                    marginBottom: "5px",
                  }}
                >
                  The start date cannot be later than the end date.
                </Form.Text>
              )}
            </Form.Group>    

            <Form.Group className="mb-3">
              <Form.Label>Must HAVE Finding / Disorder (Optional)</Form.Label>
              <SnomedSearch
                label=""
                target_code="404684003"
                onSelect={(snomedSelection) => {
                  const newCode = snomedSelection.code.code || snomedSelection.code[0]?.code;
                  setMustHaveFindings((prev) =>
                    prev.some(item => (item.code.code || item.code[0]?.code) === newCode)
                      ? prev
                      : [...prev, snomedSelection]
                  );
                }}
              />
              {/*
              <Form.Check
                type="checkbox"
                label="Include child codes (subsumed concepts)"
                checked={includeChildCodesHave}
                onChange={() => setIncludeChildCodesHave(!includeChildCodesHave)}
                style={{ marginTop: "10px" }}
              />
              */}

              {mustHaveFindings.length > 0 && (
                <ul style={{ marginTop: "10px", paddingLeft: "20px" }}>
                  {mustHaveFindings.map((item, index) => {
                    const displayValue = item.code?.[0]?.display;
                    const uniqueId = item.code?.[0]?.code;
                    const count = includeChildCodesHave ? item.count : 1;

                    return (
                      <li key={uniqueId}>
                        <a
                          href={`https://termbrowser.nhs.uk/?perspective=full&conceptId1=${uniqueId}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ textDecoration: "underline", color: "#007bff" }}
                        >
                          {displayValue}
                        </a>{' '}
                        {`(Include ${count} code${count !== 1 ? 's' : ''})`}
                        {item.timeFrame?.start || item.timeFrame?.end ? (
                          <span>
                            {" "}
                            — Timeframe: {item.timeFrame?.start || "Any"} to {item.timeFrame?.end || "Any"}
                          </span>
                        ) : (
                          <span> — Timeframe: Any</span>
                        )}
                        <Button
                          variant="outline-danger"
                          size="sm"
                          onClick={() => setMustHaveFindings(prev => prev.filter((_, i) => i !== index))}
                          style={{ marginLeft: "10px", padding: "0 6px" }}
                        >
                          ❌
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Form.Group>
            
            <Form.Group className="mb-3">
              <Form.Label>Must NOT HAVE Finding / Disorder (Optional)</Form.Label>
              <SnomedSearch
                label=""
                target_code="404684003"
                onSelect={(snomedSelection) => {
                  const newCode = snomedSelection.code.code || snomedSelection.code[0]?.code;
                  setMustNotHaveFindings((prev) =>
                    prev.some(item => (item.code.code || item.code[0]?.code) === newCode)
                      ? prev
                      : [...prev, snomedSelection]
                  );
                }}
              />
              
              {/*
              <Form.Check
                type="checkbox"
                label="Include child codes (subsumed concepts)"
                checked={includeChildCodesNotHave}
                onChange={() => setIncludeChildCodesNotHave(!includeChildCodesNotHave)}
                style={{ marginTop: "10px" }}
              />
              */}

              {mustNotHaveFindings.length > 0 && (
                <ul style={{ marginTop: "10px", paddingLeft: "20px" }}>
                  {mustNotHaveFindings.map((item, index) => {
                    const displayValue = item.code?.[0]?.display;
                    const uniqueId = item.code?.[0]?.code;
                    const count = includeChildCodesNotHave ? item.count : 1;

                    return (
                      <li key={uniqueId}>
                        <a
                          href={`https://termbrowser.nhs.uk/?perspective=full&conceptId1=${uniqueId}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          style={{ textDecoration: "underline", color: "#007bff" }}
                        >
                          {displayValue}
                        </a>{' '}
                        {`(Include ${count} code${count !== 1 ? 's' : ''})`}
                        {item.timeFrame?.start || item.timeFrame?.end ? (
                          <span>
                            {" "}
                            — Timeframe: {item.timeFrame?.start || "Any"} to {item.timeFrame?.end || "Any"}
                          </span>
                        ) : (
                          <span> — Timeframe: Any</span>
                        )}
                        <Button
                          variant="outline-danger"
                          size="sm"
                          onClick={() => setMustNotHaveFindings(prev => prev.filter((_, i) => i !== index))}
                          style={{ marginLeft: "10px", padding: "0 6px" }}
                        >
                          ❌
                        </Button>
                      </li>
                    );
                  })}
                </ul>
              )}
            </Form.Group>

            <Button
              variant="primary"
              type="submit"
              disabled={
                !isTitleValid ||
                (!demo && !isAllowedEmail) ||
                noCriteriaSelected ||
                loading
              }
            >
              {loading ? <Spinner size="sm" /> : "Submit"}
            </Button>
            {(!isTitleValid || (!demo && !isEmailValid)) && (
              <div style={{ fontSize: "0.85rem", color: "#6c757d", marginTop: "5px" }}>
                Please provide a title and a valid email address.
              </div>
            )}
            
            {noCriteriaSelected && (
              <div style={{ fontSize: "0.85rem", color: "#6c757d", marginTop: "3px" }}>
                  Please select at least one cohort criterion (e.g. gender, ethnicity, admission date, or must HAVE finding).
                </div>
            )}
          </Form>
      
          <h5 style={{ marginTop: '25px' }}>Summary of Selected Criteria</h5>
          
          {noCriteriaSelected && (
              <div
                style={{
                  backgroundColor: "#f8d7da",
                  color: "#842029",
                  border: "1px solid #f5c2c7",
                  borderRadius: "6px",
                  padding: "12px",
                  marginBottom: "15px",
                  maxWidth: "700px"
                }}
              >
                <strong>No cohort selection criteria have been specified.</strong>
                <br />
                Please select at least one criterion before submitting your request.
              </div>
            )}
          <ul>
            <li><strong>Title:</strong> {title || "N/A"}</li>
            {!demo && (
                <li><strong>Email:</strong> {email || "N/A"}</li>
            )}
            
            <li><strong>Genders:</strong> {selectedGenders.length === 0 ? "All" : selectedGenders.map((item) => item.display).join(", ")}</li>
            <li><strong>Age Range:</strong> {minAge} - {maxAge}</li>
            <li><strong>Ethnicities:</strong> {ethnicity.length === 0 ? "All" : ethnicity.map((item) => item.display).join(", ")}</li>
            <li><strong>Admission Time Range:</strong> {startDate || endDate ? `${startDate || "Any"} to ${endDate || "Any"}` : "Any"}</li>
            <li>
              <strong>Must Have Findings/Disorders:</strong>{" "}
              {mustHaveFindings.length === 0
                ? "None"
                : mustHaveFindings
                    .map((item) => {
                      const display = item.code?.[0]?.display;
                      const start = item.timeFrame?.start;
                      const end = item.timeFrame?.end;
            
                      if (!display) return null;
            
                      const timeframe =
                        start || end
                          ? ` (Timeframe: ${start || "Any"} to ${end || "Any"})`
                          : " (Timeframe: Any)";
            
                      return `${display}${timeframe}`;
                    })
                    .filter(Boolean)
                    .join(", ")}
            </li>
            
            <li>
              <strong>Must Not Have Findings/Disorders:</strong>{" "}
              {mustNotHaveFindings.length === 0
                ? "None"
                : mustNotHaveFindings
                    .map((item) => {
                      const display = item.code?.[0]?.display;
                      const start = item.timeFrame?.start;
                      const end = item.timeFrame?.end;
            
                      if (!display) return null;
            
                      const timeframe =
                        start || end
                          ? ` (Timeframe: ${start || "Any"} to ${end || "Any"})`
                          : " (Timeframe: Any)";
            
                      return `${display}${timeframe}`;
                    })
                    .filter(Boolean)
                    .join(", ")}
            </li>
          </ul>
        </div>
    )}
    </div>
    <Modal
      show={showConfirm}
      onHide={() => setShowConfirm(false)}
      centered
    >
      <Modal.Header closeButton>
        <Modal.Title>Confirm submission</Modal.Title>
      </Modal.Header>

      <Modal.Body>
        <p>
          <strong>
            Have you reviewed your selected criteria in the summary?
          </strong>
        </p>

        <p style={{ marginBottom: 0 }}>
          Please make sure the criteria are correct before submitting your request.
        </p>
      </Modal.Body>

      <Modal.Footer>
        <Button
          variant="secondary"
          onClick={() => setShowConfirm(false)}
        >
          No, go back and review
        </Button>

        <Button
          variant="primary"
          onClick={confirmSubmit}
        >
          Yes, submit request
        </Button>
      </Modal.Footer>
    </Modal>

    </>
  );
}
// --- Results Page ---
const COLORS = ["#0088FE", "#00C49F", "#FFBB28", "#FF8042", "#AA336A"];

function ResultsPage() {
  const savedResults = sessionStorage.getItem("resultsData");
  const results = savedResults ? JSON.parse(savedResults) : null;

  if (!results) return <p>No results to display.</p>;

  const {
    title,
    total_patients,
    total_records,
    minAge,
    maxAge,
    genderCounts = [],
    ageGroups = [],
    ethnicityCounts = [],
    admissions_by_month = [],
    diagnoses_included = [],
    diagnoses_excluded = [],
    selected_criteria = []
  } = results;
  
  
  const formatTimeframe = (timeFrame) => {
      const start = timeFrame?.start || "Any";
      const end = timeFrame?.end || "Any";
      return `${start} to ${end}`;
    };
    
  // Original criteria selected by the requester
    const criteria = selected_criteria || {};
    
    const selectedGender = criteria.gender;
    const genderLabel = Array.isArray(selectedGender)
      ? selectedGender.map(item => item.display).join(", ") || "All"
      : selectedGender && selectedGender !== "ALL"
        ? selectedGender
        : "All";
    
    const selectedEthnicity = criteria.ethnicity;
    const ethnicityLabel = Array.isArray(selectedEthnicity)
      ? selectedEthnicity.map(item => item.display).join(", ") || "All"
      : selectedEthnicity && selectedEthnicity !== "ALL"
        ? selectedEthnicity
        : "All";
    
    const ageLabel = criteria.ageRange
      ? `${criteria.ageRange.min} - ${criteria.ageRange.max} years`
      : "N/A";
    
    const admissionLabel = formatTimeframe(criteria.timeRange);
    
    
    // Format selected findings/disorders
    const formatSelectedFindings = (findings) => {
      if (!findings || findings.length === 0) {
        return "None";
      }

  return findings.map((item, index) => {
    const mainCode = Array.isArray(item.code)
      ? item.code[0]
      : item.code;

    const display = mainCode?.display || item.display || "Unknown";
    const code = mainCode?.code || "";
    const timeframe = formatTimeframe(item.timeFrame);

    return (
      <div key={index} style={{ marginBottom: "8px" }}>
        <strong>{display}</strong>

        {code && (
          <div style={{ color: "#666", fontSize: "13px" }}>
            SNOMED CT: {code}
          </div>
        )}

        <div style={{ color: "#666", fontSize: "13px" }}>
          Timeframe: {timeframe}
        </div>
      </div>
    );
  });
};

  return (
    <>
    <div style={{ position: "fixed", top: "20px", right: "20px", zIndex: 1000 }}>
        <img
          src={logo}
          alt="Logo"
          style={{  width: "15vw", minWidth: "80px", maxWidth: "250px", height: "auto" }}
        />
    </div>
    <div
          style={{
            margin: "20px 0 20px 20px",
            maxWidth: "1200px",
            width: "95%"
          }}
        >
      <h1>Results for {title || "Untitled"} [DEMO]</h1>
      
              <p
          style={{
            marginTop: "10px",
            color: "#666",
            textDecoration: "underline",
            fontSize: "14px",
          }}
        >
          This is a demonstration version of the app. The results displayed
          are for illustrative purposes only and are not real clinical data.
        </p>
        
        {/* Important information about the results */}
        <div
          style={{
            backgroundColor: "#f4f8fb",
            borderLeft: "5px solid #0072CE",
            padding: "15px 20px",
            marginTop: "25px",
            marginBottom: "25px",
            fontSize: "15px",
            lineHeight: "1.6",
          }}
        >
          <h3
            style={{
              marginTop: 0,
              color: "#003087",
            }}
          >
            Important information about the results
          </h3>
        
          <p>
            <strong>Disclosure control:</strong>{" "}
            Counts are rounded to the nearest 10, or shown as zero where
            the count is less than 10, to protect patient confidentiality.
          </p>
        
          <p>
            <strong>Unique patients:</strong>{" "}
            The total patient count and demographic distributions
            (gender, age and ethnicity) represent unique patients.
            Each patient is counted only once within each demographic
            distribution.
          </p>
        
          <p style={{ marginBottom: 0 }}>
            <strong>Admissions and Findings / Disorders:</strong>{" "}
            Admission counts represent hospital admissions rather than
            unique patients. Finding / Disorder counts represent the
            number of records associated with each specific clinical
            finding or disorder. A patient may have multiple admissions
            and multiple records for the same finding or disorder and
            may therefore be counted more than once across admission
            periods and clinical categories.
          </p>
        </div>
        
      {/* Summary of Selected Criteria */}

        <div
          style={{
            backgroundColor: "#ffffff",
            border: "1px solid #d5dce3",
            borderRadius: "8px",
            padding: "20px",
            marginTop: "25px",
            marginBottom: "30px",
          }}
        >
          <h2
            style={{
              color: "#003087",
              marginTop: 0,
              marginBottom: "10px",
              fontSize: "24px",
            }}
          >
            Summary of Selected Criteria
          </h2>
        
          <p
            style={{
              color: "#666",
              fontSize: "14px",
              marginBottom: "20px",
            }}
          >
            The following criteria were submitted to define the patient cohort.
          </p>
        
          <table
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "15px",
            }}
          >
            <thead>
              <tr>
                <th style={{ width: "35%" }}>Selection criterion</th>
                <th>Selected value</th>
              </tr>
            </thead>
        
            <tbody>
              <tr>
                <td><strong>Gender</strong></td>
                <td>{genderLabel}</td>
              </tr>
        
              <tr>
                <td><strong>Age range</strong></td>
                <td>{ageLabel}</td>
              </tr>
        
              <tr>
                <td><strong>Ethnicity</strong></td>
                <td>{ethnicityLabel}</td>
              </tr>
        
              <tr>
                <td><strong>Admission time range</strong></td>
                <td>{admissionLabel}</td>
              </tr>
        
              <tr>
                <td>
                  <strong>Must HAVE Finding / Disorder</strong>
                </td>
                <td>
                  {formatSelectedFindings(criteria.mustHaveFindings)}
                </td>
              </tr>
        
              <tr>
                <td>
                  <strong>Must NOT HAVE Finding / Disorder</strong>
                </td>
                <td>
                  {formatSelectedFindings(criteria.mustNotHaveFindings)}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        
      {/* Cohort Results heading */}
        <div
          style={{
            backgroundColor: "#003087",
            color: "#ffffff",
            padding: "20px 25px",
            marginTop: "35px",
            marginBottom: "25px",
            borderRadius: "6px",
          }}
        >
          <h2
            style={{
              color: "#ffffff",
              fontSize: "28px",
              margin: 0,
            }}
          >
            Cohort Results
          </h2>
        </div>

      {/* Cohort Summary */}
      <div style={{ marginBottom: "20px" }}>
        <h4>Cohort Summary</h4>
        <p>Total unique patients: {total_patients || 0}</p>
        
        <p>Total records (including multiple records per patient): {total_records || 0}</p>
                
        {!total_patients && (
          <p style={{ color: "red", fontStyle: "italic" }}>No results to display</p>
        )}
      </div>

      {/* Only show charts if patients exist */}
      {total_patients > 0 && (
        <>
          {/* Gender Distribution */}
          {genderCounts.length > 0 && (
            <>
              <h3>Gender distribution (unique patients)</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={genderCounts}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="gender" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="count" fill="#8884d8" />
                </BarChart>
              </ResponsiveContainer>
              <table
                  style={{
                    width: "100%",
                    marginTop: "10px",
                    borderCollapse: "collapse",
                    border: "1px solid black"
                  }}
                >
                  <thead>
                    <tr>
                      <th style={{ border: "1px solid black", padding: "6px" }}>Gender</th>
                      <th style={{ border: "1px solid black", padding: "6px" }}>Count</th>
                    </tr>
                  </thead>
                  <tbody>
                    {genderCounts.map((g) => (
                      <tr key={g.gender}>
                        <td style={{ border: "1px solid black", padding: "6px" }}>{g.gender}</td>
                        <td style={{ border: "1px solid black", padding: "6px" }}>{g.count}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
            </>
          )}
          
          <div style={{ marginTop: "60px" }}></div>
          
          {/* Age Distribution */}
          {ageGroups.length > 0 && (
            <>
              <h3>Age distribution (unique patients)</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={ageGroups}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="range" />
                  <YAxis />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="count" fill="#82ca9d" />
                </BarChart>
              </ResponsiveContainer>
              <table style={{ width: "100%", marginTop: "10px", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th style={{ border: "1px solid black", padding: "6px" }}>Age Range</th>
                    <th style={{ border: "1px solid black", padding: "6px" }}>Count</th>
                  </tr>
                </thead>
                <tbody>
                  {ageGroups.map((a) => (
                    <tr key={a.range}>
                      <td style={{ border: "1px solid black", padding: "6px" }}>{a.range}</td>
                      <td style={{ border: "1px solid black", padding: "6px" }}>{a.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          
          <div style={{ marginTop: "60px" }}></div>
          
          {/* Ethnicity Distribution */}
          {ethnicityCounts.length > 0 && (
            <>
              <h3>Ethnicity distribution (unique patients)</h3>
              <div style={{ display: "flex", justifyContent: "center", marginBottom: "20px" }}>
                <PieChart width={600} height={350}>
                  <Pie
                    data={ethnicityCounts}
                    dataKey="count"
                    nameKey="ethnicity"
                    cx="50%"
                    cy="55%"
                    outerRadius={120}
                    label
                  >
                    {ethnicityCounts.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend verticalAlign="bottom" height={36} />
                </PieChart>
              </div>
              <div style={{ marginTop: "20px" }}>
                  <table style={{ width: "100%", marginTop: "180px", borderCollapse: "collapse" }}>
                    <thead>
                      <tr>
                        <th style={{ border: "1px solid black", padding: "6px" }}>Ethnicity</th>
                        <th style={{ border: "1px solid black", padding: "6px" }}>Count</th>
                      </tr>
                    </thead>
                    <tbody>
                      {ethnicityCounts.map((e) => (
                        <tr key={e.ethnicity}>
                          <td style={{ border: "1px solid black", padding: "6px" }}>{e.ethnicity}</td>
                          <td style={{ border: "1px solid black", padding: "6px" }}>{e.count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
              </div>
            </>
          )}
          
          <div style={{ marginTop: "60px" }}></div>
          
          {/* Admissions by Month-Year */}
          {admissions_by_month.length > 0 && (
            <>
              <h3>Admissions by Month-Year</h3>
              <table style={{ width: "100%", marginTop: "10px", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                    <th style={{ border: "1px solid black", padding: "6px" }}>Month-Year</th>
                    <th style={{ border: "1px solid black", padding: "6px" }}>Admissions</th>
                  </tr>
                </thead>
                <tbody>
                  {admissions_by_month.map((m) => (
                    <tr key={m.monthYear}>
                      <td style={{ border: "1px solid black", padding: "6px" }}>{m.monthYear}</td>
                      <td style={{ border: "1px solid black", padding: "6px" }}>{m.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          
          <div style={{ marginTop: "60px" }}></div>

          {/* Diagnoses Included */}
          {results.diagnoses_included?.length > 0 && (
            <>
              <h3>Diagnoses Included</h3>
              <table style={{ width: "100%", marginTop: "10px", borderCollapse: "collapse" }}>
                <thead>
                  <tr>
                      <th style={{ border: "1px solid black", padding: "6px", width: "40%" }}>Diagnosis</th>
                      <th style={{ border: "1px solid black", padding: "6px", width: "10%" }}>Code type</th>
                      <th style={{ border: "1px solid black", padding: "6px", width: "20%" }}>Code</th>
                      <th style={{ border: "1px solid black", padding: "6px", width: "50%" }}>Timeframe</th>
                      <th style={{ border: "1px solid black", padding: "6px", width: "20%" }}>Count</th>
                  </tr>
                </thead>
                <tbody>
                  {results.diagnoses_included.map((d, i) => (
                    <tr key={`${d.code}-${i}`}>
                      <td style={{ border: "1px solid black", padding: "6px" }}>{d.diagnosis}</td>
                      <td style={{ border: "1px solid black", padding: "6px" }}>{d.codeType || "Child code"}</td>
                      <td style={{ border: "1px solid black", padding: "6px" }}>{d.code}</td>
                      <td style={{ border: "1px solid black", padding: "6px" }}>{formatTimeframe(d.timeFrame)}</td>
                      <td style={{ border: "1px solid black", padding: "6px" }}>{d.count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
          
          <div style={{ marginTop: "60px" }}></div>
          
          {/* Diagnoses Excluded */}
          {results.diagnoses_excluded?.length > 0 && (
            <>
              <h3>Diagnoses Excluded</h3>
                <table style={{ width: "100%", marginTop: "10px", borderCollapse: "collapse" }}>
                  <thead>
                    <tr>
                      <th style={{ border: "1px solid black", padding: "6px", width: "40%" }}>Diagnosis</th>
                      <th style={{ border: "1px solid black", padding: "6px", width: "10%" }}>Code type</th>
                      <th style={{ border: "1px solid black", padding: "6px", width: "20%" }}>Code</th>
                      <th style={{ border: "1px solid black", padding: "6px", width: "50%" }}>Timeframe</th>
                    </tr>
                  </thead>
                  <tbody>
                    {results.diagnoses_excluded.map((d, i) => (
                      <tr key={`${d.code}-${i}`}>
                          <td style={{ border: "1px solid black", padding: "6px" }}>{d.diagnosis}</td>
                          <td style={{ border: "1px solid black", padding: "6px" }}>{d.codeType || "Child code"}</td>
                          <td style={{ border: "1px solid black", padding: "6px" }}>{d.code}</td>
                          <td style={{ border: "1px solid black", padding: "6px" }}>{formatTimeframe(d.timeFrame)}</td>
                        </tr>
                    ))}
                  </tbody>
                </table>
            </>
          )}
        </>
      )}
    </div>
    </>
  );
}

// --- App with Router ---
function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<CohortForm />} />
        <Route path="/results" element={<ResultsPage />} />
      </Routes>
    </Router>
  );
}

export default App;
