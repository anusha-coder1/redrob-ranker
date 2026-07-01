import streamlit as st
import json
import pandas as pd
import sys, os

sys.path.insert(0, os.path.dirname(__file__))
from rank import score_candidate, make_reasoning, load_candidates

st.title("Redrob Candidate Ranker")
st.write("Upload a candidates JSON/JSONL file and get a ranked CSV back.")
st.caption("Senior AI Engineer JD · Redrob Hackathon Submission")

st.info("This is a demo sandbox. Upload up to 100-200 candidates to test. The full 100K run happens locally.")

uploaded = st.file_uploader("Upload candidates (.json or .jsonl)", type=["json", "jsonl"])

if uploaded:
    try:
        content = uploaded.read().decode("utf-8")
        if uploaded.name.endswith(".jsonl"):
            candidates = [json.loads(l) for l in content.splitlines() if l.strip()]
        else:
            candidates = json.loads(content)
        st.write(f"Loaded {len(candidates)} candidates")
    except Exception as e:
        st.error(f"Couldn't parse file: {e}")
        st.stop()

    if len(candidates) > 300:
        st.warning("Trimming to 300 for sandbox demo")
        candidates = candidates[:300]

    with st.spinner("Scoring..."):
        results = []
        for c in candidates:
            from rank import title_score, skill_score, experience_score
            p = c.get("profile", {})
            sc = score_candidate(c)
            results.append({
                "candidate_id": c["candidate_id"],
                "score": sc,
                "title": p.get("current_title", ""),
                "yoe": p.get("years_of_experience", 0),
                "location": p.get("location", ""),
                "_c": c,
                "t_s": title_score(p.get("current_title", "")),
                "s_s": skill_score(c.get("skills", [])),
                "e_s": experience_score(c),
            })

    df = pd.DataFrame(results).sort_values("score", ascending=False).reset_index(drop=True)
    df["rank"] = range(1, len(df) + 1)
    top = df.head(100)

    st.success(f"Done! Showing top {min(len(top), 100)}")
    st.dataframe(top[["rank", "candidate_id", "score", "title", "yoe", "location"]])

    # build csv
    import io, csv
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["candidate_id", "rank", "score", "reasoning"])
    for _, row in top.iterrows():
        c = row["_c"]
        r = make_reasoning(c, {"skill": row["s_s"], "exp": row["e_s"], "title": row["t_s"]})
        w.writerow([row["candidate_id"], int(row["rank"]), round(row["score"], 4), r])

    st.download_button("Download CSV", buf.getvalue().encode(), "submission.csv", "text/csv")

    # quick stats
    col1, col2 = st.columns(2)
    col1.metric("Top score", f"{df['score'].iloc[0]:.3f}")
    col2.metric("Median score", f"{df['score'].median():.3f}")
