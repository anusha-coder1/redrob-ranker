import gradio as gr
import json
import csv
import io
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from rank import score_candidate, make_reasoning, title_score, skill_score, experience_score

def rank_candidates(file):
    if file is None:
        return "Please upload a file.", None

    try:
        with open(file.name, "r", encoding="utf-8") as f:
            content = f.read()

        if file.name.endswith(".jsonl"):
            candidates = [json.loads(l) for l in content.splitlines() if l.strip()]
        else:
            candidates = json.loads(content)
            if isinstance(candidates, dict):
                candidates = [candidates]
    except Exception as e:
        return f"Error reading file: {e}", None

    if len(candidates) > 300:
        candidates = candidates[:300]

    results = []
    for c in candidates:
        p = c.get("profile", {})
        sc = score_candidate(c)
        results.append({
            "candidate_id": c["candidate_id"],
            "score": sc,
            "title": p.get("current_title", ""),
            "yoe": p.get("years_of_experience", 0),
            "location": p.get("location", ""),
            "t_s": title_score(p.get("current_title", "")),
            "s_s": skill_score(c.get("skills", [])),
            "e_s": experience_score(c),
            "_c": c,
        })

    results.sort(key=lambda x: (-x["score"], x["candidate_id"]))
    top = results[:100]

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["candidate_id", "rank", "score", "reasoning"])
    table_rows = []

    for i, row in enumerate(top, 1):
        c = row["_c"]
        r = make_reasoning(c, {"skill": row["s_s"], "exp": row["e_s"], "title": row["t_s"]})
        w.writerow([row["candidate_id"], i, round(row["score"], 4), r])
        table_rows.append([i, row["candidate_id"], round(row["score"], 4), row["title"], row["yoe"], row["location"]])

    out_path = "/tmp/submission.csv"
    with open(out_path, "w") as f:
        f.write(buf.getvalue())

    summary = f"Ranked {len(results)} candidates. Showing top 20 preview.\n\n"
    summary += f"{'Rank':<5} {'ID':<15} {'Score':<7} {'Title':<35} {'YoE':<5} Location\n"
    summary += "-" * 90 + "\n"
    for row in table_rows[:20]:
        summary += f"{row[0]:<5} {row[1]:<15} {row[2]:<7.3f} {str(row[3])[:34]:<35} {row[4]:<5} {row[5]}\n"

    return summary, out_path


demo = gr.Interface(
    fn=rank_candidates,
    inputs=gr.File(label="Upload candidates (.json or .jsonl)"),
    outputs=[
        gr.Textbox(label="Results (top 20 preview)", lines=25),
        gr.File(label="Download submission.csv"),
    ],
    title="Redrob Candidate Ranker",
    description="Upload a candidates JSON/JSONL file to get a ranked CSV. Senior AI Engineer JD · Redrob Hackathon.",
)

if __name__ == "__main__":
    demo.launch()
