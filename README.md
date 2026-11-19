# CareSync AFH — Residential Care & eMAR Web Platform

A full-stack Python web application built with **Flask**, **SQLite**, **Tailwind CSS**, and **ReportLab** for Oregon Adult Foster Homes (AFH) and residential care facilities.

## Features
- **Resident Census & Intake:** Track room numbers, Oregon AFH care levels (Levels 1–3), and resident allergies.
- **Real-Time eMAR Logging:** Record medication administrations with caregiver initials and timestamps.
- **Automated Vital Signs Alerts:** Automatically flags elevated blood pressure readings (`>= 140/90 mmHg`) with visual caregiver action banners.
- **One-Click State Compliance PDF:** Generates formatted daily shift and eMAR audit reports using ReportLab.

## Quick Start
1. Activate environment: `source .venv/bin/activate`
2. Install packages: `pip install flask reportlab`
3. Run app: `python3 app.py`
