import json
import pandas as pd
import argparse
from datetime import datetime, date

# run with:
# python rank.py --candidates candidates.jsonl --out submission.csv

def load_candidates(path):
    candidates = []
    if path.endswith(".gz"):
        import gzip
        with gzip.open(path, "rt") as f:
            for line in f:
                if line.strip():
                    candidates.append(json.loads(line))
    elif path.endswith(".json"):
        with open(path) as f:
            candidates = json.load(f)
    else:
        with open(path) as f:
            for line in f:
                if line.strip():
                    candidates.append(json.loads(line))
    print(f"loaded {len(candidates)} candidates")
    return candidates


# I read the JD really carefully - the role needs people who actually
# shipped retrieval/ranking systems. not just people with AI on their resume.
# so title matters a lot, and skill duration matters (0 months = sus)

AI_TITLES = [
    "ml engineer", "machine learning engineer", "ai engineer",
    "nlp engineer", "applied scientist", "search engineer",
    "ranking engineer", "recommendation", "deep learning engineer",
    "llm engineer", "senior ml", "senior ai", "staff ml", "staff ai",
    "applied ml", "retrieval", "conversational ai"
]

# these are the skills the JD says are non-negotiable
CORE_SKILLS = [
    "embeddings", "sentence-transformers", "faiss", "pinecone", "weaviate",
    "qdrant", "milvus", "elasticsearch", "opensearch", "vector",
    "dense retrieval", "semantic search", "rag", "bm25",
    "ndcg", "mrr", "ranking", "learning to rank", "a/b testing",
    "information retrieval", "hybrid search", "reranking"
]

NLP_LLM = [
    "nlp", "transformers", "bert", "gpt", "llm", "fine-tuning",
    "hugging face", "lora", "qlora", "openai", "natural language"
]

ML_GENERAL = [
    "python", "pytorch", "tensorflow", "scikit-learn", "xgboost",
    "machine learning", "deep learning", "mlflow"
]

# cities the JD specifically calls out
GOOD_CITIES = [
    "pune", "noida", "hyderabad", "mumbai", "delhi", "gurgaon",
    "gurugram", "bengaluru", "bangalore", "ncr", "new delhi"
]

# consulting firms - JD says these are a red flag if it's your only background
CONSULTING = [
    "tcs", "tata consultancy", "infosys", "wipro", "accenture",
    "cognizant", "capgemini", "hcl", "tech mahindra"
]

# non-AI jobs that keyword stuff (JD warned about this explicitly)
BAD_TITLES = [
    "hr manager", "marketing", "content writer", "sales",
    "human resources", "product manager", "business analyst",
    "finance", "scrum master", "ui/ux", "qa engineer", "recruiter"
]


def title_score(title):
    t = title.lower()
    if any(x in t for x in BAD_TITLES):
        return -0.2   # keyword stuffer trap
    if any(x in t for x in AI_TITLES):
        return 1.0
    # data scientist is ok but not perfect for this role
    if "data scientist" in t or "data engineer" in t:
        return 0.5
    if "software engineer" in t or "backend" in t:
        return 0.3
    return 0.1


def skill_score(skills_list):
    if not skills_list:
        return 0.0

    PROF = {"beginner": 0.1, "intermediate": 0.4, "advanced": 0.75, "expert": 1.0}
    
    core_hit = 0.0
    nlp_hit = 0.0
    ml_hit = 0.0

    for s in skills_list:
        name = s.get("name", "").lower()
        prof = PROF.get(s.get("proficiency", "beginner"), 0.1)
        duration = s.get("duration_months", 0)

        # if someone claims expert but used it 0 months, that's sketchy
        # real experience leaves a trace
        if s.get("proficiency") == "expert" and duration == 0:
            prof = prof * 0.3
        elif s.get("proficiency") == "advanced" and duration == 0:
            prof = prof * 0.5
        elif duration >= 24:
            prof = prof * 1.1

        for kw in CORE_SKILLS:
            if kw in name:
                core_hit = max(core_hit, prof)
                break

        for kw in NLP_LLM:
            if kw in name:
                nlp_hit = max(nlp_hit, prof)
                break

        for kw in ML_GENERAL:
            if kw in name:
                ml_hit = max(ml_hit, prof)
                break

    # core retrieval/ranking skills are what this role really needs
    score = core_hit * 0.55 + nlp_hit * 0.25 + ml_hit * 0.20
    return min(score, 1.0)


def experience_score(candidate):
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    
    yoe = profile.get("years_of_experience", 0)
    
    # JD says 5-9 years, sweet spot is 6-8
    if 6 <= yoe <= 8:
        exp_s = 1.0
    elif 5 <= yoe < 6 or 8 < yoe <= 9:
        exp_s = 0.8
    elif 4 <= yoe < 5 or 9 < yoe <= 11:
        exp_s = 0.6
    elif yoe > 11:
        exp_s = 0.4
    else:
        exp_s = 0.2

    # check if they've actually shipped things - look at career descriptions
    prod_words = ["production", "deployed", "shipped", "real users", "at scale", "live", "serving"]
    all_desc = " ".join(c.get("description", "").lower() for c in career)
    prod_count = sum(1 for w in prod_words if w in all_desc)
    prod_bonus = min(prod_count * 0.05, 0.25)

    # penalize if they only worked at big consulting firms
    companies = [c.get("company", "").lower() for c in career]
    consulting_only = all(any(firm in co for firm in CONSULTING) for co in companies) if companies else False
    consulting_penalty = -0.2 if consulting_only else 0

    # startup/small company experience - JD is a series A startup, they like this
    startup_months = sum(
        c.get("duration_months", 0) for c in career
        if c.get("company_size", "") in ("1-10", "11-50", "51-200")
    )
    startup_bonus = 0.1 if startup_months >= 18 else 0

    # title chaser check - lots of short jobs
    if len(career) >= 4:
        avg_tenure = sum(c.get("duration_months", 0) for c in career) / len(career)
        if avg_tenure < 15:
            exp_s -= 0.15  # job hopper

    return max(0, min(1.0, exp_s + prod_bonus + consulting_penalty + startup_bonus))


def location_score(candidate):
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    
    loc = profile.get("location", "").lower()
    country = profile.get("country", "").lower()
    relocate = signals.get("willing_to_relocate", False)

    if any(city in loc for city in GOOD_CITIES):
        return 1.0
    if country == "india" or "india" in loc:
        return 0.7 if relocate else 0.5
    # outside india - JD says case by case, no visa sponsorship
    return 0.3 if relocate else 0.1


def behavioral_score(signals):
    # this is the multiplier part - a great profile that's been inactive
    # for 6 months is basically not hirable right now
    
    mult = 1.0

    # how recently were they active?
    last_active = signals.get("last_active_date", "2020-01-01")
    try:
        last = datetime.strptime(last_active[:10], "%Y-%m-%d").date()
        days_ago = (date(2026, 1, 1) - last).days
    except:
        days_ago = 365

    if days_ago > 365:
        mult *= 0.35
    elif days_ago > 180:
        mult *= 0.55
    elif days_ago > 90:
        mult *= 0.80
    elif days_ago <= 30:
        mult *= 1.05

    # open to work is an obvious signal
    if signals.get("open_to_work_flag"):
        mult *= 1.08
    else:
        mult *= 0.85

    # response rate - if they never reply to recruiters, they're not actually looking
    rr = signals.get("recruiter_response_rate", 0.5)
    if rr < 0.15:
        mult *= 0.5
    elif rr < 0.40:
        mult *= 0.80
    elif rr >= 0.70:
        mult *= 1.05

    # notice period - JD explicitly says they want under 30 days ideally
    notice = signals.get("notice_period_days", 60)
    if notice <= 30:
        mult *= 1.08
    elif notice <= 60:
        mult *= 1.0
    elif notice <= 90:
        mult *= 0.88
    else:
        mult *= 0.65

    # interview completion - people who ghost interviews are a red flag
    icr = signals.get("interview_completion_rate", 0.7)
    if icr < 0.5:
        mult *= 0.75

    # github activity - JD says they value external validation of work
    github = signals.get("github_activity_score", -1)
    if github > 60:
        mult *= 1.08
    elif github > 30:
        mult *= 1.03

    return max(0.2, min(1.3, mult))


def is_suspicious(candidate):
    # catch honeypot profiles - dataset has ~80 of these
    # they get disqualified if we rank too many of them
    
    profile = candidate.get("profile", {})
    career = candidate.get("career_history", [])
    skills = candidate.get("skills", [])

    # expert in everything but 0 months on all of them
    if len(skills) >= 5:
        expert_skills = [s for s in skills if s.get("proficiency") in ("expert", "advanced")]
        zero_duration = [s for s in skills if s.get("duration_months", 0) == 0]
        if len(expert_skills) >= 6 and len(zero_duration) == len(skills):
            return True

    # claimed experience way more than career history adds up to
    total_months = sum(c.get("duration_months", 0) for c in career)
    claimed = profile.get("years_of_experience", 0)
    if claimed > 0 and total_months > 0:
        if claimed > (total_months / 12) + 5:
            return True

    # marketing/hr person with tons of expert AI skills - obvious trap
    title = profile.get("current_title", "").lower()
    if any(b in title for b in BAD_TITLES):
        expert_ai = [
            s for s in skills
            if s.get("proficiency") == "expert"
            and any(kw in s.get("name", "").lower() for kw in ["machine learning", "deep learning", "llm", "bert"])
        ]
        if len(expert_ai) >= 4:
            return True

    return False


def make_reasoning(candidate, scores):
    p = candidate.get("profile", {})
    sig = candidate.get("redrob_signals", {})

    title = p.get("current_title", "")
    yoe = p.get("years_of_experience", 0)
    loc = p.get("location", "")
    notice = sig.get("notice_period_days", -1)
    rr = sig.get("recruiter_response_rate", -1)
    github = sig.get("github_activity_score", -1)
    active = sig.get("open_to_work_flag", False)

    bits = [f"{title}, {yoe}y exp, {loc}"]

    if scores["skill"] > 0.6:
        bits.append("strong retrieval/embedding skills")
    if scores["skill"] > 0.3:
        bits.append("relevant ML skills")
    if scores["exp"] > 0.7:
        bits.append("right exp range with production background")
    if active:
        bits.append("actively looking")
    if github > 60:
        bits.append(f"active on GitHub ({github}/100)")
    if notice >= 0 and notice <= 30:
        bits.append(f"{notice}d notice")
    if notice >= 0 and notice > 90:
        bits.append(f"concern: {notice}d notice period")
    if rr >= 0 and rr < 0.25:
        bits.append(f"concern: low recruiter response ({rr:.0%})")

    return ". ".join(bits[:4]) + "."


def score_candidate(c):
    if is_suspicious(c):
        return 0.001

    p = c.get("profile", {})
    sig = c.get("redrob_signals", {})

    t_score = title_score(p.get("current_title", ""))
    s_score = skill_score(c.get("skills", []))
    e_score = experience_score(c)
    l_score = location_score(c)
    b_mult  = behavioral_score(sig)

    raw = (
        t_score * 0.35 +
        s_score * 0.25 +
        e_score * 0.20 +
        l_score * 0.10 +
        ((t_score + s_score + e_score) / 3) * 0.10
    )

    return max(0.001, min(0.999, raw * b_mult))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidates", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    candidates = load_candidates(args.candidates)

    print("scoring...")
    results = []
    for i, c in enumerate(candidates):
        if i % 10000 == 0 and i > 0:
            print(f"  {i}/{len(candidates)}")

        score = score_candidate(c)
        p = c.get("profile", {})
        sig = c.get("redrob_signals", {})

        results.append({
            "candidate_id": c["candidate_id"],
            "score": score,
            "title": p.get("current_title", ""),
            "yoe": p.get("years_of_experience", 0),
            "loc": p.get("location", ""),
            "t_score": title_score(p.get("current_title", "")),
            "s_score": skill_score(c.get("skills", [])),
            "e_score": experience_score(c),
            "_candidate": c,
        })

    df = pd.DataFrame(results)
    # spec says: ties broken by candidate_id ascending
    df = df.sort_values(["score", "candidate_id"], ascending=[False, True]).reset_index(drop=True)

    top100 = df.head(100).copy()
    top100["rank"] = range(1, len(top100) + 1)

    print("\nTop 10 preview:")
    print(top100[["rank", "candidate_id", "score", "title", "yoe", "loc"]].head(10).to_string())

    rows = []
    for _, row in top100.iterrows():
        c = row["_candidate"]
        reasoning = make_reasoning(c, {
            "skill": row["s_score"],
            "exp": row["e_score"],
            "title": row["t_score"],
        })
        rows.append({
            "candidate_id": row["candidate_id"],
            "rank": int(row["rank"]),
            "score": round(row["score"], 4),
            "reasoning": reasoning,
        })

    out_df = pd.DataFrame(rows)[["candidate_id", "rank", "score", "reasoning"]]
    out_df.to_csv(args.out, index=False)
    print(f"\nsaved to {args.out}")


if __name__ == "__main__":
    main()
