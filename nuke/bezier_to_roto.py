"""
Select Bezier Nodes and copy them into 1 Roto Node
"""

import math
import re

import nuke
from nuke.rotopaint import Shape, ShapeControlPoint, CVec2


def get_bezier_points(node):
    "get bezier node points for each keyframe"
    bezier_points = node["points"].toScript().strip("{}")
    points = []
    for keyframe in bezier_points.split("} {"):
        p_key = 0
        p_dict = {}
        for k in keyframe.split("\n"):
            if not k:
                continue
            p_dict[p_key] = k.strip("{}")
            p_key += 1
        points.append(p_dict)

    return points


def get_keyframes(shape):
    "determin keyframe of set points from shape"
    if not shape:
        # no animation, return only 1 keyframe
        return [nuke.root().firstFrame()]

    key_list = shape[1:-1].split(" ")
    keyframes = []
    for enum, k in enumerate(key_list):
        if not re.search(r"\d", k):
            continue

        elif k.startswith("x"):
            keyframes.append(int(k[1:]))

        elif not keyframes and k == "0":
            keyframes.append(0)

        elif not key_list[enum - 1].startswith("x"):
            keyframes.append(keyframes[-1] * 2 - keyframes[-2])

    return keyframes


def set_interpolation_type(acp):
    "set interpolation of AnimControlPoint"
    index = 0
    while True:
        try:
            pos_curve = acp.getPositionAnimCurve(index)
        except BaseException:
            break

        for num_key in range(pos_curve.getNumberOfKeys()):
            key = pos_curve.getKey(num_key)
            key.interpolationType = 258  # linear interpolation

        index += 1


def collect_anim_keys(root):
    "clean collection of ShapeControlPoints to call set_interpolation_type"
    for shape in root:
        for point in shape:
            set_interpolation_type(point.center)
            set_interpolation_type(point.featherCenter)
            set_interpolation_type(point.rightTangent)
            set_interpolation_type(point.featherRightTangent)
            set_interpolation_type(point.leftTangent)
            set_interpolation_type(point.featherLeftTangent)


def set_controlpoints(index, keyframes, points):
    "create roto ShapeControlPoint and set attributes of bezier points"
    scp = ShapeControlPoint()
    for enum, point in enumerate(points):
        frame = keyframes[enum]
        p = [float(f) for f in point[index].split(" ")]
        pl = len(p)
        scp.center.addPositionKey(frame, CVec2(p[0], p[1]))

        if pl < 5:
            continue

        angle = p[3]
        tangent_rx = p[2] * math.cos(angle)
        tangent_ry = p[2] * math.sin(angle)

        if pl >= 6:
            offset = p[5]
        else:
            offset = 0.0

        tangent_lx = -(p[4] * math.cos(angle + offset))
        tangent_ly = -(p[4] * math.sin(angle + offset))

        scp.rightTangent.addPositionKey(frame, CVec2(tangent_rx, tangent_ry))
        scp.featherRightTangent.addPositionKey(frame, CVec2(tangent_rx, tangent_ry))
        scp.leftTangent.addPositionKey(frame, CVec2(tangent_lx, tangent_ly))
        scp.featherLeftTangent.addPositionKey(frame, CVec2(tangent_lx, tangent_ly))

        if pl < 7:
            scp.featherCenter.addPositionKey(frame, CVec2(0, 0))
            continue

        if pl >= 8:
            angle = p[3] + p[7]

        center_offx = p[6] * math.sin(angle)
        center_offy = p[6] * math.cos(angle)
        scp.featherCenter.addPositionKey(frame, CVec2(-center_offx, center_offy))

        if pl < 10:
            continue

        angle = p[3] + p[9]
        right_offx = (p[8] + p[2]) * math.cos(angle)
        right_offy = (p[8] + p[2]) * math.sin(angle)

        scp.featherRightTangent.addPositionKey(frame, CVec2(right_offx, right_offy))

        if pl < 11:
            scp.featherLeftTangent.addPositionKey(frame, CVec2(-right_offx, -right_offy))
            continue

        if pl >= 12:
            offset = p[11]
        else:
            offset = 0.0

        left_offx = -(p[10] + p[4]) * math.cos(angle + offset)
        left_offy = -(p[10] + p[4]) * math.sin(angle + offset)

        scp.featherLeftTangent.addPositionKey(frame, CVec2(left_offx, left_offy))

    return scp


def copy_bezier_to_roto():
    "copy shapes from selected bezier nodes into 1 roto node"
    selected_nodes = nuke.selectedNodes("Bezier")

    if not selected_nodes:
        nuke.message("Please select the bezier node(s) you want to copy to a roto node.")
        return

    non_linear = [
        n.name() for n in selected_nodes if not n["linear"].value() and n["shape"].toScript()
    ]

    if non_linear:
        verb = "are" if len(non_linear) > 1 else "is"
        question = (
            f"{', '.join(non_linear)} {verb} not interpolated linear.\n"
            + "All shapes in the Roto Node will be linear.\nContinue Anyway?"
        )
        if not nuke.ask(question):
            return

    roto = nuke.nodes.Roto()

    for b in selected_nodes:
        shape = b["shape"].toScript()
        points = get_bezier_points(b)
        keyframes = get_keyframes(shape)

        roto_shape = Shape(roto["curves"])
        roto_shape.name = b.name()

        all_points = len(points[0])
        for index in range(all_points):
            roto_shape.append(set_controlpoints(index, keyframes, points))
            roto["curves"].changed()

    roto["curves"].rootLayer.append(roto_shape)
    collect_anim_keys(roto["curves"].rootLayer)


if __name__ == "__main__":
    copy_bezier_to_roto()
