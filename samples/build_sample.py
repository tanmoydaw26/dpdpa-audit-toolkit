"""
Generate the pre-filled sample assessment.

The sample entity is fictional but constructed to be realistic and to exercise
every branch of the toolkit: it is a notified Significant Data Fiduciary, relies
on a Consent Manager, sits in a regulated sector, offers a product used by
minors, and holds pre-commencement consent data. That combination brings 87 of
the 90 controls into scope and engages five of the seven Schedule entries.

The maturity pattern is deliberately uneven and characteristic of a regulated
Indian fintech in 2026: strong on information security and incident response
(built for RBI and PCI expectations), materially weaker on the obligations that
are distinctive to the DPDP Act — itemised notice, provable consent artefacts,
withdrawal propagation, erasure, rights fulfilment and the children's
provisions. A uniformly mediocre sample would demonstrate nothing.

Run:  python -m samples.build_sample
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dpdpa_audit import Assessment, CompanyProfile, load_library  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

# people ------------------------------------------------------------------
LEGAL = "Meera Raghunathan, Head of Legal & Compliance"
CISO = "Arjun Nair, Chief Information Security Officer"
ENG = "Devika Iyer, VP Engineering"
PROD = "Rohit Menon, Head of Product"
PEOPLE = "Sneha Kulkarni, Head of People"
VENDOR = "Farhan Qureshi, Head of Vendor Management"
CX = "Anita Desai, Head of Customer Experience"
CFO = "Vikram Shetty, Chief Financial Officer"
DPO = "Interim — see SDF-01"

PROFILE = CompanyProfile(
    legal_name="Kavach Financial Technologies Private Limited",
    trading_name="KavachPay",
    sector="Financial services — consumer lending, UPI payments and prepaid instruments",
    registered_office=("Level 7, Prestige Zeta, Whitefield Main Road, Bengaluru 560066, "
                       "Karnataka, India"),
    headcount=1180,
    data_principal_count=14_200_000,
    business_description=(
        "KavachPay operates a consumer financial services platform in India comprising a UPI "
        "payments application, an unsecured personal and consumer-durable lending business "
        "originated digitally and co-lent with two partner NBFCs, a prepaid payment instrument "
        "wallet, and 'Kavach Junior', a supervised prepaid card and savings product marketed to "
        "13-17 year olds under a parent's account. Onboarding is fully digital and relies on "
        "third-party KYC and bureau services. The entity was notified as a Significant Data "
        "Fiduciary and participates in the account aggregator ecosystem as a Financial "
        "Information User, receiving financial information through a registered Consent Manager."
    ),
    systems_in_scope=[
        "KavachPay consumer mobile application (Android, iOS) and web onboarding journey",
        "Kavach Lend — loan origination and underwriting platform (in-house, AWS ap-south-1)",
        "Kavach Junior — teen prepaid card product and parent supervision console",
        "Kavach CRM — Salesforce Financial Services Cloud (customer service and collections)",
        "Kavach Analytics — Snowflake data warehouse and dbt transformation layer",
        "Kavach Ledger — core wallet and PPI ledger",
        "Marketing stack — CleverTap (engagement), Meta and Google advertising integrations",
        "Communications — Exotel (voice), Gupshup (SMS and WhatsApp), Amazon SES (email)",
        "Identity and KYC — Signzy (video KYC), Karza (document verification), CIBIL and CRIF",
        "Account aggregator integration via a registered Consent Manager",
        "Corporate systems — Google Workspace, Darwinbox (HRMS), Freshservice (ITSM)",
    ],
    entities_in_scope=[
        "Kavach Financial Technologies Private Limited (Data Fiduciary)",
        "Kavach Collections Services Private Limited (wholly-owned subsidiary, collections)",
    ],
    exclusions=[
        "Kavach Insurance Broking Private Limited — separate legal entity and consent "
        "architecture; scheduled for assessment in the next cycle.",
        "Physical branch operations of the co-lending partner NBFCs, which are the partners' "
        "own Data Fiduciary responsibility.",
        "Testing of the account aggregator's own systems, which are outside the entity's "
        "control; reliance was placed on the Consent Manager's registration status only.",
    ],
    flags={
        "is_sdf": True,
        "processes_children_data": True,
        "processes_employee_data": True,
        "uses_consent_manager": True,
        "is_consent_manager": False,
        "has_pre_commencement_data": True,
        "regulated_sector": True,
        "claims_exemption": False,
        "startup_exempt_s8_3": False,
        "startup_exempt_s8_7": False,
        "startup_exempt_s11": False,
    },
)

# (score, finding, evidence_ref, owner) -----------------------------------
R = {
    # -- APP ------------------------------------------------------------
    "APP-01": (3, "A written applicability analysis dated 12 February 2026 concludes that the "
                  "entity processes digital personal data within India as a Data Fiduciary and "
                  "additionally offers goods and services to Data Principals in India from a "
                  "Singapore-incorporated affiliate. The analysis is sound but has not been "
                  "revisited since the Kavach Junior launch in April 2026.",
               "WP-001", LEGAL),
    "APP-02": (2, "Role determination has been performed for the co-lending arrangements and for "
                  "the KYC vendors, but not for the marketing stack. CleverTap and the Meta "
                  "Custom Audiences integration are treated as processors in the vendor register "
                  "while the contractual terms and the practical control over onward use point "
                  "to an independent fiduciary role for the advertising platforms. The "
                  "mischaracterisation understates the notice and consent obligations attaching "
                  "to those disclosures.",
               "WP-002", LEGAL),
    "APP-05": (1, "The compliance plan carries a single milestone described as 'DPDP readiness' "
                  "with no linkage to the commencement of individual provisions or to the "
                  "phasing of the Rules. Management could not demonstrate a mechanism for "
                  "tracking notifications, so a provision coming into force would not "
                  "automatically trigger a change in the plan.",
               "WP-003", LEGAL),
    # -- GOV ------------------------------------------------------------
    "GOV-01": (2, "Accountability is asserted in the Information Privacy Policy v2.1 and the "
                  "Head of Legal & Compliance is named as owner. However the policy is silent on "
                  "the entity's responsibility for processing carried out by processors on its "
                  "behalf, and the collections subsidiary operates its own dialler and call "
                  "recording estate without the parent's oversight of that processing.",
               "WP-010", LEGAL),
    "GOV-02": (2, "A record of processing activities exists in a spreadsheet covering 61 "
                  "activities, last updated November 2025. Walkthroughs identified four "
                  "unrecorded processing activities: Kavach Junior parent supervision, the "
                  "WhatsApp collections journey, the churn-prediction model in Kavach Analytics, "
                  "and employee productivity monitoring in the collections function. The record "
                  "does not capture retention period or recipient for 23 of the 61 entries.",
               "WP-011", LEGAL),
    "GOV-03": (3, "Contact details for the privacy function are published in the app privacy "
                  "policy and on the website footer, and the address routes to a monitored "
                  "mailbox. The published contact is a generic role address rather than the "
                  "person discharging the function, and the Kavach Junior parent console does "
                  "not surface the contact at all.",
               "WP-012", LEGAL),
    "GOV-04": (2, "Privacy is reported to the Risk Management Committee twice yearly as part of a "
                  "combined information security update. Minutes for the two meetings in the "
                  "period record no privacy-specific decision, no budget approval and no "
                  "challenge from members. There is no board-level acceptance of the residual "
                  "risk arising from the open items in this report.",
               "WP-013", CFO),
    "GOV-05": (3, "A policy set comprising an Information Privacy Policy, Data Classification "
                  "Standard, Retention Standard and Third Party Standard is approved and "
                  "accessible on the intranet. The Retention Standard is dated 2023 and predates "
                  "both the Kavach Junior product and the current warehouse architecture, and "
                  "the Third Party Standard does not address the s.8(2) contract requirement.",
               "WP-014", LEGAL),
    "GOV-06": (2, "Annual information security training is mandatory and completion stands at 94 "
                  "per cent. Privacy content within it runs to four slides and does not address "
                  "consent, rights handling or the children's provisions. No role-specific "
                  "training has been delivered to the engineering, marketing or collections "
                  "teams whose decisions determine compliance in practice.",
               "WP-015", PEOPLE),
    "GOV-07": (1, "Evidence of compliance is not systematically retained. Consent artefacts are "
                  "held only in the current state of the consent table with no immutable history, "
                  "notice versions are not archived, and rights request correspondence is held in "
                  "agent mailboxes. The entity could not reconstruct, for a Data Principal who "
                  "consented in March 2025, what notice they were shown. This directly undermines "
                  "the ability to discharge the burden of proof the Act places on the Data "
                  "Fiduciary.",
               "WP-016", ENG),
    # -- PUR ------------------------------------------------------------
    "PUR-01": (2, "A lawful basis is documented for the lending and payments journeys. Four "
                  "activities have no identified basis: the churn model, marketing enrichment "
                  "from a third-party data broker, call recording in collections, and the "
                  "employee monitoring noted at GOV-02. Management's position that these fall "
                  "within 'legitimate business interest' has no counterpart in the Act, which "
                  "provides a closed list of legitimate uses.",
               "WP-020", LEGAL),
    "PUR-02": (2, "The onboarding journey collects marital status, education level and employer "
                  "address for all applicants irrespective of product. Product management "
                  "confirmed these fields are used only for a subset of underwriting models and "
                  "could not evidence necessity for the payments-only journey, which represents "
                  "roughly 60 per cent of registrations.",
               "WP-021", PROD),
    "PUR-03": (1, "Transaction data collected for payments processing is used to build "
                  "propensity segments that are pushed to Meta and Google for acquisition "
                  "campaigns. The notice presented at registration does not disclose "
                  "advertising as a purpose. This is undisclosed secondary use of data obtained "
                  "for a different specified purpose.",
               "WP-022", PROD),
    "PUR-04": (3, "Bureau and KYC data feeding underwriting is refreshed at decision time and a "
                  "correction workflow exists in Kavach CRM. Corrections applied in CRM do not "
                  "propagate to the Snowflake warehouse, so models and collections lists may run "
                  "on superseded data for up to 30 days.",
               "WP-023", ENG),
    "PUR-05": (2, "A privacy review is a documented gate in the product development lifecycle but "
                  "is discretionary in practice. Of the 11 features released in the period, three "
                  "carried a completed review. Kavach Junior, the highest-risk launch in the "
                  "period, went live without one.",
               "WP-024", PROD),
    # -- NOT ------------------------------------------------------------
    "NOT-01": (3, "The registration journey presents a notice screen before the consent action on "
                  "the mobile application. In the web journey and in the assisted onboarding "
                  "flow used by field agents, the notice is presented as a hyperlink beside a "
                  "pre-ticked declaration, so it neither accompanies nor precedes the consent in "
                  "any meaningful sense.",
               "WP-030", PROD),
    "NOT-02": (1, "The notice describes the data collected in categories such as 'identity and "
                  "contact information' and 'usage data' and states purposes as 'to provide and "
                  "improve our services'. It is neither an itemised description of the personal "
                  "data nor a specified purpose. The notice also omits the account aggregator "
                  "data received through the Consent Manager entirely.",
               "WP-031", LEGAL),
    "NOT-03": (2, "The notice explains the access and correction rights and links to the "
                  "grievance form. It does not explain the right to withdraw consent, the right "
                  "to nominate, or the manner in which a Data Principal may make a complaint to "
                  "the Data Protection Board.",
               "WP-032", LEGAL),
    "NOT-04": (1, "Notice and consent screens are available in English and Hindi only. The "
                  "entity's own registration data shows material user populations in Tamil, "
                  "Telugu, Marathi, Bengali and Kannada. No language other than English and "
                  "Hindi is offered, and no request mechanism exists for the remaining Eighth "
                  "Schedule languages.",
               "WP-033", PROD),
    "NOT-05": (0, "Approximately 9.4 million Data Principals onboarded before the current notice "
                  "version have not been given a retrospective notice. Management was aware of "
                  "the requirement and has scoped a campaign but has not set a date, citing "
                  "concern about attrition and support volume. No compensating action has been "
                  "taken.",
               "WP-034", LEGAL),
    # -- CON ------------------------------------------------------------
    "CON-01": (2, "Consent is captured through a single checkbox covering the privacy policy, "
                  "terms of service, marketing communications and credit bureau enquiry. It is "
                  "therefore neither specific nor unconditional: a Data Principal cannot accept "
                  "the service without also accepting marketing. Purpose-level granularity "
                  "exists in the data model but is not exposed in the interface.",
               "WP-040", PROD),
    "CON-02": (2, "Registration for the payments-only product cannot be completed without "
                  "consenting to the bureau enquiry, which is not necessary for that service. "
                  "The lending journey, by contrast, is correctly scoped.",
               "WP-041", PROD),
    "CON-03": (3, "The consent request is short and in plain language and names the entity. It "
                  "does not provide the contact details of the person able to answer questions "
                  "about the processing, and directs the reader to a 47-page combined policy "
                  "document for detail.",
               "WP-042", LEGAL),
    "CON-04": (1, "Withdrawal of consent is not available in the application. Marketing "
                  "preferences can be toggled, but withdrawal of consent for processing requires "
                  "an email to the support address, after which an agent follows a manual "
                  "runbook. Against a two-tap consent action this is plainly not as easy to "
                  "withdraw as to give.",
               "WP-043", PROD),
    "CON-05": (2, "Consequences of withdrawal are described in the policy document but are not "
                  "surfaced at the point of withdrawal, and the description does not distinguish "
                  "consequences that follow from the withdrawal itself from service changes the "
                  "entity elects to make.",
               "WP-044", LEGAL),
    "CON-06": (1, "Testing of three withdrawal requests found processing continued after "
                  "withdrawal in all three. Marketing suppression was applied within 48 hours, "
                  "but the Snowflake warehouse, the CleverTap audience and the churn model "
                  "training set retained and continued to use the records. Median elapsed time "
                  "to full cessation could not be established because the entity does not "
                  "measure it.",
               "WP-045", ENG),
    "CON-07": (1, "The consent table records a current state per Data Principal with a single "
                  "last-updated timestamp. It does not retain the notice version, the interface, "
                  "the purposes in force at the time, or any history of change. For two of five "
                  "sampled Data Principals the entity could not demonstrate what was consented "
                  "to or when. The Act places the burden of proving valid consent on the Data "
                  "Fiduciary and that burden could not presently be discharged.",
               "WP-046", ENG),
    "CON-08": (1, "Purposes were extended twice in the period — advertising segments in "
                  "September 2025 and the churn model in January 2026 — without a fresh notice "
                  "or fresh consent. Existing consent was treated as covering the new purposes on "
                  "the basis of the general 'improve our services' wording.",
               "WP-047", LEGAL),
    # -- CMG ------------------------------------------------------------
    "CMG-01": (3, "The account aggregator relied upon is an RBI-licensed NBFC-AA and the entity "
                  "holds its certificate on file. Registration specifically as a Consent Manager "
                  "with the Data Protection Board has not been confirmed, and the entity has no "
                  "process for periodic re-confirmation of that status.",
               "WP-050", LEGAL),
    "CMG-02": (2, "Consent artefacts received through the aggregator are stored and the data "
                  "fetch is scoped to the artefact. Reconciliation between artefacts held by the "
                  "aggregator and consents recorded internally is not performed, so a revoked "
                  "artefact would not necessarily stop an internal reuse of previously fetched "
                  "financial information.",
               "WP-051", ENG),
    # -- LGU ------------------------------------------------------------
    "LGU-01": (2, "Where consent is not relied upon, the entity's documentation cites 'legitimate "
                  "use' generically rather than identifying the specific statutory limb. Two "
                  "activities — fraud analytics using device signals, and the credit bureau "
                  "reporting of repayment behaviour — rest on limbs that do not on their terms "
                  "extend to that processing.",
               "WP-055", LEGAL),
    "LGU-02": (3, "Employment-purpose processing is documented for payroll, benefits and "
                  "performance. The collections team's screen and keystroke monitoring is also "
                  "placed under this limb; the connection to safeguarding the employer from loss "
                  "or to provision of a service to the employee is asserted rather than "
                  "evidenced, and employees have not been informed of the monitoring.",
               "WP-056", PEOPLE),
    "LGU-03": (3, "Voluntary provision is relied upon for support interactions initiated by the "
                  "Data Principal, which is appropriate. The same limb is stretched to cover "
                  "retention of call recordings for model training, which is a different purpose "
                  "from the one for which the data was voluntarily provided.",
               "WP-057", CX),
    # -- RET ------------------------------------------------------------
    "RET-01": (2, "A retention schedule exists but is expressed at system level rather than by "
                  "data category and purpose, and defaults to 'as required by applicable law' for "
                  "11 of 19 systems. Snowflake and the S3 data lake have no defined retention "
                  "period at all; the oldest personal data located during testing dated from "
                  "2019.",
               "WP-060", ENG),
    "RET-02": (1, "Erasure on withdrawal or purpose completion is not implemented. The manual "
                  "runbook noted at CON-04 anonymises the CRM record but leaves the warehouse, "
                  "the ledger, the communications platforms and the backups untouched. RBI and "
                  "PMLA retention requirements were cited as justification but have not been "
                  "mapped to data categories, so they operate as a blanket exception rather than "
                  "a bounded one.",
               "WP-061", ENG),
    "RET-03": (1, "Erasure does not propagate. Testing confirmed that a record erased in Kavach "
                  "CRM remained present in Snowflake, in the dbt derived tables, in CleverTap and "
                  "in Gupshup's message logs. No processor has been issued an erasure "
                  "instruction in the period, and the vendor contracts contain no mechanism for "
                  "doing so.",
               "WP-062", ENG),
    "RET-04": (0, "There is no concept of deemed purpose completion on inactivity. Accounts "
                  "dormant since 2019 remain fully populated and continue to be included in "
                  "marketing audiences. Approximately 2.1 million Data Principals have had no "
                  "interaction with the platform for over three years.",
               "WP-063", ENG),
    "RET-05": (0, "No advance intimation is given before erasure, because no scheduled erasure "
                  "takes place. The requirement has not been designed for.",
               "WP-064", ENG),
    # -- RGT ------------------------------------------------------------
    "RGT-01": (2, "An access request route exists via the grievance form and produces a summary of "
                  "profile data. It does not include the identities of processors or other "
                  "recipients with whom data has been shared, nor a description of the processing "
                  "activities. Two of the four requests received in the period were answered "
                  "outside 30 days.",
               "WP-070", CX),
    "RGT-02": (3, "Correction and updating of profile data is self-service in the application and "
                  "works as described. Completion of incomplete records and correction of data "
                  "held only in the warehouse or with processors requires a manual request and is "
                  "not propagated, as noted at PUR-04.",
               "WP-071", ENG),
    "RGT-03": (1, "Erasure requests are accepted but cannot be fulfilled beyond the CRM, for the "
                  "reasons at RET-03. Three of the three erasure requests received were closed as "
                  "completed on the basis of CRM anonymisation alone, which overstates what was "
                  "done and creates a misleading record.",
               "WP-072", CX),
    "RGT-04": (0, "The right to nominate has not been implemented. There is no interface, no "
                  "record structure and no operating procedure for giving effect to a nomination "
                  "on death or incapacity.",
               "WP-073", PROD),
    "RGT-05": (3, "Identity verification for rights requests reuses the existing authenticated "
                  "session where the request originates in the app, which is proportionate. "
                  "Email-originated requests trigger a request for a self-attested identity "
                  "document, which exceeds what is necessary where the mailbox is the registered "
                  "one.",
               "WP-074", CX),
    "RGT-06": (2, "Rights requests arrive through the general support queue and are not "
                  "separately categorised, so volumes, ageing and outcomes cannot be reported. "
                  "The eight requests identified in the period were reconstructed manually from "
                  "mailbox searches during this assessment. No service level is defined.",
               "WP-075", CX),
    # -- GRV ------------------------------------------------------------
    "GRV-01": (2, "A grievance mechanism exists in the form of a web form and a support email "
                  "address, both monitored. There is no defined escalation path, no distinction "
                  "between a service complaint and a data protection grievance, and no owner "
                  "accountable for grievance outcomes as opposed to ticket closure.",
               "WP-080", CX),
    "GRV-02": (1, "Response times are not measured against any prescribed period because the "
                  "period has not been identified and no clock is started. Sampling of 15 "
                  "privacy-related tickets found a median first substantive response of 11 days "
                  "and a longest of 42 days.",
               "WP-081", CX),
    "GRV-03": (3, "The grievance route is published in the app, on the website and in the privacy "
                  "policy. It is not present in the Kavach Junior parent console and is not "
                  "included in transactional communications, which is where a dissatisfied Data "
                  "Principal is most likely to look.",
               "WP-082", CX),
    "GRV-04": (1, "No trend analysis is performed. Privacy grievances are not tagged, so the "
                  "recurring theme identified during this assessment — inability to stop "
                  "marketing contact after withdrawal — has never been reported to management as "
                  "a pattern despite appearing in 9 of the 15 tickets sampled.",
               "WP-083", CX),
    # -- SEC ------------------------------------------------------------
    "SEC-01": (3, "A security programme aligned to ISO 27001 is defined, owned by the CISO and "
                  "certified, with the certificate valid to August 2027. The statement of "
                  "applicability is scoped to the payments platform and excludes the collections "
                  "subsidiary and the corporate HRMS, both of which hold personal data.",
               "WP-090", CISO),
    "SEC-02": (3, "Role-based access control is enforced through Okta with quarterly recertification "
                  "for production systems. Recertification does not extend to Snowflake, where 41 "
                  "analyst accounts hold read access to unmasked customer tables, including 7 "
                  "belonging to former contractors whose engagements have ended.",
               "WP-091", CISO),
    "SEC-03": (3, "Data is encrypted at rest with AWS KMS and in transit with TLS 1.2 or above. "
                  "Column-level masking is applied in the production database but not in "
                  "Snowflake or in the pre-production environments, which are refreshed from "
                  "production without obfuscation.",
               "WP-092", CISO),
    "SEC-04": (4, "Centralised logging into a managed SIEM covers all in-scope production "
                  "systems, with documented use cases for privileged access, bulk export and "
                  "anomalous query patterns. Alert tuning is reviewed monthly and the "
                  "24x7 monitoring arrangement was evidenced through three sampled alerts and "
                  "their disposition.",
               "WP-093", CISO),
    "SEC-05": (3, "Vulnerability scanning runs weekly with defined remediation SLAs. Of 23 "
                  "critical findings raised in the period, 19 were closed within SLA; the four "
                  "exceptions relate to the legacy PPI ledger and have been open for over 120 "
                  "days without a documented risk acceptance.",
               "WP-094", CISO),
    "SEC-06": (3, "Change management is enforced through Freshservice with peer review and "
                  "automated security testing in the pipeline. Emergency changes bypass the "
                  "control and 14 per cent of production changes in the period were classified as "
                  "emergency, which is high enough to weaken the assurance the control provides.",
               "WP-095", ENG),
    "SEC-07": (4, "Backups are encrypted, replicated across availability zones and restore-tested "
                  "quarterly. The two restore tests in the period met their objectives and are "
                  "documented with evidence of data integrity verification.",
               "WP-096", CISO),
    "SEC-08": (3, "Background verification, confidentiality undertakings, endpoint management and "
                  "data loss prevention are in place for employees. Contractors in the "
                  "collections subsidiary use personally-owned devices with no endpoint control, "
                  "and physical access to the collections floor is not restricted from the "
                  "general office area.",
               "WP-097", CISO),
    "SEC-09": (3, "Annual penetration testing by an external firm covers the application and "
                  "infrastructure, and the most recent report is dated March 2026 with findings "
                  "tracked to closure. Testing has never been directed at the privacy controls "
                  "themselves — consent enforcement, erasure completeness or access segregation "
                  "in the warehouse.",
               "WP-098", CISO),
    # -- BRC ------------------------------------------------------------
    "BRC-01": (3, "The incident response procedure defines a personal data breach and correctly "
                  "captures unauthorised disclosure, acquisition, sharing, use, alteration, "
                  "destruction and loss of access. The definition is annexed to the security "
                  "procedure rather than integrated into triage, and the severity matrix used by "
                  "the on-call team is framed around availability and financial impact only, so a "
                  "confidentiality-only event scores low and may not escalate.",
               "WP-100", CISO),
    "BRC-02": (3, "Detection is strong for infrastructure and application events. Detection of "
                  "breaches arising from misuse of legitimate access — the Snowflake exposure at "
                  "SEC-02 being the clearest example — is not covered by any use case, and the "
                  "two incidents in the period were both identified through customer complaint "
                  "rather than monitoring.",
               "WP-101", CISO),
    "BRC-03": (2, "The procedure requires intimation to the Board but names neither the form nor "
                  "the period, both of which are left as 'per applicable law'. Neither of the two "
                  "incidents in the period was assessed for reportability, and no intimation has "
                  "ever been prepared or rehearsed. Given that s.8(6) carries the second highest "
                  "penalty in the Schedule, the absence of an operable mechanism is a material "
                  "exposure.",
               "WP-102", LEGAL),
    "BRC-04": (2, "There is no template, channel or owner for intimation to affected Data "
                  "Principals. The one incident in the period that affected identifiable "
                  "individuals — 3,400 loan applicants whose data was exposed through a "
                  "misconfigured partner API — was handled by customer service on a "
                  "reactive basis, with no proactive intimation and no record of who was told "
                  "what.",
               "WP-103", CX),
    "BRC-05": (3, "A breach register is maintained in Freshservice with cause, systems affected "
                  "and remediation. Entries do not record the categories or volume of personal "
                  "data affected, or the reportability assessment, both of which would be the "
                  "first things sought in an inquiry.",
               "WP-104", CISO),
    "BRC-06": (2, "A tabletop exercise was conducted in October 2025 covering a ransomware "
                  "scenario. No exercise has tested a personal data breach requiring regulatory "
                  "and Data Principal intimation. Post-incident actions from the partner API "
                  "incident remain open six months later with no owner recorded.",
               "WP-105", CISO),
    # -- CHD ------------------------------------------------------------
    "CHD-01": (2, "Kavach Junior collects date of birth and is designed for 13-17 year olds, so "
                  "child users are identified within that product. The main KavachPay application "
                  "relies on a self-declared 18-plus checkbox with no verification, and analysis "
                  "of KYC data during this assessment identified 1,847 accounts whose bureau or "
                  "document date of birth indicates the holder is under 18.",
               "WP-110", PROD),
    "CHD-02": (2, "The Kavach Junior journey requires the parent to initiate the account from "
                  "their own authenticated, KYC-verified session, which is a reasonable "
                  "foundation. The relationship between parent and child is self-declared and "
                  "unverified, and the consent captured from the parent is the same bundled "
                  "consent described at CON-01 rather than a consent directed at the child's "
                  "data.",
               "WP-111", PROD),
    "CHD-03": (0, "The advertising and analytics SDKs embedded in the KavachPay application are "
                  "active in the Kavach Junior experience. Testing confirmed that device "
                  "identifiers and in-app behavioural events for accounts flagged as minors are "
                  "transmitted to CleverTap and to the Meta SDK, and that those accounts are "
                  "eligible for inclusion in lookalike audiences. Children are therefore subject "
                  "to tracking, behavioural monitoring and targeted advertising. The prohibition "
                  "is absolute and is not cured by the parental consent obtained, and the "
                  "conduct engages the third highest penalty entry in the Schedule.",
               "WP-112", PROD),
    "CHD-04": (2, "No assessment of detrimental effect on children's wellbeing has been performed "
                  "for Kavach Junior. Features that warrant such an assessment — spending streak "
                  "rewards, peer comparison of savings, and push notifications timed to school "
                  "hours — were designed without privacy or wellbeing review, consistent with the "
                  "gate failure at PUR-05.",
               "WP-113", PROD),
    "CHD-05": (1, "Persons with disability having a lawful guardian are not identified and there "
                  "is no mechanism for a guardian to act on their behalf. Support agents "
                  "described handling such cases informally by accepting instructions from "
                  "family members, which is both an unaddressed obligation and an "
                  "impersonation risk.",
               "WP-114", CX),
    # -- PRO ------------------------------------------------------------
    "PRO-01": (3, "A vendor register lists 96 third parties with 34 flagged as processing "
                  "personal data. Onward recipients engaged by those processors are not recorded, "
                  "and four processors identified through expenditure analysis during this "
                  "assessment were absent from the register, including the third-party data "
                  "broker noted at PUR-01.",
               "WP-120", VENDOR),
    "PRO-02": (2, "Of 34 processors, 26 have an executed agreement containing data protection "
                  "terms. Eight are engaged on click-through terms or purchase orders alone, "
                  "including two with access to full customer records. The Act requires a valid "
                  "contract for engagement of a processor and does not admit a de facto "
                  "arrangement.",
               "WP-121", VENDOR),
    "PRO-03": (2, "Where agreements exist, security obligations are generally flowed down. "
                  "Erasure on instruction is absent from 21 of 26 agreements and breach "
                  "notification to the entity within a defined period is absent from 14. The "
                  "entity therefore cannot discharge its own erasure and intimation obligations "
                  "through its processors, which is the practical consequence identified at "
                  "RET-03 and BRC-03.",
               "WP-122", VENDOR),
    "PRO-04": (2, "Sub-processor authorisation is required in the standard template but the "
                  "template was adopted in 2024 and older agreements are silent. No processor "
                  "has notified a sub-processor change in the period, which given the vendors "
                  "involved is more likely to indicate the clause is not operating than that no "
                  "changes occurred.",
               "WP-123", VENDOR),
    "PRO-05": (3, "Annual assurance is obtained for the 12 processors classified as critical, "
                  "through SOC 2 reports or completed questionnaires, and exceptions are tracked. "
                  "The remaining 22 receive no periodic assurance and the classification driving "
                  "that split is based on spend rather than on the personal data accessed.",
               "WP-124", VENDOR),
    "PRO-06": (2, "Exit provisions requiring return or erasure appear in 15 of 26 agreements. Two "
                  "processors were disengaged in the period and neither provided a certificate of "
                  "erasure; in one case the entity's own records show data remained accessible in "
                  "the vendor's environment three months after termination.",
               "WP-125", VENDOR),
    # -- XBD ------------------------------------------------------------
    "XBD-01": (3, "Transfers are mapped for the principal SaaS platforms and the register records "
                  "destination country and hosting region. The mapping omits support access from "
                  "the Singapore affiliate, sub-processor locations, and the CleverTap and Meta "
                  "onward flows, so it understates the actual footprint.",
               "WP-130", ENG),
    "XBD-02": (2, "No mechanism exists for monitoring restricted-country notifications. The "
                  "entity became aware of the transfer restriction regime through this "
                  "assessment and has no owner for tracking it, which means a notification would "
                  "not be detected and acted upon.",
               "WP-131", LEGAL),
    "XBD-03": (2, "RBI payment system data localisation requirements are met for the payments "
                  "platform, with the annual system audit report on file. Localisation "
                  "requirements have not been assessed for the lending and analytics estates, and "
                  "the Snowflake account holds transaction-derived data in a configuration that "
                  "has not been reviewed against the RBI direction. Sectoral requirements of this "
                  "kind are expressly preserved and are not displaced by compliance with the Act.",
               "WP-132", LEGAL),
    "XBD-04": (2, "Standard contractual protections are present in the major SaaS agreements. "
                  "Transfers are not disclosed in the notice, no assessment of the destination "
                  "environment has been performed, and the Singapore affiliate's support access "
                  "operates under an intra-group arrangement that has never been documented.",
               "WP-133", LEGAL),
    # -- SDF ------------------------------------------------------------
    "SDF-01": (1, "No Data Protection Officer has been appointed. The Head of Legal & Compliance "
                  "performs the function informally alongside a broad commercial mandate, "
                  "reports to the General Counsel rather than to the board, and is not designated "
                  "as DPO in any board record. The statutory requirement is a DPO based in India "
                  "who represents the Significant Data Fiduciary and is responsible to the board, "
                  "and none of those three elements is presently satisfied.",
               "WP-140", CFO),
    "SDF-02": (0, "No independent data auditor has been appointed. Management's position was that "
                  "the existing ISO 27001 certification body discharges the requirement; that "
                  "engagement is an information security certification and does not evaluate "
                  "compliance with the Act.",
               "WP-141", CFO),
    "SDF-03": (1, "No Data Protection Impact Assessment has been conducted. A template was "
                  "drafted in January 2026 and remains unapproved and unused. The obligation is "
                  "periodic and applies to the entity as a Significant Data Fiduciary "
                  "irrespective of individual product risk.",
               "WP-142", LEGAL),
    "SDF-04": (1, "No periodic audit of compliance with the Act has been undertaken. This "
                  "assessment is the first exercise of its kind and was commissioned by "
                  "management rather than performed by an independent auditor, so it does not "
                  "itself discharge the obligation.",
               "WP-143", CFO),
    "SDF-05": (1, "Algorithmic due diligence is not performed. Three models act on personal data "
                  "with direct consequences for Data Principals — underwriting, collections "
                  "prioritisation and churn prediction — and none has been assessed for risk to "
                  "the rights of Data Principals. The underwriting model has documented fairness "
                  "testing performed for RBI purposes, which is the nearest available evidence "
                  "but is directed at a different question.",
               "WP-144", ENG),
    "SDF-06": (2, "The entity has not identified whether any transfer restriction specific to a "
                  "Significant Data Fiduciary applies to it, and has no process for monitoring "
                  "the position. The gap follows from XBD-02 and would be closed by the same "
                  "mechanism.",
               "WP-145", LEGAL),
    # -- BRD ------------------------------------------------------------
    "BRD-01": (2, "The entity has experience of responding to RBI inspections and has a "
                  "regulatory response process, which provides a partial foundation. No owner is "
                  "designated for Data Protection Board correspondence, and the evidence "
                  "deficiencies at GOV-07 and CON-07 mean the entity could not currently produce "
                  "the consent and notice records an inquiry would be most likely to seek.",
               "WP-150", LEGAL),
    "BRD-02": (1, "Management was not aware of the voluntary undertaking mechanism or that "
                  "mitigating action and its timeliness are express factors in determining a "
                  "penalty. The practical significance — that documented prompt remediation of "
                  "the findings in this report is itself risk mitigation — had not been "
                  "considered.",
               "WP-151", LEGAL),
    "BRD-03": (2, "A remediation tracker exists and carries 23 open privacy items. Fourteen have "
                  "no owner, 19 have no target date, and no budget has been allocated for the "
                  "engineering work that the erasure, consent and withdrawal findings in this "
                  "report will require. Without funding and ownership the plan is a list rather "
                  "than a commitment.",
               "WP-152", CFO),
}


def build() -> str:
    lib = load_library(os.path.join(ROOT, "controls"))
    a = Assessment.blank_for(lib, PROFILE)
    a.assessment_date = "2026-08-14"
    a.auditor_name = "Nandita Krishnan, CIPP/E, CISA"
    a.auditor_firm = "Sentinel Assurance LLP, Chartered Accountants"
    a.engagement_ref = "SA/DPDP/2026/0417"
    a.report_title = "DPDP Act, 2023 Compliance Audit Report"
    a.scope_statement = (
        "An assessment of the design and operating effectiveness of the entity's arrangements "
        "for compliance with the Digital Personal Data Protection Act, 2023 across the digital "
        "personal data processing activities of Kavach Financial Technologies Private Limited "
        "and its collections subsidiary, covering the systems and activities listed in the scope "
        "schedule. Fieldwork was performed between 27 July and 14 August 2026 and comprised "
        "document inspection, 19 process walkthroughs with control owners, inspection of system "
        "configuration, and substantive testing of consent, withdrawal, rights and erasure "
        "journeys on live and non-production environments."
    )
    a.limitations = a.limitations + [
        "Testing of erasure completeness was performed on non-production environments refreshed "
        "from production. Where a finding turns on data present in production only, this is "
        "stated in the finding.",
        "The account aggregator's own systems and controls were not examined. Reliance was "
        "placed on its licence status and on artefacts it made available to the entity.",
    ]

    in_scope = {c.id for c in lib.in_scope(PROFILE)}
    missing = sorted(in_scope - set(R))
    extra = sorted(set(R) - in_scope)
    if missing or extra:
        raise SystemExit(f"sample is incomplete.\n  missing responses: {missing}\n"
                         f"  responses for out-of-scope controls: {extra}")

    for cid, (score, finding, ref, owner) in R.items():
        r = a.response(cid)
        r.score = score
        r.finding = " ".join(finding.split())
        r.evidence_ref = ref
        r.owner = owner
        ctrl = lib.controls[cid]
        r.evidence = list(ctrl.evidence_expected[:2])

    out = os.path.join(HERE, "sample_assessment.json")
    a.save(out)
    return out


if __name__ == "__main__":
    p = build()
    print(f"wrote {p}")
