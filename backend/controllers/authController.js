const axios = require('axios')
const SMART_CONFIG = require('../config/smart')

// Step 1: Redirect patient to hospital login page
const redirectToLogin = async (req, res) => {
  try {
    const source = req.query.source || 'sandbox'
    const config = SMART_CONFIG[source]

    // Fetch the hospital's SMART configuration
    const smartConfig = await axios.get(
      `${config.fhirUrl}/.well-known/smart-configuration`
    )

    const { authorization_endpoint } = smartConfig.data

    // Build the login URL
    const params = new URLSearchParams({
      response_type: 'code',
      client_id: config.clientId,
      redirect_uri: config.redirectUri,
      scope: config.scope,
      state: source,
      aud: config.fhirUrl
    })

    const loginUrl = `${authorization_endpoint}?${params.toString()}`
    
    console.log(`Redirecting patient to: ${loginUrl}`)
    res.redirect(loginUrl)

  } catch (error) {
    console.error('Error during login redirect:', error.message)
    res.status(500).json({ error: 'Failed to initiate login' })
  }
}

// Step 2: Handle callback after patient logs in
const handleCallback = async (req, res) => {
  try {
    const { code, state } = req.query
    const source = state || 'sandbox'
    const config = SMART_CONFIG[source]

    // Fetch token endpoint
    const smartConfig = await axios.get(
      `${config.fhirUrl}/.well-known/smart-configuration`
    )

    const { token_endpoint } = smartConfig.data

    // Exchange code for access token
    const tokenResponse = await axios.post(
      token_endpoint,
      new URLSearchParams({
        grant_type: 'authorization_code',
        code: code,
        client_id: config.clientId,
        redirect_uri: config.redirectUri
      }),
      { headers: { 'Content-Type': 'application/x-www-form-urlencoded' } }
    )

    const { access_token, patient, id_token} = tokenResponse.data

    console.log('Full token response: ', tokenResponse.data)

    if (!patient) {
        // Extract patient ID from the fhirUser field in token response
        const fhirUser = tokenResponse.data.fhirUser || 
                   JSON.parse(Buffer.from(access_token.split('.')[1], 'base64').toString()).fhirUser
  
        const patientId = fhirUser ? fhirUser.split('/')[1] : null
  
        console.log(`Extracted patient ID: ${patientId}`)

    if (patientId) {
        const records = await pullPatientRecords(patientId, access_token, config.fhirUrl)
        return res.json({
            message: 'Successfully connected and retrieved records',
            patientId: patientId,
            records: records
        })
    }

    return res.json({
        message: 'Authorization successful',
        access_token: access_token,
        note: 'Patient ID not returned by sandbox - token exchange worked correctly'
    })
    } 
    
    
    console.log(`Token received for patient: ${patient}`)
    // Step 3: Pull patient records immediately
    const records = await pullPatientRecords(
      patient,
      access_token,
      config.fhirUrl
    )

    res.json({
      message: 'Successfully connected and retrieved records',
      patientId: patient,
      records: records
    })

  } catch (error) {
    console.error('Error during callback:', error.message)
    res.status(500).json({ error: 'Failed to complete authorization' })
  }
}

// Step 3: Pull FHIR records using access token
const pullPatientRecords = async (patientId, token, fhirUrl) => {
  const headers = { Authorization: `Bearer ${token}` }

  const [patient, conditions, medications, observations] = await Promise.all([
    axios.get(`${fhirUrl}/Patient/${patientId}`, { headers }),
    axios.get(`${fhirUrl}/Condition?patient=${patientId}`, { headers }),
    axios.get(`${fhirUrl}/MedicationRequest?patient=${patientId}`, { headers }),
    axios.get(`${fhirUrl}/Observation?patient=${patientId}`, { headers })
  ])

  return {
    patient: patient.data,
    conditions: conditions.data,
    medications: medications.data,
    observations: observations.data
  }
}
const queryLocalFHIR = async (req, res) => {
  try {
    const { name } = req.query
    
    if (!name) {
      return res.status(400).json({ 
        error: 'Please provide a patient name',
        example: 'http://localhost:3000/local?name=Walton'
      })
    }

    const fhirUrl = process.env.HAPI_FHIR_URL

    const patientSearch = await axios.get(
      `${fhirUrl}/Patient?name=${name}`
    )

    if (patientSearch.data.total === 0) {
      return res.status(404).json({ 
        error: `No patient found with name: ${name}` 
      })
    }

    const patient = patientSearch.data.entry[0].resource
    const patientId = patient.id

    console.log(`Found local patient: ${patient.name[0].family}, ID: ${patientId}`)

    const [conditions, medications, observations] = await Promise.all([
      axios.get(`${fhirUrl}/Condition?patient=${patientId}`),
      axios.get(`${fhirUrl}/MedicationRequest?patient=${patientId}`),
      axios.get(`${fhirUrl}/Observation?patient=${patientId}`)
    ])

    res.json({
      message: 'Successfully retrieved records from local HAPI FHIR',
      source: 'Local HAPI FHIR Server',
      patientId: patientId,
      records: {
        patient: patient,
        conditions: conditions.data,
        medications: medications.data,
        observations: observations.data
      }
    })

  } catch (error) {
    console.error('Error querying local FHIR:', error.message)
    res.status(500).json({ error: 'Failed to query local FHIR server' })
  }
}
module.exports = { redirectToLogin, handleCallback, queryLocalFHIR }


//Job 1: redirectToLogin
//→ When patient says "connect Hospital X" look up that hospital's login page and send the patient there

//Job 2: handleCallback
//→ When the hospital sends the patient back with a temporary code, exchange that code
// for a real access token

//Job 3: pullPatientRecords
//→ Use the access token to pull the patient's conditions, medications, and observations
// from that hospital