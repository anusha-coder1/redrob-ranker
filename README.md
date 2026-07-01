# Redrob Hackathon — Candidate Ranker

My submission for the Intelligent Candidate Discovery & Ranking challenge.

## What I built

A candidate scoring system that ranks 100K candidates for the Senior AI Engineer JD at Redrob.

The key insight from reading the JD carefully: **keyword matching is explicitly called out as a trap**. The JD literally says a candidate who has all the AI keywords but works as a Marketing Manager is not a fit. So I built the scorer around that — the candidate's *actual role and career history* matters more than what's in their skills section.

## How the scoring works

```
final_score = (title_fit × 0.35 + skill_depth × 0.25 + experience × 0.20 + location × 0.10 + coherence × 0.10) × behavioral_multiplier
```

**Title fit (35%)** — this is the biggest signal. Someone currently working as an ML Engineer, NLP Engineer, or Applied Scientist scores high. An HR Manager with a bunch of AI skills in their profile scores low. The JD warned about exactly this pattern.

**Skill depth (25%)** — I look at embeddings, vector databases (Pinecone, FAISS, Qdrant, etc.), ranking/IR skills, and NLP/LLM skills. But I also check `duration_months` — if someone lists "expert" at a skill but has 0 months of usage, that's suspicious and I reduce that skill's weight.

**Experience (20%)** — The JD says 5–9 years, but makes clear the sweet spot is really 6–8. I also look for production deployment language in their career descriptions ("deployed", "shipped", "at scale", "real users") and penalize if their entire career is at TCS/Infosys/Wipro etc. (the JD explicitly flags consulting-only backgrounds).

**Location (10%)** — JD prefers Pune/Noida but accepts all major Indian cities. Outside India scores low since they don't sponsor visas.

**Behavioral multiplier (0.2–1.3×)** — This one is important. A perfect candidate who hasn't logged in for 6 months and has a 5% recruiter response rate isn't actually hirable. I use the `redrob_signals` to discount inactive or unresponsive candidates.

## What I tried that didn't work

I initially tried using sentence-transformers to embed the JD and compare it against a text dump of each candidate profile. The cosine similarity scores looked reasonable but they completely failed at the keyword stuffer problem — a Marketing Manager listing 15 AI skills would score high because the word overlap with the JD was high. Exactly the trap the JD warned about.

I also tried weighing GitHub activity much more heavily but found it was filtering out great candidates who just don't have public repos (which is fine for most product company engineers).

The rule-based approach with explicit penalties for the things the JD calls out turned out to work better for this specific problem.

## Honeypot handling

The dataset has ~80 honeypot profiles with impossible data (e.g., expert at 10 skills but 0 months on all of them, claimed years of experience that doesn't add up with their career history). I detect these and score them near zero. In the 100K run, found 25 suspicious profiles.

## How to run

```bash
pip install pandas

# on the full dataset
python rank.py --candidates ./candidates.jsonl --out ./submission.csv

# quick test on sample
python rank.py --candidates ./sample_candidates.json --out ./test.csv

# validate before submitting
python validate_submission.py submission.csv
```

Takes about 60-90 seconds on CPU for 100K candidates. No GPU needed, no API calls, no internet required during ranking.

## Files

```
rank.py                    # main scorer
app.py                     # streamlit demo for the sandbox requirement  
requirements.txt
validate_submission.py     # from the hackathon bundle
sample_candidates.json     # from the hackathon bundle
submission_metadata.yaml
```
