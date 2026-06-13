# Patient Health Passport

A Health Information Network (HIN) prototype that enables 
patients to aggregate their fragmented Electronic Health Records (EHR) 
from multiple healthcare providers (simulated by Synthea, 
Epic Healthcare Sandbox, and Cerner) into one unified Health record

## Problem Statement/Goals
A patient who has visited however many different hospitals over their 
lifetime due to a medical condition has that number of
separate, disconnected records, each stored 
in a different EHR system. This project solves that by giving patients a single place to 
access all of their health data and have CONTROL over who they show it to.

## Description
1. Patient connects their hospital accounts to the app
2. The app authenticates using SMART on FHIR — the legal OAuth 
standard for patient-authorized health data access
3. Records are pulled from each connected hospital via FHIR R4 APIs
4. System uses a token exchange process for authorization
5. All records are aggregated into one unified patient record

## Tech Stack
- **Backend:** Node.js, Express
- **Auth Protocol:** SMART on FHIR (OAuth 2.0)
- **Data Standard:** HL7 FHIR R4
- **Local FHIR Server:** HAPI FHIR
- **Synthetic Data:** Synthea, Epic Sandbox, Cerner Sandbox

## Current Project Structure
patient-health-passport/
*  backend/:Node.js HIN engine (SMART on FHIR auth + FHIR API calls)
* hapi-fhir-jpaserver-starter/: Local FHIR server (fake hospital data source)
* synthea/:Synthetic patient generator (114 fake patients)

## Current Status 
- [x] SMART on FHIR authorization flow working end to end
- [x] Local HAPI FHIR server running with 114 synthetic patients
- [x] Successfully pulling conditions, medications, and observations
- [ ] Multi-hospital aggregation (Stage 5 - in progress)
- [ ] Patient-facing UI (Stage 6)
- [ ] AI normalization/aggregation layer (Phase 2)

## Setup Instructions
See README files in each subfolder for specific setup instructions.