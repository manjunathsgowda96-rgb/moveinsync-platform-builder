# MoveInSync Operations Control Tower — MVP

A Streamlit prototype for the Platform Builder case study.

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

Upload the supplied Fleet-CaseStudy-Data.xlsx through the app. The case data is intentionally not committed to this repository.

## Scope

The MVP focuses on Site Type = O (managed service), where the operating fleet is in MoveInSync's operational scope. It provides site health, SLA exception monitoring, and vendor service performance using the supplied historical trip data.

The 10-minute breach threshold is an explicit prototype assumption pending confirmation of the contractual SLA.
