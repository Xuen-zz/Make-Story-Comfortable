# test_pipeline.py
import urllib.request
import json
import time

url = "http://127.0.0.1:7860/api/generate/pipeline_chapter"
payload = {
    "llm_config_name": "Gemini 3.8 Flash (内置免密)",
    "emb_config_name": "默认 (离线/免学模式)",
    "filepath": "output/目标市场欧美试水",
    "chapter_num": 4,
    "word_number": 3000,
    "user_guidance": "",
    "characters_involved": "",
    "key_items": "",
    "scene_location": "",
    "time_constraint": "",
    "style_name": "",
    "narrative_style_name": "",
    "xp_type": "",
    "target_style": "Alpha Romance (GoodNovel / Dreame 爆款标准)",
    "auto_retry_translation": True,
    "scene_by_scene": True
}

req = urllib.request.Request(
    url,
    data=json.dumps(payload).encode('utf-8'),
    headers={"Content-Type": "application/json"}
)

print("Sending request to pipeline_chapter...")
t0 = time.time()
with urllib.request.urlopen(req, timeout=600) as resp:
    op_id = ""
    for line in resp:
        line = line.decode('utf-8', errors='replace').strip()
        if not line.startswith("data: "):
            continue
        data_str = line[6:].strip()
        if not data_str:
            continue
        try:
            ev = json.loads(data_str)
            ev_type = ev.get("type")
            if ev_type == "started":
                op_id = ev.get("operation_id")
                print(f"[{time.time()-t0:.1f}s] Pipeline started, op_id={op_id}")
            elif ev_type == "progress":
                desc = ev.get("message", "")
                val = ev.get("value", 0)
                content = ev.get("content", "")
                if content:
                    try:
                        c_json = json.loads(content)
                        if c_json.get("pipeline_event") == "stage_update":
                            stg = c_json.get("stage")
                            stg_name = c_json.get("stage_name")
                            stg_status = c_json.get("status")
                            msg = c_json.get("message")
                            print(f"[{time.time()-t0:.1f}s] Stage {stg} ({stg_name}) -> {stg_status}: {msg[:60]}")
                    except Exception:
                        pass
                else:
                    print(f"[{time.time()-t0:.1f}s] Progress ({val:.2f}): {desc[:60]}")
            elif ev_type == "result":
                content = ev.get("content", "")
                print(f"[{time.time()-t0:.1f}s] Pipeline Completed! Result size={len(content)}")
                try:
                    res_json = json.loads(content)
                    print("Success:", res_json.get("success"))
                    print("Audit Pass:", res_json.get("audit_pass"))
                    print("Retry Occurred:", res_json.get("retry_occurred"))
                    print("Draft length:", len(res_json.get("draft", "")))
                    print("Polished length:", len(res_json.get("polished", "")))
                    print("Translation length:", len(res_json.get("translation", "")))
                except Exception as e:
                    print("Result parse error:", e)
                break
            elif ev_type == "error":
                print(f"[{time.time()-t0:.1f}s] Pipeline Error: {ev.get('message')}")
                break
        except Exception as err:
            pass

print("Finished testing pipeline.")
