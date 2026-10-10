# Resource Sync Log — OpenEMR ↔ Patient Health Passport

A per-resource record of what works, what broke, the root cause, and the fix,
for the read/write sync between OpenEMR Hospital and Store 1 (`patient_db`).
The goal for each resource: a change in one side shows up in the other.

Kept as a repo file (not Google Drive) so patient-data specifics stay local
and version-controlled.

Last updated: 2026-08-18.

---

## Why only 3 of 6 resources are writable

Conditions, Medications, and (as of today) Allergies are bidirectional.
Immunizations, Procedures, and Observations are **not**, and can't become so
without abandoning the API/FHIR-only decision below. Root cause per resource:

| Resource      | Why it can't write |
|---------------|---------------------|
| Immunizations | OpenEMR's route table has **only** `GET /api/immunization` and `GET /fhir/Immunization` — no POST/PUT/DELETE exists in either API. There is no endpoint to send a write to, full stop. Confirmed directly in `_rest_routes.inc.php`. |
| Procedures    | Same shape as Immunizations: only `GET /api/procedure` and `GET /fhir/Procedure` exist. (OpenEMR does have a full-CRUD `surgery` endpoint, but that's a distinct OpenEMR concept from the FHIR `Procedure` resource we read — not a drop-in write target.) |
| Observations  | OpenEMR has no *plain* patient-level vitals/observation write endpoint at all. Vitals only write through `/patient/{pid}/encounter/{eid}/vital` — nested under a specific clinical encounter, which means creating or resolving an encounter first. This is a real design gap on our side (deferred, not impossible) rather than an OpenEMR hard limit — see Observations section below. |

For all three, the alternative would be writing directly to OpenEMR's MySQL
tables, bypassing its API entirely — which the architecture decision below
explicitly rules out, since it breaks FHIR-compliance and upgrade-safety.

Allergies looked like it would join this "impossible" list too, since GET
returned 401 for the write client — but that turned out to be a scope gate,
not a missing route (see Allergies section). Immunizations/Procedures/
Observations have no such loophole: the routes are absent, not gated.

---

## Architecture decision: API/FHIR-only

Onset display and immunization/procedure writes all hit the same wall —
OpenEMR's FHIR/REST API does not support them, and the only way through is
direct MySQL access to OpenEMR's own tables. **Decision: stay API/FHIR-only.**
No direct reads or writes against OpenEMR's database. Consequences are called
out per resource below (onset for OpenEMR-origin conditions stays blank;
immunizations/procedures stay read-only). This keeps the integration
FHIR-compliant and upgrade-safe at the cost of a few capabilities OpenEMR
won't expose.

---

## Capability matrix (probed against the live OpenEMR instance)

What OpenEMR actually allows decides what "bidirectional" can mean. Reads
probed via the FHIR capability statement (`/apis/default/fhir/metadata`);
writes verified against OpenEMR's **actual REST route table**
(`_rest_routes.inc.php` inside the container) — the authoritative source, not
just probe HTTP codes.

| Resource      | FHIR read | OpenEMR write route (REST or FHIR)      | Sync direction achievable          |
|---------------|-----------|-----------------------------------------|------------------------------------|
| Conditions    | ✅        | ✅ `POST/PUT/DELETE .../medical_problem` | **Bidirectional** (ICD-10 caveat)  |
| Medications   | ✅        | ✅ `POST/PUT/DELETE .../medication`      | **Bidirectional**                  |
| Allergies     | ✅        | ✅ `POST/PUT/DELETE .../allergy`         | **Bidirectional** (name/dates only — see below) |
| Immunizations | ✅        | ❌ **GET routes only** — no POST/PUT anywhere | **Read-only** (one-way)       |
| Procedures    | ✅        | ❌ **GET routes only** — no POST/PUT anywhere | **Read-only** (one-way)       |
| Observations  | ✅        | ❌ encounter-nested only                 | **Read-only** (one-way)            |

**Hard limit:** OpenEMR exposes **no write route** for immunizations or
procedures in *either* its Standard API or its FHIR API (confirmed in the route
table: only `GET /api/immunization`, `GET /api/procedure`, and their FHIR
`GET` equivalents exist). True bidirectional sync for them is impossible
without bypassing OpenEMR's API — which the API/FHIR-only decision rules out.

### OAuth client scopes (registered in OpenEMR's `oauth_clients`)
- **Read client** ("Patient Health Passport: Hospital"): already registered for
  all six FHIR read scopes we need (`patient/AllergyIntolerance.read`,
  `patient/Immunization.read`, `patient/Procedure.read`, plus the original
  three, and `patient/Coverage.read`). Reads only needed the requested-scope
  string widened in `config/smart.py` — no re-registration.
- **Write client** ("Patient Health Passport Writer"): re-registered
  2026-08-18 via OpenEMR's OAuth2 Dynamic Client Registration endpoint
  (`POST /oauth2/default/registration`, RFC 7591 — the same mechanism used
  for every other client here, no DB edits) with scope expanded to add
  `user/allergy.read user/allergy.write` alongside the original
  `user/medical_problem.*`/`user/medication.*`/`user/patient.*`. The old
  writer client (scoped without allergy) was left registered but is no
  longer referenced by `.env` — safe to disable/revoke as cleanup.

---

## Conditions — bidirectional, with caveats

### Problem 1: Resurrection of removed conditions (FIXED)
- **Symptom:** removing conditions in the UI, then logging back into OpenEMR,
  re-created them as fresh active rows every time. Medications never did this.
- **Root cause:** `_sync_versioned()` in `storage/store.py` matched incoming
  OpenEMR reads only against *active* (`ended_at IS NULL`) rows. OpenEMR's FHIR
  `Condition` endpoint keeps returning resolved/ended records forever (its
  `MedicationRequest` endpoint filters them out — that asymmetry is why only
  conditions broke). So a deliberately-ended condition looked brand-new on
  every login and was re-inserted as active.
- **Fix:** for resources with an `openemr` block, the sync now loads *all* rows
  (active + ended), tracks each `openemr_id`'s latest state and whether it's
  active, and **never resurrects an `openemr_id` that was ended locally on
  purpose**. See `store.py` `_sync_versioned`. Verified against live data.

### Problem 2: Onset never displayed for OpenEMR conditions (ROOT CAUSE FOUND)
- **Symptom:** the Onset column is blank for every condition pulled from
  OpenEMR; only app-created conditions show a date.
- **Real root cause (source-verified):** OpenEMR's FHIR Condition service
  (`src/Services/FHIR/FhirConditionService.php`) **never emits an onset field
  at all** — `begdate` is used *only* to compute active/inactive clinicalStatus
  (line ~187), and is never mapped to `onsetDateTime` / `onsetPeriod` /
  `onsetString`. The begin-date is real in OpenEMR's `lists` table (verified:
  Greta's Hypertension=2011-02-18, Aquatic Urticaria=2007-02-14,
  IBS=2014-04-08) but is simply **not in the FHIR payload we read**. No
  normalizer change can recover what OpenEMR doesn't send.
  - (An earlier draft guessed the fix was reading `onsetPeriod.start`. That was
    wrong — OpenEMR emits *no* onset element. Corrected here.)
- **Also broken:** when onset was absent the normalizer stored the literal
  display placeholder `"—"` **as data** (mojibake `�` in the DB). A placeholder
  must never be persisted.
- **Fixes applied:**
  1. `normalize_conditions()` reads `onsetDateTime` → `onsetPeriod.start` →
     `onsetString` (works if any source *does* send onset) and stores `None`
     (clean SQL `NULL`) when absent. Existing garbage cleaned:
     `UPDATE conditions SET onset = NULL WHERE onset NOT REGEXP '^[0-9]{4}-[0-9]{2}-[0-9]{2}'`.
  2. **Onset-preservation in `_sync_versioned` (store.py):** because OpenEMR
     re-reads a condition with onset missing, a naive resync would treat
     "missing" as "changed to empty" and **wipe an onset the patient entered**.
     Fixed by coalescing incoming values over stored values for an
     `openemr_id` match — a `None` from the read means "OpenEMR didn't send
     this," not "cleared." Verified: an app-entered onset survives re-login
     with no row churn, and a real status change still versions.
- **Net result under API/FHIR-only:**
  - Conditions **added in the app**: onset displays and persists. ✅
  - Conditions **originating in OpenEMR**: onset stays blank — OpenEMR won't
    share it over FHIR, and direct DB reads were declined. Accepted ceiling.

### Problem 3: "Unknown condition" for uncoded diagnoses (CONFIRMED permanent — accepted)
- **Cause:** OpenEMR's FHIR Condition mapping drops a diagnosis's free-text
  name when it has no formal code, so `normalize_conditions()` falls back to
  "Unknown condition."
- **Confirmed genuinely unrecoverable (2026-08-18):** while fixing the
  equivalent Allergies bug (see above), checked whether Condition has the
  same recovery path — it doesn't. `FhirConditionService.php`'s
  `populateCode()` just never calls `setCode()` when there's no diagnosis,
  and nothing else in that file calls `setText()`/attaches a narrative the
  way Allergy's mapping does. There is no field in OpenEMR's Condition FHIR
  response, anywhere, that carries an uncoded condition's title. This isn't
  a gap in our normalizer; the data isn't in the payload.
- **Decision:** explicitly **not** auto-resolved (no name→code NIH crosscheck).
  Auto-picking a code from a free-text name is a silent clinical coding
  decision and a worse failure mode than an honest "Unknown." Entering a valid
  ICD-10 code in OpenEMR (or via the app's own Condition edit form, which
  already writes ICD-10) is the supported path.
- **UX polish (2026-08-18):** the fallback name now reads
  `"Unknown condition (no ICD-10 code)"` instead of a bare `"Unknown
  condition"`, so it reads as an explained data gap rather than an app bug.
  Live example: Greta's "IBS" condition has an empty `diagnosis` field in
  OpenEMR (confirmed via DB inspection) — that's the one currently showing
  this fallback. Editing it in the app with a real ICD-10 code (e.g.
  `K58.9`, IBS without diarrhea) would resolve it the same way the earlier
  Aquatic Urticaria fix did.
- **Related artifact:** a condition entered with a code NIH can't resolve to a
  name (e.g. `H40.11X4`) shows the *code* as its name. Same inherent ICD-10
  limitation; also accepted.

### Write path notes
- Store 1 is written first, then best-effort mirrored to OpenEMR
  (`records_controller.py` → `openemr_write.py`). A failed push never blocks the
  local write; it's reported via `synced_to_openemr`.
- Conditions carry the ICD-10 code through as OpenEMR's `diagnosis` field
  (`ICD10:<code>`), because OpenEMR's Condition mapping never round-trips a
  free-text title.
- Date format: `medical_problem` requires plain `Y-m-d` (ConditionValidator),
  unlike medication — see `resources.py` `datetime_fields`.

---

## Medications — bidirectional (reference "good" path)

- Reads and writes both work.
- Quirks handled:
  - Name can live in `medicationCodeableConcept.text` *or*
    `medicationReference.display` (`normalize_medications`).
  - Standard API `medication` (via `ListService`) requires full
    `Y-m-d H:i:s` datetimes and 400s on a plain date — opposite of conditions.
    Handled by `datetime_fields` in `resources.py`.
  - PUT requires `title` resent on every update, not just changed fields —
    `push_end()` resends the row's fields alongside `enddate`.
  - Patient addressed by OpenEMR's internal numeric pid (`id_style: "pid"`),
    resolved+cached in `openemr_write._resolve_pid`.

---

## Allergies — bidirectional (name/dates only)

### Enabling writes (DONE, 2026-08-18)
OpenEMR exposes full CRUD at `POST/PUT/DELETE /api/patient/:puuid/allergy`
(uuid-addressed — confirmed in the route table; the original doc draft here
incorrectly said `pid`, copying the medication pattern without checking).
GET had returned 401 for our write token because the route existed but the
token lacked scope, not because the route was missing. Fixed by:
1. Registering a new write client via OpenEMR's OAuth2 Dynamic Client
   Registration endpoint with `user/allergy.read user/allergy.write` added
   (see OAuth scopes above) — admin-confirmed, then `.env` pointed at it.
2. Adding those scopes to `config/smart.py`'s `openemr_write` scope string.
3. Uncommenting the `openemr` block under `allergies` in `resources.py`,
   with the `id_style` correction (`"uuid"`, not `"pid"`).
4. Switching the Allergies UI tab from `ResourceTable` to
   `EditableResourceTable`.

### Permanent limit: only the allergen name and dates round-trip
`AllergyIntoleranceRestController::WHITELISTED_FIELDS` (source-confirmed) is
exactly `title, begdate, enddate, diagnosis, comments`. There is no
`severity_al`, no status, no category field accepted by this endpoint at
all — not a scope issue, the endpoint simply doesn't take them. So:
- `name` → OpenEMR's `title`. Round-trips. ✅
- `status`, `category`, `criticality` → **no OpenEMR equivalent reachable
  over this endpoint.** They're stored in Store 1 and shown in the UI, but
  never pushed, and never come back from OpenEMR either (except
  `criticality`, indirectly — see below). Same shape as the Conditions
  ICD-10 caveat: accepted, not a bug.
- The Severity dropdown's options were changed from FHIR criticality's
  3-value set (`low`/`high`/`unable-to-assess`) to OpenEMR's own
  `severity_ccda` list (`Unassigned`/`Mild`/`Mild to moderate`/`Moderate`/
  `Moderate to severe`/`Severe`/`Life threatening severity`/`Fatal`), to
  match what a clinician sees in OpenEMR's own allergy form — since the
  field is Store-1-only anyway, matching that vocabulary is purely a UX
  choice, not a sync requirement.

### Bug found and fixed: "Unknown" allergen name on writes without a diagnosis code
- **Symptom:** an allergy added through the app (title only, no ICD code)
  read back with its name showing as the literal word `"Unknown"`.
- **Root cause (source-confirmed,
  `FhirAllergyIntoleranceService::parseOpenEMRRecord`):** when a `lists` row
  has no `diagnosis`, OpenEMR doesn't leave `AllergyIntolerance.code` empty —
  it sets `code.coding` to FHIR's standard "data absent reason" placeholder
  (`system: http://terminology.hl7.org/CodeSystem/data-absent-reason,
  code: "unknown", display: "Unknown"`). Read naively, that placeholder's
  `display` looks like real data, so it was picked up as the allergen name.
- **The recoverable part:** unlike Condition, OpenEMR's allergy mapping
  *does* preserve the free-text title — just in the resource's narrative
  (`text.div`, an XHTML-wrapped string) instead of `code.text`
  (`$allergyIntoleranceResource->setText(UtilsService::createNarrative($dataRecord['title'], "additional"))`).
- **Fix:** `normalize_allergies()` now detects the data-absent-reason system
  URI and skips it instead of treating its `display` as a real name, then
  falls back to extracting the plain text from `text.div` before ever
  falling back to the generic `"Unknown allergy"`. See `_narrative_text()` in
  `normalizer.py`. Verified live: Greta's app-added allergen now reads back
  with its real name.
- **Why this fix doesn't apply to Conditions:** checked directly —
  `FhirConditionService.php` has no `setText()`/narrative call anywhere, and
  `populateCode()` simply never calls `setCode()` when there's no diagnosis
  (no placeholder, no fallback text, nothing to recover). Confirmed dead end;
  see Conditions Problem 3 below.

### Bug found and fixed: resync clobbered app-entered values (2026-10-09)
- **Symptoms (seen in live data):** an app-entered allergy's status flipped
  `inactive` → `active` and its severity became `�` after the next login.
- **Causes:** (1) `normalize_allergies` defaulted absent fields to the `"—"`
  display placeholder, which was persisted as data (mojibake) and, being
  non-None, defeated `_sync_versioned`'s keep-existing-on-missing coalesce.
  (2) OpenEMR's FHIR mapping hardcodes every allergy's `category` to
  `"medication"`, so a read can never carry a real category.
- **Fixes:** absent fields now normalize to `None`; `resources.py` gained a
  generic `"local_only"` list (allergies: `["category"]`) whose stored value
  a read never overwrites. Existing `�` values nulled. Verified with an
  isolated test patient: category and severity survive a resync.
- **Still open (design decision):** `status` is derived by OpenEMR from the
  end date (no end date → `active`), so an app-set `inactive` reverts on the
  next login. Making it stick means pushing an `enddate` when a patient saves
  an inactive/resolved allergy (`resolved` can't round-trip: it needs OpenEMR's
  `outcome` flag, which the write endpoint doesn't accept).
- **Cleanup:** an orphaned active "Unknown" row (no `openemr_id`, left over
  from before the narrative-name fix) was ended.

---

## Immunizations — read-only (permanent limit)

- **Read (DONE):** `Immunization` FHIR pull added; `normalize_immunizations()`
  flattens vaccineCode / status / occurrenceDateTime; `immunizations` table +
  registry entry + read-only UI tab added.
- **Write (IMPOSSIBLE):** OpenEMR's route table has **only** `GET /api/immunization`
  and `GET /fhir/Immunization` — no POST/PUT/DELETE in either API. There is no
  endpoint to mirror to. No `openemr` block; flows OpenEMR → Passport only.
  Not a code gap on our side.
- **Data caveat (Greta):** her 2 immunizations were entered in OpenEMR with no
  vaccine selected (`immunization_id = 0`), so they read back with no
  vaccineCode and normalize to "Unknown vaccine." That's an OpenEMR data-entry
  gap, not a sync bug.

---

## Procedures — read-only (permanent limit)

- **Read (DONE):** `Procedure` FHIR pull added; `normalize_procedures()`
  flattens code / status / performedDateTime|performedPeriod.start;
  `procedures` table + registry entry + read-only UI tab added.
- **Write (IMPOSSIBLE):** route table has **only** `GET /api/procedure` and
  `GET /fhir/Procedure` — no write route. (A separate `surgery` endpoint has
  full CRUD, but "surgery" is a different OpenEMR concept from the FHIR
  Procedure read, so it is not a drop-in write path.) Read-only.
- **Note on table name:** `procedures` (plural) is safe as a MySQL identifier;
  the reserved word is the singular `PROCEDURE`.

---

## Observations — read-only (deferred, not blocked-forever)

- Read works. No write path: OpenEMR has no plain patient-level vitals endpoint
  — vitals are nested under an encounter
  (`/patient/{pid}/encounter/{eid}/vital`), which needs encounter
  creation/lookup first. Deferred until that's designed.

---

## Other data the chart shows — is it FHIR?

- **Insurance → FHIR `Coverage`.** A real FHIR resource; OpenEMR exposes it
  read-only and our read client is already scoped (`patient/Coverage.read`).
  Could be added as a read-only tab. Writing coverage is not planned.
- **Continuity of Care Document (CCD/C-CDA) → a *document*, not structured
  fields.** In FHIR it's a `DocumentReference` (pointer) + `Binary` (the actual
  document). You'd surface/download it, not field-sync it.
- **Ledger → not FHIR-syncable in OpenEMR.** Billing maps to FHIR
  `Account`/`Invoice`/`Claim`/`ChargeItem`, but OpenEMR's FHIR API exposes
  none of them. Only reachable via direct DB, which is out of scope under the
  API/FHIR-only decision.

---

## Open items / next actions
1. **Rotate OAuth client IDs/secrets** — flagged earlier after an accidental
   plaintext exposure; still pending. Now also: the old (pre-allergy) write
   client is still registered and enabled in OpenEMR but unused — disable it.
2. **Insurance/Coverage tab** — optional read-only add, if wanted.
3. **Immunizations / Procedures / Observations writes** — not possible while
   API/FHIR-only, and for Immunizations/Procedures not possible at all short
   of OpenEMR adding write endpoints (see "Why only 3 of 6 resources are
   writable" above). Observations is the one gap that's a real design task
   (encounter-nested vitals endpoint), not a hard OpenEMR limit.
4. **IBS condition (Greta):** currently showing "Unknown condition (no
   ICD-10 code)" — has no diagnosis code in OpenEMR. Not a bug; would need a
   code entered (via the app's own edit form) to resolve, same as the
   earlier Aquatic Urticaria fix.
