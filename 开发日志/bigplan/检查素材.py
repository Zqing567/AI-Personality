"""只读检查当前素材路径、原图字节、GIF 元数据与 Markdown 引用。"""

from collections import Counter
from hashlib import sha1
from pathlib import Path
import json
import re
from urllib.parse import unquote

from PIL import Image


ROOT = Path(__file__).resolve().parents[2]
INDEX_DIR = ROOT / "DeepSeek大肥鱼" / "模型事迹及其表情包"
baseline = json.loads((ROOT / "原始素材清单.json").read_text(encoding="utf-8"))
mapping = json.loads((INDEX_DIR / "素材迁移映射.json").read_text(encoding="utf-8"))["items"]
current = json.loads((INDEX_DIR / "素材索引.json").read_text(encoding="utf-8"))["items"]

original_by_id = {item["id"]: item for item in baseline["images"]}
current_by_id = {item["id"]: item for item in current}
assert len(original_by_id) == len(mapping) == 46
assert len(current_by_id) == 42
assert len({item["new_path"].casefold() for item in mapping}) == 46
assert {item["id"] for item in mapping} == set(original_by_id)
assert set(current_by_id) == {f"A{i:02d}" for i in range(2, 44)}

actual_hashes = []
gif_count = 0
for item in mapping:
    asset_id = item["id"]
    original = original_by_id[asset_id]
    assert item["old_path"] == original["path"], asset_id
    path = ROOT / item["new_path"]
    data = path.read_bytes()
    assert len(data) == original["bytes"], asset_id
    blob_hash = sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
    assert blob_hash == item["git_blob_sha"] == original["git_blob_sha"], asset_id
    actual_hashes.append(blob_hash)
    with Image.open(path) as image:
        assert image.format == original["format"], asset_id
        assert getattr(image, "n_frames", 1) == original["frame_count"], asset_id
        if image.format == "GIF":
            assert image.n_frames > 1, asset_id
            gif_count += 1
    if asset_id in current_by_id:
        current_item = current_by_id[asset_id]
        assert current_item["path"] == item["new_path"], asset_id
        assert current_item["original_path"] == item["old_path"], asset_id
        for field in ("credits", "privacy", "permission_status", "source_url"):
            assert field in current_item, (asset_id, field)
        for event in current_item["events"]:
            assert (INDEX_DIR / "事迹" / event).is_file(), (asset_id, event)

assert Counter(actual_hashes) == Counter(x["git_blob_sha"] for x in baseline["images"])
assert gif_count == 8
assert len(list((ROOT / "DeepSeek大肥鱼" / "表情包").rglob("*.*"))) == 42

links = 0
for document in ROOT.rglob("*.md"):
    if ".git" in document.parts or ".obsidian" in document.parts:
        continue
    text = document.read_text(encoding="utf-8")
    for raw_target in re.findall(r"\]\(([^)]+)\)", text):
        if "://" in raw_target or raw_target.startswith("mailto:"):
            continue
        local_target = raw_target.split("#", 1)[0]
        if not local_target:
            continue
        assert " " not in local_target, (document, raw_target)
        assert (document.parent / unquote(local_target)).exists(), (document, raw_target)
        links += 1

print(f"通过：46 张图字节与 Git blob 哈希一致；8 个 GIF 均为多帧；{links} 条本地 Markdown 链接可解析。")
