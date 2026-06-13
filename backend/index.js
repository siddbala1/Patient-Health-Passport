const express = require('express')
const cors = require('cors')
const dotenv = require('dotenv')

// Load environment variables from .env file
dotenv.config()

const app = express()
const PORT = process.env.PORT || 3000

// Middleware
app.use(cors())
app.use(express.json())

// Routes
const authRoutes = require('./routes/auth')
app.use('/', authRoutes)

// Basic health check endpoint
app.get('/health', (req, res) => {
  res.json({ 
    status: 'running',
    message: 'Health Passport HIN Backend is live'
  })
})

// Start server
app.listen(PORT, () => {
  console.log(`Health Passport backend running on http://localhost:${PORT}`)
})

//Function explanations:
//app.listen(3000) 
//→ "Open the front door at address 3000"

//app.use(cors()) 
//→ "Allow people from outside to walk in"

//app.use(express.json()) 
//→ "Make sure staff can read the paperwork patients bring in"

//app.use('/', authRoutes)
//→ "Direct anyone who walks in to the authorization department"

//app.get('/health')
//→ "Put up a sign that says we're open and running"