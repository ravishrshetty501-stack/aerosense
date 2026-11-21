# Deterministic AQI Calculation Methodology
**AeroSense AI — Multi-Standard Calculation Engine**

Air quality indices cannot be calculated using a single global formula; different jurisdictions possess distinct epidemiological profiles, background concentrations, and regulatory thresholds. AeroSense AI implements three separate deterministic methodologies.

---

## 1. US EPA AQI Standard

### Governing Reference
*Technical Assistance Document for the Reporting of Daily Air Quality – the Air Quality Index (AQI)*, EPA 454/B-18-007.

### Breakpoints Table

| Category | AQI Range | PM2.5 (24-hr, µg/m³) | PM10 (24-hr, µg/m³) | NO₂ (1-hr, µg/m³) | O₃ (8-hr, µg/m³) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Good** | 0 – 50 | 0.0 – 12.0 | 0 – 54 | 0 – 100 | 0 – 108 |
| **Moderate** | 51 – 100 | 12.1 – 35.4 | 55 – 154 | 101 – 190 | 109 – 140 |
| **Sensitive Groups** | 101 – 150 | 35.5 – 55.4 | 155 – 254 | 191 – 675 | 141 – 170 |
| **Unhealthy** | 151 – 200 | 55.5 – 150.4 | 255 – 354 | 676 – 1220 | 171 – 210 |
| **Very Unhealthy** | 201 – 300 | 150.5 – 250.4 | 355 – 424 | 1221 – 2350 | 211 – 400 |
| **Hazardous** | 301 – 500 | 250.5 – 500.4 | 425 – 604 | 2351 – 3850 | 401 – 800 |

### Mathematical Interpolation Formula
$$I_p = \frac{I_{Hi} - I_{Lo}}{BP_{Hi} - BP_{Lo}} (C_p - BP_{Lo}) + I_{Lo}$$
Where:
- $C_p$ = Truncated pollutant concentration
- $BP_{Hi}, BP_{Lo}$ = Breakpoint concentrations bounding $C_p$
- $I_{Hi}, I_{Lo}$ = Index values corresponding to breakpoints
- Overall AQI: $I = \max(I_{p_1}, I_{p_2}, \dots, I_{p_n})$
- Dominant Pollutant = Pollutant yielding the maximum sub-index.

---

## 2. India CPCB NAQI Standard

### Governing Reference
*National Air Quality Index (NAQI) Final Report*, Central Pollution Control Board (CPCB), Ministry of Environment, Forest and Climate Change, 2014.

### Regulatory Integrity Rule
Under official CPCB guidelines, an overall NAQI can **only** be calculated if:
1. At least three pollutants are monitored.
2. At least one of the monitored pollutants is particulate matter (PM2.5 or PM10).
*If particulate measurements are missing, AeroSense AI explicitly labels the index as unavailable or provisional.*

### Breakpoints Table

| Category | AQI Range | PM2.5 (µg/m³) | PM10 (µg/m³) | NO₂ (µg/m³) | SO₂ (µg/m³) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Good** | 0 – 50 | 0 – 30 | 0 – 50 | 0 – 40 | 0 – 40 |
| **Satisfactory**| 51 – 100 | 31 – 60 | 51 – 100 | 41 – 80 | 41 – 80 |
| **Moderate** | 101 – 200 | 61 – 90 | 101 – 250 | 81 – 180 | 81 – 380 |
| **Poor** | 201 – 300 | 91 – 120 | 251 – 350 | 181 – 280 | 381 – 800 |
| **Very Poor** | 301 – 400 | 121 – 250 | 351 – 430 | 281 – 400 | 801 – 1600 |
| **Severe** | 401 – 500 | 251+ | 431+ | 401+ | 1601+ |

---

## 3. European Air Quality Index (EAQI)

### Governing Reference
European Environment Agency (EEA) Air Quality Index Directive.

### Band Hierarchy
1. **Good**: PM2.5 $\le 10$ µg/m³
2. **Fair**: PM2.5 $10 - 20$ µg/m³
3. **Moderate**: PM2.5 $20 - 25$ µg/m³
4. **Poor**: PM2.5 $25 - 50$ µg/m³
5. **Very Poor**: PM2.5 $50 - 75$ µg/m³
6. **Extremely Poor**: PM2.5 $> 75$ µg/m³

The dominant category represents the worst band among available monitored pollutants.
