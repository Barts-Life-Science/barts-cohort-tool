import React, { useState } from "react";
import { AsyncTypeahead } from "react-bootstrap-typeahead";
import Form from "react-bootstrap/Form";
import Button from "react-bootstrap/Button";

const SnomedSearch = (args) => {
  const [code, setCode] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [options, setOptions] = useState([]);
  const [codeStartDate, setCodeStartDate] = useState("");
  const [codeEndDate, setCodeEndDate] = useState("");

  const invalidDateRange =
    codeStartDate &&
    codeEndDate &&
    new Date(codeStartDate) > new Date(codeEndDate);

  // --------------------------------------------------
  // Search SNOMED
  // --------------------------------------------------
  const handleSearch = (query) => {
    setIsLoading(true);

    fetch(`/api/snomed/search?ecl=<<${args.target_code}&term=${query}`)
      .then((response) => response.json())
      .then((data) => {
        const options = (data.expansion?.contains || []).map((item) => ({
          ...item,

          // Ontoserver normally only provides inactive=true.
          // If inactive is missing, consider the concept active.
          inactive: item.inactive === true,
        }));

        setOptions(options);
        setIsLoading(false);
      })
      .catch((error) => {
        console.error("Error fetching SNOMED terms:", error);
        setOptions([]);
        setIsLoading(false);
      });
  };

  // --------------------------------------------------
  // Add selected SNOMED code
  // --------------------------------------------------
  const addCode = () => {
    if (code.length !== 1) {
      alert("Please select one SNOMED term first.");
      return;
    }

    if (invalidDateRange) {
      return;
    }

    const selectedItem = code[0];
    const selectedCode = String(selectedItem.code);

    fetch(
      `/api/snomed/count-descendants-and-self?code=${selectedItem.code}`
    )
      .then((response) => response.json())
      .then((data) => {
        const count = data.expansion?.total || 0;

        // --------------------------------------------------
        // Create details for primary + child + inactive codes
        // --------------------------------------------------
        let codesWithDetails =
          data.expansion?.contains?.map((item) => ({
            code: item.code,
            display: item.display,
            count: count,

            // Inactive takes priority over primary/child
            codeType:
              item.inactive === true
                ? "Not active"
                : String(item.code) === selectedCode
                  ? "Primary code"
                  : "Child code",

            timeFrame: {
              start: codeStartDate,
              end: codeEndDate,
            },
          })) || [];

        // --------------------------------------------------
        // If primary code wasn't returned in the expansion,
        // add it manually.
        // --------------------------------------------------
        if (
          !codesWithDetails.some(
            (item) => String(item.code) === selectedCode
          )
        ) {
          codesWithDetails = [
            {
              code: selectedItem.code,
              display: selectedItem.display,
              count: count,

              codeType:
                selectedItem.inactive === true
                  ? "Not active"
                  : "Primary code",

              timeFrame: {
                start: codeStartDate,
                end: codeEndDate,
              },
            },
            ...codesWithDetails,
          ];
        }

        // --------------------------------------------------
        // Send selection back to parent component
        // --------------------------------------------------
        if (args.onSelect) {
          args.onSelect({
            code: code,
            display: selectedItem.display,
            count: count,
            codesWithDetails: codesWithDetails,
            timeFrame: {
              start: codeStartDate,
              end: codeEndDate,
            },
          });
        }

        // Reset fields
        setCode([]);
        setCodeStartDate("");
        setCodeEndDate("");
      })
      .catch((error) => {
        console.error("Error fetching child codes:", error);
      });
  };

  return (
    <div>
      <Form.Group className="mb-1">
        <p style={{ margin: 0, fontWeight: "bold" }}>
          {args.label}
        </p>

        <p style={{ margin: 0 }}>
          <i>Start typing to search and add SNOMED terms.</i>
        </p>

        <p style={{ margin: 0 }}>
          <i>
            Select the term, choose the optional date range, then click Add.
          </i>
        </p>

        <p style={{ margin: 0 }}>
          <i>Child codes are automatically included.</i>
        </p>

        <div
          style={{
            display: "flex",
            gap: "10px",
            alignItems: "end",
            width: "100%",
            flexWrap: "wrap",
          }}
        >
          <div style={{ width: "500px" }}>
            <AsyncTypeahead
              id={args.label}

              // Inactive concepts are still shown,
              // but clearly labelled.
              labelKey={(option) =>
                option.inactive === true
                  ? `${option.display} (Not active)`
                  : option.display
              }

              options={options}
              isLoading={isLoading}
              onSearch={handleSearch}
              placeholder="Search for something..."
              selected={code}
              onChange={setCode}
              useCache={false}
              filterBy={() => true}
            />
          </div>

          <Form.Group style={{ width: "320px" }}>
            <Form.Label>From</Form.Label>

            <Form.Control
              type="date"
              value={codeStartDate}
              onChange={(e) =>
                setCodeStartDate(e.target.value)
              }
            />
          </Form.Group>

          <Form.Group style={{ width: "320px" }}>
            <Form.Label>To</Form.Label>

            <Form.Control
              type="date"
              value={codeEndDate}
              onChange={(e) =>
                setCodeEndDate(e.target.value)
              }
            />
          </Form.Group>

          {invalidDateRange && (
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

          <Button
            variant="outline-primary"
            onClick={addCode}
            disabled={
              code.length !== 1 ||
              invalidDateRange
            }
            style={{
              height: "38px",
              width: "90px",
            }}
          >
            Add
          </Button>
        </div>

        <p
          style={{
            fontSize: "0.7em",
            marginTop: "5px",
          }}
        >
          If the SNOMED terms are not loading, please refresh the page or try
          again in about five minutes. If the issue persists, please contact
          the Barts Life Sciences team using the email provided above.
        </p>
      </Form.Group>
    </div>
  );
};

export default SnomedSearch;