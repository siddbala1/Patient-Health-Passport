const express = require('express')
const router = express.Router()
const { redirectToLogin, handleCallback, queryLocalFHIR } = require('../controllers/authController')

// Route 1: Patient initiates connection to a hospital
router.get('/connect', redirectToLogin)

// Route 2: Hospital redirects patient back after login
router.get('/callback', handleCallback)

// Route 3: Query local HAPI FHIR server directly
router.get('/local', queryLocalFHIR)

module.exports = router

//Someone visits /connect  
//→ send them to redirectToLogin in authController

//Someone visits /callback 
//→ send them to handleCallback in authController