const SMART_CONFIG = {
  sandbox: {
    name: "SMART Health IT Sandbox",
    fhirUrl: "https://launch.smarthealthit.org/v/r4/sim/WzMsIiIsIiIsIkFVVE8iLDAsMCwwLCIiLCIiLCIiLCIiLCIiLCIiLCIiLDAsMSwiIl0/fhir",
    clientId: "whatever",
    redirectUri: "http://localhost:3000/callback",
    scope: "openid fhirUser patient/Patient.read patient/Condition.read patient/Observation.read patient/MedicationRequest.read"
  },

  local: {
    name: "Local HAPI FHIR",
    fhirUrl: "http://localhost:8080/fhir",
  }
}

module.exports = SMART_CONFIG


//Code explanation:

//Think of it like a contact book at the reception desk:

//Sandbox Hospital:
//- Address: launch.smarthealthit.org
//- Our ID with them: "whatever"
//- Where to send patients after login: localhost:3000/callback
//- What information we're allowed to request: 
//  patient records, conditions, observations, medications

//Local HAPI Hospital:
//- Address: localhost:8080/fhir
//- This is YOUR fake hospital running on your computer