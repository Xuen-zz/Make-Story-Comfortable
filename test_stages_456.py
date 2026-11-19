# test_stages_456.py
import urllib.request
import json
import time

url_trans = "http://127.0.0.1:7860/api/generate/translate"
payload_trans = {
    "llm_config_name": "Gemini 3.8 Flash (内置免密)",
    "filepath": "output/目标市场欧美试水",
    "chapter_num": 4,
    "target_style": "Alpha Romance (GoodNovel / Dreame 爆款标准)",
    "custom_guidance": "Native English prose, natural pacing, zero AI cliches"
}

print("Testing Step 4: Translate Chapter 4...")
req = urllib.request.Request(
    url_trans,
    data=json.dumps(payload_trans).encode('utf-8'),
    headers={"Content-Type": "application/json"}
)

en_text = ""
with urllib.request.urlopen(req, timeout=300) as resp:
    for line in resp:
        line = line.decode('utf-8', errors='replace').strip()
        if not line.startswith("data: "): continue
        raw = line[6:].strip()
        if not raw: continue
        try:
            ev = json.loads(raw)
            if ev.get("type") == "result":
                en_text = ev.get("content", "")
                print(f"Translation done! Length: {len(en_text)} chars, words: {len(en_text.split())}")
        except Exception:
            pass

assert en_text, "Translation failed"

# Save en_text to chapters_en
import os
os.makedirs("output/目标市场欧美试水/chapters_en", exist_ok=True)
with open("output/目标市场欧美试水/chapters_en/chapter_4_en.txt", "w", encoding="utf-8") as f:
    f.write(en_text)

print("Saved chapter_4_en.txt. Now testing Step 5: Audit...")
url_audit = "http://127.0.0.1:7860/api/generate/audit_translation"
payload_audit = {
    "llm_config_name": "Gemini 3.8 Flash (内置免密)",
    "filepath": "output/目标市场欧美试水",
    "chapter_num": 4
}
req_audit = urllib.request.Request(
    url_audit,
    data=json.dumps(payload_audit).encode('utf-8'),
    headers={"Content-Type": "application/json"}
)

audit_report = ""
with urllib.request.urlopen(req_audit, timeout=300) as resp:
    for line in resp:
        line = line.decode('utf-8', errors='replace').strip()
        if not line.startswith("data: "): continue
        raw = line[6:].strip()
        if not raw: continue
        try:
            ev = json.loads(raw)
            if ev.get("type") == "result":
                audit_report = ev.get("content", "")
                print(f"Audit done! Length: {len(audit_report)}")
                print("Audit conclusion preview:")
                for l in audit_report.split("\n"):
                    if "结论" in l or "通过" in l or "需重译" in l or "5." in l:
                        print("  ", l)
        except Exception:
            pass

print("Finished testing translation & audit!")
