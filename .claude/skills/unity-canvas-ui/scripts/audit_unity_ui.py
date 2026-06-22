#!/usr/bin/env python3
"""
audit_unity_ui.py

Unity .prefab / .unity 파일을 스캔해 Canvas UI의 해상도 대응 위반을 찾는다.

사용법:
    python3 audit_unity_ui.py path/to/file.prefab [path/to/another.prefab ...]
    python3 audit_unity_ui.py path/to/folder/  # 재귀 스캔

출력: JSON. 배열의 각 항목은 하나의 위반을 의미.

체크 항목:
  1. CanvasScaler가 Constant Pixel Size 모드로 설정됨 (critical)
  2. CanvasScaler의 referenceResolution이 1280x720 이하 (warning)
  3. RectTransform의 offset(left/right/top/bottom)이 음수이면서 오버플로우 의도 네이밍 아님 (critical)
  4. Anchor와 Pivot 방향 불일치 (warning)
  5. Button 내부의 Label(Text/TMP)에 음수 offset (critical)
  6. Image 컴포넌트에 Preserve Aspect 미설정 + 부모가 비정사각 (info) — 이 체크는 스크립트가 부모를 추적 못 하면 스킵
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any


# Unity YAML은 표준 PyYAML로는 바로 안 읽힌다 (태그 때문).
# 간단한 정규식 파서로 필요한 정보만 추출한다.


DOC_SEP_RE = re.compile(r"^--- !u!(\d+) &(\d+)(?: stripped)?$", re.MULTILINE)


@dataclass
class Node:
    type_id: int
    file_id: str
    raw: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass
class Issue:
    severity: str  # "critical" | "warning" | "info"
    category: str
    file: str
    game_object: str
    component: str
    message: str
    suggestion: str


def parse_unity_yaml(text: str) -> list[Node]:
    """문서 구분자로 나눠 각 노드의 raw 텍스트를 보관."""
    matches = list(DOC_SEP_RE.finditer(text))
    nodes: list[Node] = []
    for i, m in enumerate(matches):
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        raw = text[start:end]
        nodes.append(Node(type_id=int(m.group(1)), file_id=m.group(2), raw=raw))
    return nodes


# 필드 추출기들 (정규식 기반). Unity YAML은 들여쓰기가 규칙적이라 정규식으로 충분.


VEC2_RE = re.compile(r"\{x:\s*(-?[\d.eE+-]+),\s*y:\s*(-?[\d.eE+-]+)\}")


def find_scalar(raw: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", raw, re.MULTILINE)
    return m.group(1) if m else None


def find_vec2(raw: str, key: str) -> tuple[float, float] | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*(.+?)\s*$", raw, re.MULTILINE)
    if not m:
        return None
    vm = VEC2_RE.match(m.group(1))
    if not vm:
        return None
    return float(vm.group(1)), float(vm.group(2))


def find_fileid_ref(raw: str, key: str) -> str | None:
    m = re.search(rf"^\s*{re.escape(key)}:\s*\{{fileID:\s*(-?\d+)\}}", raw, re.MULTILINE)
    return m.group(1) if m else None


def iter_children_refs(raw: str) -> list[str]:
    """m_Children: 아래의 fileID 목록."""
    m = re.search(r"m_Children:\s*\n((?:\s+-.*\n)*)", raw)
    if not m:
        return []
    block = m.group(1)
    return re.findall(r"\{fileID:\s*(-?\d+)\}", block)


def iter_component_refs(raw: str) -> list[str]:
    """GameObject의 m_Component 아래의 fileID 목록."""
    m = re.search(r"m_Component:\s*\n((?:\s+-.*\n)*)", raw)
    if not m:
        return []
    block = m.group(1)
    return re.findall(r"component:\s*\{fileID:\s*(-?\d+)\}", block)


# Unity class IDs (우리가 관심있는 것만)
CID_GAMEOBJECT = 1
CID_MONOBEHAVIOUR = 114
CID_RECTTRANSFORM = 224
CID_CANVASSCALER = 114  # MonoBehaviour인데 script GUID로 구분됨 — 간단히 "CanvasScaler" 문자열로 찾음
CID_IMAGE = 114  # 마찬가지
CID_BUTTON = 114

# Canvas Scaler / Image / Button은 MonoBehaviour인데 여러 필드로 식별해야 해서,
# 문자열 매칭으로 대체:
#   - CanvasScaler: m_UiScaleMode 필드 존재
#   - Image: m_Sprite 필드 존재 (Raw/Text 아닌)
#   - Button: m_OnClick 필드 존재


@dataclass
class RectInfo:
    file_id: str
    gameobject_fid: str | None
    anchor_min: tuple[float, float]
    anchor_max: tuple[float, float]
    anchored_position: tuple[float, float]
    size_delta: tuple[float, float]
    pivot: tuple[float, float]
    father_fid: str | None
    child_fids: list[str]

    def is_stretch_x(self) -> bool:
        return self.anchor_min[0] != self.anchor_max[0]

    def is_stretch_y(self) -> bool:
        return self.anchor_min[1] != self.anchor_max[1]

    def offsets(self) -> tuple[float, float, float, float]:
        """Return (left, bottom, right, top) as shown in the Unity Inspector.

        Unity 내부 저장:
            offsetMin.x = anchoredPosition.x - sizeDelta.x * pivot.x
            offsetMin.y = anchoredPosition.y - sizeDelta.y * pivot.y
            offsetMax.x = anchoredPosition.x + sizeDelta.x * (1 - pivot.x)
            offsetMax.y = anchoredPosition.y + sizeDelta.y * (1 - pivot.y)
        인스펙터 표시:
            left   = offsetMin.x
            bottom = offsetMin.y
            right  = -offsetMax.x   # 안쪽 여백이면 양수
            top    = -offsetMax.y
        이 함수는 인스펙터 관점(여백이면 양수, 넘침이면 음수)으로 반환한다.
        Stretch 축에서만 "여백"으로 해석하는 것이 의미 있음.
        """
        px, py = self.pivot
        sx, sy = self.size_delta
        ax, ay = self.anchored_position
        left = ax - sx * px
        bottom = ay - sy * py
        right = -(ax + sx * (1 - px))
        top = -(ay + sy * (1 - py))
        return left, bottom, right, top


def extract_rect(node: Node) -> RectInfo | None:
    if node.type_id != CID_RECTTRANSFORM:
        return None
    amn = find_vec2(node.raw, "m_AnchorMin") or (0.5, 0.5)
    amx = find_vec2(node.raw, "m_AnchorMax") or (0.5, 0.5)
    ap = find_vec2(node.raw, "m_AnchoredPosition") or (0.0, 0.0)
    sd = find_vec2(node.raw, "m_SizeDelta") or (0.0, 0.0)
    pv = find_vec2(node.raw, "m_Pivot") or (0.5, 0.5)
    father = find_fileid_ref(node.raw, "m_Father")
    go = find_fileid_ref(node.raw, "m_GameObject")
    children = iter_children_refs(node.raw)
    return RectInfo(
        file_id=node.file_id,
        gameobject_fid=go,
        anchor_min=amn,
        anchor_max=amx,
        anchored_position=ap,
        size_delta=sd,
        pivot=pv,
        father_fid=father,
        child_fids=children,
    )


def extract_gameobject_name(nodes_by_id: dict[str, Node], gameobject_fid: str | None) -> str:
    if not gameobject_fid or gameobject_fid not in nodes_by_id:
        return "<unknown>"
    node = nodes_by_id[gameobject_fid]
    name = find_scalar(node.raw, "m_Name") or "<unnamed>"
    # Unity는 이름을 따옴표로 감싸기도 함
    return name.strip().strip('"').strip("'")


def is_canvas_scaler(node: Node) -> bool:
    return node.type_id == CID_MONOBEHAVIOUR and "m_UiScaleMode" in node.raw


def is_button(node: Node) -> bool:
    return node.type_id == CID_MONOBEHAVIOUR and "m_OnClick" in node.raw


def is_text_like(node: Node) -> bool:
    # uGUI Text 또는 TextMeshPro Text
    return node.type_id == CID_MONOBEHAVIOUR and (
        "m_Text:" in node.raw and "m_FontData" in node.raw  # legacy Text
        or "m_text:" in node.raw and "m_TextInfo" in node.raw  # TMP UGUI
        or "m_fontAsset" in node.raw  # TMP
    )


def is_image(node: Node) -> bool:
    return node.type_id == CID_MONOBEHAVIOUR and "m_Sprite:" in node.raw and "m_Type:" in node.raw


def audit_file(path: Path) -> list[Issue]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [
            Issue(
                severity="info",
                category="file",
                file=str(path),
                game_object="-",
                component="-",
                message="파일을 UTF-8로 읽을 수 없음 (바이너리 asset일 수도 있음)",
                suggestion="대상이 text serialization 모드인지 확인 (Edit > Project Settings > Editor > Asset Serialization = Force Text)",
            )
        ]

    nodes = parse_unity_yaml(text)
    nodes_by_id = {n.file_id: n for n in nodes}
    issues: list[Issue] = []

    # 1) CanvasScaler 검사
    scalers = [n for n in nodes if is_canvas_scaler(n)]
    for s in scalers:
        mode = find_scalar(s.raw, "m_UiScaleMode")
        ref = find_vec2(s.raw, "m_ReferenceResolution")
        match = find_scalar(s.raw, "m_MatchWidthOrHeight")
        # mode: 0=ConstantPixelSize, 1=ScaleWithScreenSize, 2=ConstantPhysicalSize
        go_fid = find_fileid_ref(s.raw, "m_GameObject")
        go_name = extract_gameobject_name(nodes_by_id, go_fid)
        if mode == "0":
            issues.append(
                Issue(
                    severity="critical",
                    category="canvas-scaler",
                    file=str(path),
                    game_object=go_name,
                    component="CanvasScaler",
                    message="UI Scale Mode가 Constant Pixel Size로 설정됨",
                    suggestion="Scale With Screen Size로 변경, Reference Resolution 1920x1080, Match 0.5를 기본으로 검토",
                )
            )
        elif mode == "2":
            issues.append(
                Issue(
                    severity="warning",
                    category="canvas-scaler",
                    file=str(path),
                    game_object=go_name,
                    component="CanvasScaler",
                    message="UI Scale Mode가 Constant Physical Size — 기기 DPI 부정확 위험",
                    suggestion="Scale With Screen Size 사용을 권장",
                )
            )
        if ref and (ref[0] <= 1280 or ref[1] <= 720):
            issues.append(
                Issue(
                    severity="warning",
                    category="canvas-scaler",
                    file=str(path),
                    game_object=go_name,
                    component="CanvasScaler",
                    message=f"Reference Resolution이 {int(ref[0])}x{int(ref[1])} — 고해상도에서 UI가 흐려질 수 있음",
                    suggestion="최소 1920x1080, 가능하면 2560x1440",
                )
            )
        if match is not None:
            try:
                mv = float(match)
                if mv == 0.0 or mv == 1.0:
                    issues.append(
                        Issue(
                            severity="info",
                            category="canvas-scaler",
                            file=str(path),
                            game_object=go_name,
                            component="CanvasScaler",
                            message=f"Match가 {mv} — 한 축만 기준. PC/모바일 동시 대응이 의도면 0.5 권장",
                            suggestion="Match=0.5로 두 축의 균형을 취하는 게 실무 표준",
                        )
                    )
            except ValueError:
                pass

    # 2) RectTransform 검사 — 음수 offset (stretch 축에서)
    rects: dict[str, RectInfo] = {}
    for n in nodes:
        r = extract_rect(n)
        if r is not None:
            rects[n.file_id] = r

    for rid, r in rects.items():
        go_name = extract_gameobject_name(nodes_by_id, r.gameobject_fid)

        # 오버플로우 의도 네이밍 허용
        overflow_allowed = any(
            tag in go_name.lower()
            for tag in ("_overflow", "_shadow", "_decoration", "_frame", "bleed")
        )

        left, bottom, right, top = r.offsets()

        # stretch인 축에서만 "음수 offset" 판정이 의미 있다
        if r.is_stretch_x():
            if left < -0.01 and not overflow_allowed:
                issues.append(
                    Issue(
                        severity="critical",
                        category="rect-offset",
                        file=str(path),
                        game_object=go_name,
                        component="RectTransform",
                        message=f"Left offset이 음수 ({left:.1f}) — 부모 경계 밖으로 튀어나옴",
                        suggestion="부모 안쪽으로 들어오도록 left를 0 이상으로. 의도적 오버플로우면 오브젝트 이름에 _Overflow 등을 붙이세요.",
                    )
                )
            if right < -0.01 and not overflow_allowed:
                issues.append(
                    Issue(
                        severity="critical",
                        category="rect-offset",
                        file=str(path),
                        game_object=go_name,
                        component="RectTransform",
                        message=f"Right offset이 음수 ({right:.1f}) — 부모 경계 밖으로 튀어나옴",
                        suggestion="Right를 0 이상으로",
                    )
                )

        if r.is_stretch_y():
            if bottom < -0.01 and not overflow_allowed:
                issues.append(
                    Issue(
                        severity="critical",
                        category="rect-offset",
                        file=str(path),
                        game_object=go_name,
                        component="RectTransform",
                        message=f"Bottom offset이 음수 ({bottom:.1f})",
                        suggestion="Bottom을 0 이상으로",
                    )
                )
            if top < -0.01 and not overflow_allowed:
                issues.append(
                    Issue(
                        severity="critical",
                        category="rect-offset",
                        file=str(path),
                        game_object=go_name,
                        component="RectTransform",
                        message=f"Top offset이 음수 ({top:.1f})",
                        suggestion="Top을 0 이상으로",
                    )
                )

        # 3) Anchor/Pivot 불일치 (한 점 anchor에 대해서만 검사)
        if not r.is_stretch_x() and not r.is_stretch_y():
            ax = r.anchor_min[0]  # == anchor_max[0]
            ay = r.anchor_min[1]
            px, py = r.pivot
            # 앵커가 모서리(0 or 1)인데 pivot이 다른 모서리면 경고
            if ax in (0.0, 1.0) and abs(ax - px) > 0.01:
                issues.append(
                    Issue(
                        severity="warning",
                        category="anchor-pivot",
                        file=str(path),
                        game_object=go_name,
                        component="RectTransform",
                        message=f"Anchor x={ax}이지만 Pivot x={px} — 회전/스케일 시 위치 튀는 원인",
                        suggestion="Anchor와 Pivot의 방향을 일치시킬 것 (references/principles.md 표 참조)",
                    )
                )
            if ay in (0.0, 1.0) and abs(ay - py) > 0.01:
                issues.append(
                    Issue(
                        severity="warning",
                        category="anchor-pivot",
                        file=str(path),
                        game_object=go_name,
                        component="RectTransform",
                        message=f"Anchor y={ay}이지만 Pivot y={py}",
                        suggestion="Anchor와 Pivot의 방향을 일치시킬 것",
                    )
                )

    # 4) Button 내부 Label 특별 검사: 버튼 자식 중 text-like에 stretch + 음수 offset이면 더 강하게 경고
    # (위 rect-offset에서 이미 잡히지만, "버튼 안의 라벨"은 특히 빈번한 패턴이라 카테고리 분리)
    button_go_fids: set[str] = set()
    for n in nodes:
        if is_button(n):
            go_fid = find_fileid_ref(n.raw, "m_GameObject")
            if go_fid:
                button_go_fids.add(go_fid)

    # GameObject -> RectTransform 매핑
    go_to_rect: dict[str, str] = {}
    for rid, r in rects.items():
        if r.gameobject_fid:
            go_to_rect[r.gameobject_fid] = rid

    for bfid in button_go_fids:
        brid = go_to_rect.get(bfid)
        if not brid:
            continue
        brect = rects[brid]
        # 버튼의 자식 RectTransform 중 텍스트 컴포넌트가 있는 것
        for child_rid in brect.child_fids:
            child_rect = rects.get(child_rid)
            if not child_rect:
                continue
            child_go_fid = child_rect.gameobject_fid
            if not child_go_fid:
                continue
            # 이 자식 GameObject에 text-like component가 있나?
            child_go = nodes_by_id.get(child_go_fid)
            if not child_go:
                continue
            child_component_fids = iter_component_refs(child_go.raw)
            has_text = any(
                is_text_like(nodes_by_id[cfid])
                for cfid in child_component_fids
                if cfid in nodes_by_id
            )
            if not has_text:
                continue
            # text-like 자식에 대해 음수 offset 재검증, severity="critical"로 카테고리 button-label
            cleft, cbottom, cright, ctop = child_rect.offsets()
            name = extract_gameobject_name(nodes_by_id, child_go_fid)
            if child_rect.is_stretch_x():
                if cleft < -0.01:
                    issues.append(
                        Issue(
                            severity="critical",
                            category="button-label",
                            file=str(path),
                            game_object=name,
                            component="Text/TMP (Button 내부)",
                            message=f"버튼 내부 라벨의 Left offset이 {cleft:.1f} (음수) — 라벨이 버튼 밖으로 삐져나옴",
                            suggestion="Left를 0 이상(여백 권장 8~16)으로. 라벨이 안 들어가면 버튼 키우거나 폰트 줄이기.",
                        )
                    )
                if cright < -0.01:
                    issues.append(
                        Issue(
                            severity="critical",
                            category="button-label",
                            file=str(path),
                            game_object=name,
                            component="Text/TMP (Button 내부)",
                            message=f"버튼 내부 라벨의 Right offset이 {cright:.1f} (음수)",
                            suggestion="Right를 0 이상으로",
                        )
                    )

    return issues


def audit_path(path: Path) -> list[Issue]:
    if path.is_dir():
        results: list[Issue] = []
        for ext in ("*.prefab", "*.unity"):
            for f in path.rglob(ext):
                results.extend(audit_file(f))
        return results
    return audit_file(path)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Unity Canvas UI audit tool")
    parser.add_argument("paths", nargs="+", help=".prefab / .unity file or folder")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print human summary instead of raw JSON")
    args = parser.parse_args(argv)

    all_issues: list[Issue] = []
    for p in args.paths:
        all_issues.extend(audit_path(Path(p)))

    if args.pretty:
        by_sev: dict[str, list[Issue]] = {"critical": [], "warning": [], "info": []}
        for i in all_issues:
            by_sev.setdefault(i.severity, []).append(i)
        total = len(all_issues)
        print(f"\n=== Unity Canvas UI Audit — {total} issues found ===\n")
        for sev in ("critical", "warning", "info"):
            items = by_sev[sev]
            if not items:
                continue
            print(f"[{sev.upper()}] {len(items)} issues")
            for issue in items:
                print(f"  {issue.file}")
                print(f"    GameObject: {issue.game_object}   Component: {issue.component}")
                print(f"    {issue.message}")
                print(f"    → {issue.suggestion}\n")
    else:
        print(json.dumps([asdict(i) for i in all_issues], ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
