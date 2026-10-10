-- Store 1: the app's persistent, source-of-truth database.
-- One table per normalizer output (patient_info, conditions, medications,
-- observations). Clinical tables are append-only: edits/removals never
-- delete a row, they set ended_at on the old row and insert a new one.

CREATE TABLE IF NOT EXISTS patient_info (
    patient_id  VARCHAR(64) PRIMARY KEY,
    source      VARCHAR(128),
    name        VARCHAR(255),
    gender      VARCHAR(32),
    birth_date  VARCHAR(32),
    city        VARCHAR(128),
    state       VARCHAR(64),
    phone       VARCHAR(64),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS conditions (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    patient_id  VARCHAR(64) NOT NULL,
    name        VARCHAR(255) NOT NULL,
    status      VARCHAR(64),
    onset       VARCHAR(32),
    icd10       VARCHAR(16),
    openemr_id  VARCHAR(64) NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at    TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_conditions_patient_active (patient_id, ended_at)
);

CREATE TABLE IF NOT EXISTS medications (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    patient_id  VARCHAR(64) NOT NULL,
    name        VARCHAR(255) NOT NULL,
    status      VARCHAR(64),
    date        VARCHAR(32),
    openemr_id  VARCHAR(64) NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at    TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_medications_patient_active (patient_id, ended_at)
);

CREATE TABLE IF NOT EXISTS observations (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    patient_id  VARCHAR(64) NOT NULL,
    name        VARCHAR(255) NOT NULL,
    value       VARCHAR(255),
    date        VARCHAR(32),
    category    VARCHAR(64),
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at    TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_observations_patient_active (patient_id, ended_at)
);

-- Allergies: read from OpenEMR's AllergyIntolerance FHIR endpoint. OpenEMR
-- also has a writable /allergy Standard API endpoint, so openemr_id is kept
-- for a future write-back path (see storage/resources.py).
CREATE TABLE IF NOT EXISTS allergies (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    patient_id   VARCHAR(64) NOT NULL,
    name         VARCHAR(255) NOT NULL,
    status       VARCHAR(64),
    category     VARCHAR(64),
    criticality  VARCHAR(64),
    openemr_id   VARCHAR(64) NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at     TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_allergies_patient_active (patient_id, ended_at)
);

-- Immunizations: read-only. OpenEMR's Standard API has no write endpoint
-- (returns 404), so these flow OpenEMR -> Passport only.
CREATE TABLE IF NOT EXISTS immunizations (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    patient_id   VARCHAR(64) NOT NULL,
    name         VARCHAR(255) NOT NULL,
    status       VARCHAR(64),
    date         VARCHAR(32),
    openemr_id   VARCHAR(64) NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at     TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_immunizations_patient_active (patient_id, ended_at)
);

-- Procedures: read-only, same as immunizations (Standard API 404s for writes).
CREATE TABLE IF NOT EXISTS procedures (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    patient_id   VARCHAR(64) NOT NULL,
    name         VARCHAR(255) NOT NULL,
    status       VARCHAR(64),
    date         VARCHAR(32),
    openemr_id   VARCHAR(64) NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at     TIMESTAMP NULL DEFAULT NULL,
    INDEX idx_procedures_patient_active (patient_id, ended_at)
);
