# -*- coding: utf-8 -*-
"""
Created on Mon May 11 15:35:05 2026

@author: c_piazzese
"""

from fastapi import APIRouter 
from fastapi import BackgroundTasks
from pydantic import BaseModel
from typing import List, Union, Optional
from app.config import settings
import app.services.fhir_client as fhir_client
from fastapi.concurrency import run_in_threadpool
from datetime import datetime
import pandas as pd
import os
import json
from pathlib import Path
import math
import traceback
from app.services.cohort_worker import get_queue
from app.config import settings


# from app.services.report_utils import generate_report
from app.services.email_utils import send_results_email
from app.services.email_utils import generate_html_report
from app.services.cohort_query import run_cohort_query

router = APIRouter()
client = fhir_client.FHIRClient()

@router.get("/config")
def get_config():
    return {
        "demo": settings.demo == "yes"
    }

# Pydantic models
class AgeRange(BaseModel):
    min: int
    max: int

class CodeEntry(BaseModel):
    code: str
    display: Optional[str]

class TimeRange(BaseModel):
    start: Optional[str] = None
    end: Optional[str] = None
    
class CodeDetail(BaseModel):
    code: str
    display: Optional[str]
    count: Optional[int]
    codeType: Optional[str] = None
    timeFrame: Optional[TimeRange] = None

class FindingItem(BaseModel):
    code: List[CodeEntry]
    display: Optional[str]
    count: Optional[int]
    codesWithDetails: Optional[List[CodeDetail]]
    timeFrame: Optional[TimeRange] = None


class CohortDefinition(BaseModel):
    title: str
    email: Optional[str] = None
    gender: Union[str, List[CodeEntry]]
    ageRange: AgeRange
    ethnicity: Union[str, List[CodeEntry]]
    timeRange: Optional[TimeRange]
    mustHaveFindings: Optional[List[FindingItem]]
    mustNotHaveFindings: Optional[List[FindingItem]]

# Helper function to fetch SNOMED display name
def get_snomed_display(code: str) -> str:
    try:
        snomed_display = client.search_snomed(code, "", 1)
        return snomed_display.get('entry', [{}])[0].get('resource', {}).get('display', 'Unknown')
    except Exception as e4:
        print(f"Error fetching SNOMED display for {code}: {e4}")
        return 'Unknown'
    
def anonymise_count(value, threshold=10):
    """
    # Apply disclosure control:
    # - counts < 10 are set to 0
    # - counts >= 10 are rounded to the nearest 10
    """
    
    if value < threshold:
        return 0
    return round(value / 10) * 10



def process_cohort(cohort_definition: CohortDefinition):
    try:
        datetime_mail = datetime.now().strftime("%d %B %Y, %H:%M")
        datetime_title = datetime_mail.replace(",", "").replace(":", "_").replace(" ", "_")

        output_folder = settings.saved_searches
        
        filename = os.path.join(output_folder, f"{cohort_definition.title.replace(' ', '_')}_selected_criteria_{datetime_title}.json")

        # Save definition as JSON
        with open(filename, "w") as f:
            json.dump(cohort_definition.model_dump(), f, indent=4, allow_nan=True)

        # Extract demographics: NHS Data Dictionary codes, matched against cohort.person
        codes_gender = []
        if cohort_definition.gender != 'ALL':
            codes_gender = [entry.code for entry in cohort_definition.gender]
            
        codes_ethnicity = []
        if cohort_definition.ethnicity != 'ALL':
            codes_ethnicity = [entry.code for entry in cohort_definition.ethnicity]

        minAge = cohort_definition.ageRange.min
        maxAge = cohort_definition.ageRange.max
        start_date = cohort_definition.timeRange.start if cohort_definition.timeRange else None
        end_date = cohort_definition.timeRange.end if cohort_definition.timeRange else None

        # Build gender/ethnicity lists
        gender = cohort_definition.gender
        if isinstance(gender, str):
            gender_list = [{"code": gender, "display": gender}]
        else:
            gender_list = [{"code": item.code, "display": item.display} for item in gender]

        ethnicity = cohort_definition.ethnicity
        if isinstance(ethnicity, str):
            ethnicity_list = [{"code": ethnicity, "display": ethnicity}]
        else:
            ethnicity_list = [{"code": item.code, "display": item.display} for item in ethnicity]

        # Must-have & must-not-have codes
        musthaveSnomedCodes = set()
        musthave_filters = []

        if cohort_definition.mustHaveFindings:
            for item in cohort_definition.mustHaveFindings:
                codes = []

                if item.codesWithDetails:
                    for detail in item.codesWithDetails:
                        if detail.code:
                            codes.append(detail.code)
                            musthaveSnomedCodes.add(detail.code)

                if codes:
                    musthave_filters.append({
                        "codes": codes,
                        "start": item.timeFrame.start if item.timeFrame else None,
                        "end": item.timeFrame.end if item.timeFrame else None,
                    })

        mustNOThaveDiagnosisDetails = []
        mustNOThaveSnomedCodes = []
        mustNOT_filters = []

        if cohort_definition.mustNotHaveFindings:
            for item in cohort_definition.mustNotHaveFindings:
                codes = []

                if item.codesWithDetails:
                    for detail in item.codesWithDetails:
                        if detail.code:
                            codes.append(detail.code)
                            mustNOThaveSnomedCodes.append(detail.code)

                        if detail.display:
                            mustNOThaveDiagnosisDetails.append({
                                "code": str(detail.code),
                                "diagnosis": detail.display,
                                "codeType": detail.codeType or "Child code",
                                "timeFrame": {
                                    "start": detail.timeFrame.start if detail.timeFrame else (
                                        item.timeFrame.start if item.timeFrame else None
                                    ),
                                    "end": detail.timeFrame.end if detail.timeFrame else (
                                        item.timeFrame.end if item.timeFrame else None
                                    ),
                                },
                            })

                if codes:
                    mustNOT_filters.append({
                        "codes": codes,
                        "start": item.timeFrame.start if item.timeFrame else None,
                        "end": item.timeFrame.end if item.timeFrame else None,
                    })
                    
        # Query the gold-fed cohort tables (loaded by the SNOMED COHORT BROWSER ADF pipeline).
        # Counts are aggregated in SQL; only the chart data comes back.
        counts = run_cohort_query(
            minAge, maxAge, codes_gender, codes_ethnicity,
            start_date, end_date, musthave_filters, mustNOT_filters,
        )
        final_query = counts["sql"]

        # Saving query 
        filename_query = os.path.join(output_folder, f"{cohort_definition.title.replace(' ', '_')}_final_query_{datetime_title}.json")

        with open(filename_query, "w", encoding="utf-8") as f:
            f.write(final_query)

        total_patients = counts["total_patients"]

        print("Total patients")
        print(total_patients)

        diagnoses_included = []
        # Row-level results are no longer returned: the report only uses the aggregates.
        results_json = []

        # Apply disclosure control: if <10, return 0
        if total_patients < 10:
            total_patients = 0
            total_records = 0
            
            gender_counts, age_groups, ethnicity_counts, admissions_by_month = [], [], [], []
            
            age_min = "NA"
            age_max = "NA"
            
        else:
            
            # approximating to the nearest 10 
            total_patients = round(total_patients / 10) * 10
            total_records = anonymise_count(counts["total_records"])

            gender_counts = [
                {"gender": gender, "count": anonymise_count(n)}
                for gender, n in counts["gender_counts"]
            ]

            # Age groups (bucket by decades); all labels appear even if count is 0
            bins = [18, 30, 40, 50, 60, 70, 80, 90, 100, float("inf")]
            labels = ["18-29","30-39","40-49","50-59","60-69","70-79","80-89","90-99","100+"]
            ages = pd.DataFrame(counts["ages"], columns=["age", "count"])
            ages["range"] = pd.cut(ages["age"], bins=bins, labels=labels, right=False)
            age_groups = (
                ages.groupby("range", observed=False)["count"]
                .sum()
                .reindex(labels, fill_value=0)
                .reset_index()
            )
            age_groups["count"] = age_groups["count"].apply(anonymise_count)
            age_groups = age_groups.to_dict(orient="records")

            ethnicity_counts = [
                {"ethnicity": ethnicity, "count": anonymise_count(n)}
                for ethnicity, n in counts["ethnicity_counts"]
            ]

            # Overall age range
            age_min = int(counts["age_min"]) if counts["age_min"] is not None else "NA"
            age_max = int(counts["age_max"]) if counts["age_max"] is not None else "NA"

            # --- Admissions by Month-Year ---
            admissions_by_month = [
                {"monthYear": month_year, "count": anonymise_count(n)}
                for month_year, n in counts["admissions_by_month"]
            ]

            # --- Diagnoses included --- (condition records per must-have code)
            diagnoses_included = [
                {"code": str(code), "diagnosis": str(code), "count": anonymise_count(n)}
                for code, n in counts["diagnosis_counts"]
            ]

        # Build a set of diagnoses already included
        if diagnoses_included:
            existing_diagnoses = {d["diagnosis"] for d in diagnoses_included}
            
       
        # Build mapping: DISPLAY -> CODE for must-have findings
        # Build mapping: CODE -> DISPLAY
        musthave_code_details = {}
        
        if cohort_definition.mustHaveFindings:
            for item in cohort_definition.mustHaveFindings:
                if item.codesWithDetails:
                    for detail in item.codesWithDetails:
                        if detail.code:
                            code = str(detail.code)
                            musthave_code_details[code] = {
                                "diagnosis": detail.display or code,
                                "codeType": detail.codeType or "Child code",
                                "timeFrame": {
                                    "start": detail.timeFrame.start if detail.timeFrame else (
                                        item.timeFrame.start if item.timeFrame else None
                                    ),
                                    "end": detail.timeFrame.end if detail.timeFrame else (
                                        item.timeFrame.end if item.timeFrame else None
                                    ),
                                },
                            }     
                            
        # print(musthave_code_display)
        
        # Build a new list in the correct order
        ordered_diagnoses = []
        
        for code, detail_info in musthave_code_details.items():
            existing_entry = next(
                (e for e in diagnoses_included if str(e["code"]) == code),
                None
            )
        
            if existing_entry:
                existing_entry["diagnosis"] = detail_info["diagnosis"]
                existing_entry["codeType"] = detail_info["codeType"]
                existing_entry["timeFrame"] = detail_info["timeFrame"]
                ordered_diagnoses.append(existing_entry)
            else:
                ordered_diagnoses.append({
                    "code": code,
                    "diagnosis": detail_info["diagnosis"],
                    "codeType": detail_info["codeType"],
                    "count": 0,
                    "timeFrame": detail_info["timeFrame"],
                })
                
        # Order diagnoses by count (highest first)
        diagnoses_included = sorted(
            ordered_diagnoses,
            key=lambda x: x["count"],
            reverse=True
        )  
        
        # print(admissions_by_month)
        
        def build_timeframe_label(findings):
            if not findings:
                return None
        
            labels = []
        
            for item in findings:
                start = item.timeFrame.start if item.timeFrame else None
                end = item.timeFrame.end if item.timeFrame else None
        
                if start or end:
                    labels.append(f"Timeframe: {start or 'Any'} to {end or 'Any'}")
        
            return "; ".join(labels) if labels else None
        
        if settings.demo == 'yes':
            results_payload = {
                "title": cohort_definition.title,
                "total_patients": int(total_patients),
                "total_records": int(total_records),
                "minAge": age_min,
                "maxAge": age_max,
                "genderCounts": gender_counts,
                "ageGroups": age_groups,
                "ethnicityCounts": ethnicity_counts,
                "admissions_by_month": admissions_by_month,
                "results": results_json,
                "diagnoses_included": build_timeframe_label(cohort_definition.mustHaveFindings),
                "diagnoses_excluded": build_timeframe_label(cohort_definition.mustNotHaveFindings),
                "selected_criteria": cohort_definition.model_dump(),
            }
            
            if musthaveSnomedCodes:
                results_payload["diagnoses_included"] = diagnoses_included
               

            if mustNOThaveSnomedCodes:
                results_payload["diagnoses_excluded"] = mustNOThaveDiagnosisDetails


            def sanitize_for_json(obj):
                """Recursively replace NaN/inf with None in dicts/lists."""
                if isinstance(obj, dict):
                    return {k: sanitize_for_json(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [sanitize_for_json(v) for v in obj]
                elif isinstance(obj, float):
                    if math.isnan(obj) or math.isinf(obj):
                        return None
                return obj

            # Apply to both payloads in one line
            results_payload = sanitize_for_json(results_payload) 
            
            return results_payload
        
        # print(settings.demo)
        if settings.demo == 'no':
            results_payload = {
                "title": cohort_definition.title,
                "email": cohort_definition.email,
                "total_patients": int(total_patients),
                "total_records": int(total_records),
                "minAge": age_min,
                "maxAge": age_max,        
                "genderCounts": gender_counts,
                "ageGroups": age_groups,
                "ethnicityCounts": ethnicity_counts,
                "admissions_by_month": admissions_by_month,
                "results": results_json,
                "date_time_mail": datetime_mail,
                "selected_criteria": cohort_definition.model_dump(),
                }
        
            if musthaveSnomedCodes:
                results_payload["diagnoses_included"] = diagnoses_included
               
            
            if mustNOThaveSnomedCodes:
                results_payload["diagnoses_excluded"] = mustNOThaveDiagnosisDetails
            
            results_payload_4json = {
                "sql_query": final_query,
                "title": cohort_definition.title,
                "email": cohort_definition.email,
                "total_patients": int(total_patients),
                "total_records": int(total_records),       
                "genderCounts": gender_counts,
                "ageGroups": age_groups,
                "ethnicityCounts": ethnicity_counts,
                "admissions_by_month": admissions_by_month,
                "diagnoses_included": diagnoses_included,
                "diagnoses_excluded": mustNOThaveDiagnosisDetails
                }
    
            def sanitize_for_json(obj):
                """Recursively replace NaN/inf with None in dicts/lists."""
                if isinstance(obj, dict):
                    return {k: sanitize_for_json(v) for k, v in obj.items()}
                elif isinstance(obj, list):
                    return [sanitize_for_json(v) for v in obj]
                elif isinstance(obj, float):
                    if math.isnan(obj) or math.isinf(obj):
                        return None
                return obj
            
            # Apply to both payloads in one line
            results_payload = sanitize_for_json(results_payload)
            results_payload_4json = sanitize_for_json(results_payload_4json)
            
            # Saving results
            filename_results = os.path.join(output_folder, f"{cohort_definition.title.replace(' ', '_')}_results_{datetime_title}.json")
    
            # Save definition as JSON
            with open(filename_results, "w") as f:
                json.dump(results_payload_4json, f, indent=4, allow_nan=True)
               
            
            # Saving HTML
            filename_results_html = os.path.join(output_folder, f"{cohort_definition.title.replace(' ', '_')}_results_html_{datetime_title}.html")
            generate_html_report(results_payload, filename_results_html)
            print("Saved results to results.json")
            
                
            # Generate HTML + PDF report
            # filename_pdf = os.path.join(output_folder, f"{cohort_definition.title.replace(' ', '_')}_{datetime_title}.pdf")
    
            # html_body, pdf_path = generate_report(results_payload, filename_pdf)
            # print("PDF generated at:", pdf_path)
    
            
            html_email_body = f"""
                <html>
                  <body style="font-family: Arial, sans-serif; line-height: 1.5;">
                    <p>Dear user,</p>
                
                    <p>
                      Please find attached the results of the request submitted to the
                      Patient Cohorting Tool on {datetime_mail}.
                    </p>
                    
                    <p>
                      To view the results, please double-click on the attached HTML file.
                      It should automatically open in your default web browser
                      (for example, Google Chrome, Microsoft Edge, or Mozilla Firefox).
                      <br /><br />
                      If the file does not open correctly, please download it to your
                      computer and then open it manually using a web browser.
                    </p>
                
                    <p>
                      If you have any issues, feedback, or comments, please email the
                      Barts Life Sciences data science team at 
                      <a href="mailto:bartshealth.bls.cohortingtool@nhs.net">
                        bartshealth.bls.cohortingtool@nhs.net.<br />
                      </a>
                    </p>
                    
                    <p>
                      <u>
                      Please do not respond to this email as it is unmonitored.
                      </u>
                    </p>
                
                    <p>
                      Kind regards,<br />
                      BLS data science team
                    </p>
                  </body>
                </html>
                """
        
            # Send results email
            try:
                send_results_email(
                    to_email=cohort_definition.email,
                    subject=f"Cohort Results: {cohort_definition.title}",
                    html_body=html_email_body,
                    # pdf_path=None, #pdf_path
                    sender_email=settings.sender_email,
                    smtp_server=settings.smtp_server,
                    smtp_port=settings.smtp_port,
                    app_password=settings.app_password,
                    output_folder = output_folder,
                    cohort_title = cohort_definition.title,
                    data_and_time = datetime_title,
                    html_attachment_path=Path(filename_results_html)        
                )
                print(f"Results email sent to {cohort_definition.email}")
                
                # # ==========================
                # # TEMPORARY EXCEPTION TEST
                # # ==========================
                # raise Exception("TEST: forced processing failure")
                
            except Exception as e1:
                
                error_trace = traceback.format_exc()
                
                html_email_body = f"""
                    <html>
                      <body style="font-family: Arial, sans-serif; line-height: 1.5;">
                        <p>Dear BLS cohorting tool team,</p>
                    
                        <p>
                          The patient cohorting request titled 
                          <b>{cohort_definition.title}</b> (submitted by <b>{cohort_definition.email}</b> on {datetime_title})
                          has <span style="color:red;"><b>failed</b></span> during processing.
                        </p>
                    
                        <p>
                          The error encountered was:
                          <br/>
                          <pre style="background:#f6f6f6; padding:10px; border-radius:5px; white-space:pre-wrap;">
                          {error_trace}
                          </pre>
                        </p>
                    
                        <p>
                          The cohort definition used for this request has been attached to this email
                          as a JSON file for debugging.
                        </p>
                    
                        <p>
                          Kind regards,<br/>
                          BLS Cohorting Tool Automated System
                        </p>
                      </body>
                    </html>
                    """
                    
                send_results_email(
                    to_email=settings.failure_email,
                    subject="Cohort Submission: {cohort_definition.title} - Failed Request 2",
                    html_body=html_email_body,
                    # pdf_path=None, #pdf_path
                    sender_email=settings.sender_email,
                    smtp_server=settings.smtp_server,
                    smtp_port=settings.smtp_port,
                    app_password=settings.app_password,
                    output_folder=output_folder,
                    cohort_title = cohort_definition.title,
                    data_and_time = datetime_title,
                    html_attachment_path=Path(filename)        
                )
                
                
                html_email_body_user = f"""
                    <html>
                      <body style="font-family: Arial, sans-serif; line-height: 1.5;">
                        <p>Dear user,</p>
                    
                        <p>
                          The patient cohorting request titled 
                          <b>{cohort_definition.title}</b> (submitted by <b>{cohort_definition.email}</b> on {datetime_title})
                          has <span style="color:red;"><b>failed</b></span> during processing.
                        </p>
                    
                        <p>
                          Please review the documentation of the tool before tring to submit another request.
                        </p>
                    
                        <p>
                          If you still have issues please email the
                          Barts Life Sciences data science team at 
                          <a href="mailto:bartshealth.bls.cohortingtool@nhs.net">
                            bartshealth.bls.cohortingtool@nhs.net.<br />
                          </a>
                        </p>
                        
                        <p>
                          <u>
                          Please do not respond to this email as it is unmonitored.
                          </u>
                        </p>
                    
                        <p>
                          Kind regards,<br />
                          BLS data science team
                        </p>
                      </body>
                    </html>
                    """
                
                send_results_email(
                    to_email=cohort_definition.email,
                    subject="Cohort Submission: {cohort_definition.title} - Failed Request 2",
                    html_body=html_email_body_user,
                    # pdf_path=None, #pdf_path
                    sender_email=settings.sender_email,
                    smtp_server=settings.smtp_server,
                    smtp_port=settings.smtp_port,
                    app_password=settings.app_password,
                    output_folder=output_folder,
                    cohort_title = cohort_definition.title,
                    data_and_time = datetime_title,
                    html_attachment_path=Path(filename)        
                )
             
                print(f"Failed to send email: {e1}")
    
            # Return JSON to frontend
            return results_payload
            pass

    except Exception as e2:
        try:
            
            error_trace = traceback.format_exc()
            
            html_email_body = f"""
                <html>
                  <body style="font-family: Arial, sans-serif; line-height: 1.5;">
                    <p>Dear BLS cohorting tool team,</p>
                
                    <p>
                      The patient cohorting request titled 
                      <b>{cohort_definition.title}</b> (submitted by <b>{cohort_definition.email}</b> on {datetime_title})
                      has <span style="color:red;"><b>failed</b></span> during processing.
                    </p>
                
                    <p>
                      The error encountered was:
                      <br/>
                      <pre style="background:#f6f6f6; padding:10px; border-radius:5px; white-space:pre-wrap;">
                      {error_trace}
                      </pre>
                    </p>
                
                    <p>
                      The cohort definition used for this request has been attached to this email
                      as a JSON file for debugging.
                    </p>
                
                    <p>
                      Kind regards,<br/>
                      BLS Cohorting Tool Automated System
                    </p>
                  </body>
                </html>
                """
                
            html_email_body_user = f"""
                <html>
                  <body style="font-family: Arial, sans-serif; line-height: 1.5;">
                    <p>Dear user,</p>
                
                    <p>
                      The patient cohorting request titled 
                      <b>{cohort_definition.title}</b> (submitted by <b>{cohort_definition.email}</b> on {datetime_title})
                      has <span style="color:red;"><b>failed</b></span> during processing.
                    </p>
                
                    <p>
                      Please review the documentation of the tool before tring to submit another request.
                    </p>
                
                    <p>
                      If you still have issues please email the
                      Barts Life Sciences data science team at 
                      <a href="mailto:bartshealth.bls.cohortingtool@nhs.net">
                        bartshealth.bls.cohortingtool@nhs.net.<br />
                      </a>
                    </p>
                    
                    <p>
                      <u>
                      Please do not respond to this email as it is unmonitored.
                      </u>
                    </p>
                
                    <p>
                      Kind regards,<br />
                      BLS data science team
                    </p>
                  </body>
                </html>
                """
            
            if settings.demo == 'yes':
                send_results_email(
                    to_email=settings.failure_email,
                    subject="Cohort Submission: {cohort_definition.title} - Failed Request 1",
                    html_body=html_email_body,
                    # pdf_path=None, #pdf_path
                    smtp_server=settings.smtp_server,
                    smtp_port=settings.smtp_port,
                    app_password=settings.app_password,
                    output_folder=output_folder,
                    cohort_title = cohort_definition.title,
                    data_and_time = datetime_title,
                    html_attachment_path=Path(filename) 
                    )
            
            if settings.demo == 'no':
                send_results_email(
                    to_email=settings.failure_email,
                    subject="Cohort Submission: {cohort_definition.title} - Failed Request 1",
                    html_body=html_email_body,
                    # pdf_path=None, #pdf_path
                    sender_email=settings.sender_email,
                    smtp_server=settings.smtp_server,
                    smtp_port=settings.smtp_port,
                    app_password=settings.app_password,
                    output_folder=output_folder,
                    cohort_title = cohort_definition.title,
                    data_and_time = datetime_title,
                    html_attachment_path=Path(filename)        
                    )
                
                send_results_email(
                    to_email=cohort_definition.email,
                    subject="Cohort Submission: {cohort_definition.title} - Failed Request 1",
                    html_body=html_email_body_user,
                    # pdf_path=None, #pdf_path
                    sender_email=settings.sender_email,
                    smtp_server=settings.smtp_server,
                    smtp_port=settings.smtp_port,
                    app_password=settings.app_password,
                    output_folder=output_folder,
                    cohort_title = cohort_definition.title,
                    data_and_time = datetime_title,
                    html_attachment_path=Path(filename)        
                )
            
            print("Email with errors sent")
         
          
        except Exception as e3:
            print(f"Failed to send email: {e3}")



@router.post("/cohort/select")
async def run_select(cohort_definition: CohortDefinition):

    if settings.demo == "yes":
        return process_cohort(cohort_definition)

    else:
        get_queue().put(cohort_definition.model_dump())

        return {
            "status": "processing",
            "message": (
                "Your request is being processed in the background. "
                "You will receive an email when results are ready."
            ),
        }
    

    
