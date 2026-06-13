# Synthea — Synthetic Patient Generator

Synthea is an open source synthetic patient generator that 
creates realistic but entirely fictional patient records in 
FHIR R4 format. Used in this project to populate the local 
HAPI FHIR server with 114 fake patients for testing.

## What It Does
- Generates fake but medically realistic patient histories
- Outputs records in FHIR R4 format identical in structure 
  to what real hospitals like Epic and Cerner return
- No real patient data is ever used, so zero HIPAA concerns
- Overall benefit for prototype testing and playground for product development

## How It Relates to the Project
1. Synthea generates 114 fake patients based on real medical sources
2. Each patient file contains resources on the patient, and is loaded onto the HAPI FHIR server, allowing a simulation of patient data to occur
3. The backend queries the server using the exchange token process as it would if the data were real

## Setup Instructions

### Prerequisites
- Java JDK v21+

### Build Synthea
```bash
cd synthea
./gradlew build -x test
```

### Generate Synthetic Patients
```bash
./run_synthea -p 114
```

This generates 114 fake patients. Output files appear in:
synthea/output/fhir/

Each file is one patient's complete medical record in FHIR R4 
format, containing resources such as:
- Patient demographics
- Conditions (diagnoses)
- Observations (lab results, vitals)
- MedicationRequests (prescriptions)
- Immunizations
- Procedures
- Encounters (visit history)

## Notes
- Synthea's job is done once patients are loaded into HAPI FHIR
- The output/fhir/ folder is excluded from this repo via 
  .gitignore (files are too large)
- To regenerate patients, simply run ./run_synthea again
- Original Synthea documentation: https://github.com/synthetichealth/synthea