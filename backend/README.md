# Backend

The core of the Health Information Network. A Node.js/Express 
server that handles patient authorization and FHIR data retrieval using SMART on FHIR auth page.

## Description
1. Redirects patients to their hospital's login page from main app portal
2. Handles the OAuth 2.0 callback after patient authorizes access
3. Exchanges the authorization code for an access token
4. Uses that token to pull structured clinical records via FHIR R4 APIs

## Tech Stack
- **Runtime:** Node.js
- **Framework:** Express
- **HTTP Client:** Axios
- **Protocol:** SMART on FHIR (OAuth 2.0)
- **Data Format:** HL7 FHIR R4

## File Structure
backend/
* index.js: Main server (port 3000)
* .env: Environment variables (not in repo)
* config/
 - smart.js: Hospital configurations
* controllers/
 - authController.js: Auth flow + FHIR data retrieval
* routes/
* auth.js: URL routing

## Setup Instructions

### Prerequisites
- Node.js v20+
- A running HAPI FHIR server (see hapi-fhir-jpaserver-starter folder)

### Install Dependencies
```bash
cd backend
npm install
```

### Configure Environment
Create a `.env` file in the backend folder:
PORT=3000 HAPI_FHIR_URL=http://localhost:8080/fhir

### Start the Server
```bash
node index.js
```

### Verify It's Running
Visit: `http://localhost:3000/health`
(Could vary depending on how this is run)

## Testing the Auth Flow
1. Go to `https://launch.smarthealthit.org`
2. Set Launch Type to "Patient Standalone Launch" - this simulates how you would access your hospital as a patient
3. Copy the generated FHIR base URL into `config/smart.js`
4. Set App Launch URL to `http://localhost:3000/connect`
5. Click Launch
6. Log in as any test patient and click Authorize
7. Records returned as JSON at `http://localhost:3000/callback`

## Data Sources

Source 1:  SMART Health IT Sandbox
    Type: External test environment
    URL: launch.smarthealthit.org
Source 2: Local HAPI FHIR (using loaded Synthea patient data in JSON format)
    Type: Local fake hospital
    URL: localhost:8080/fhir