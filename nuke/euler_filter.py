"""
Euler Filter by Henriette Adel, June 2017
algorithm of filter based on:
https://forum.highend3d.com/t/euler-filter-algorithm/6147
last updated 2024 (code cleanup)
"""

import nuke
import nukescripts


def euler_filter(first, last, ro, kopie):
    "filter the rotation mathematically"
    k = nuke.thisKnob()

    progress = nuke.ProgressTask("Fixing rotation")

    if kopie:
        n = nuke.thisNode()
        for i in nuke.allNodes():
            i.setSelected(False)

        n.setSelected(True)
        nuke.nodeCopy(r"%clipboard%")
        n.setSelected(False)

        new = nuke.nodePaste(r"%clipboard%")
        new["label"].setValue("Euler Filter")
        k = new[k.name()]
    else:
        nuke.thisNode()["label"].setValue("Euler Filter")

    xyz = [ro.find("X"), ro.find("Y"), ro.find("Z")]

    for i in range(first, last + 1):
        if progress.isCancelled():
            break

        norm = (i - first) * 100 / (last - first)
        progress.setProgress(int(norm))
        progress.setMessage(f"Frame: {i}")

        nuke.root()["frame"].setValue(i)

        curr = k.valueAt(i)
        prev = k.valueAt(i - 1)

        if (
            round(abs(prev[xyz[0]] - curr[xyz[0]])) > 90
            and round(abs(prev[xyz[1]] - curr[xyz[1]])) > 90
            and round(abs(prev[xyz[2]] - curr[xyz[2]])) > 90
        ):
            for axis in xyz:
                if prev[axis] < curr[axis]:
                    k.setValueAt(curr[axis] - 180, i, axis)
                else:
                    k.setValueAt(curr[axis] + 180, i, axis)

        for axis in xyz:
            if round(abs(prev[axis] - curr[axis])) > 270:
                if prev[axis] < curr[axis]:
                    k.setValueAt(curr[axis] - 360, i, axis)
                else:
                    k.setValueAt(curr[axis] + 360, i, axis)

    del progress


def euler_fix():
    "bake animation and prepare euler animation before fixing"
    knob = nuke.thisKnob()
    baked = True

    axes = ["x", "y", "z"]

    if knob.hasExpression():
        if nuke.ask("This curve is created by an expression. Would you like to bake it now?"):
            ret = nuke.getFramesAndViews(
                "Choose a Framerange!",
                f"{nuke.root().firstFrame()}-{nuke.root().lastFrame()}",
            )
            frame_range = nuke.FrameRange(ret[0])
            for axis in axes:
                nuke.animation(
                    f"{knob.name()}.{axis}",
                    "generate",
                    (
                        str(frame_range.first()),
                        str(frame_range.last()),
                        "1",
                        "y",
                        f"{knob.name()}.{axis}",
                    ),
                )
        else:
            return

    if knob.isAnimated():
        firsts_keys = []
        lasts_keys = []

        if len(knob.animations()) < 3:
            nuke.message(
                "This calculation only works with 3 different Inputs. Please select another knob."
            )
        else:
            for a in knob.animations():
                f = int(list(a.keys())[0].x)
                l = int(list(a.keys())[-1].x)
                firsts_keys.append(f)
                lasts_keys.append(l)

                if len(list(a.keys())) != int(list(a.keys())[-1].x - list(a.keys())[0].x + 1):
                    baked = False

            first = min(firsts_keys)
            last = max(lasts_keys)

            if not baked:
                if nuke.ask("This curve doesn't seem to be baked. Would you like to do that now?"):
                    nuke.animation(
                        f"{knob.name()}.x",
                        "generate",
                        (str(first), str(last), "1", "y", f"{knob.name()}.x"),
                    )
                    nuke.animation(
                        f"{knob.name()}.y",
                        "generate",
                        (str(first), str(last), "1", "y", f"{knob.name()}.y"),
                    )
                    nuke.animation(
                        f"{knob.name()}.z",
                        "generate",
                        (str(first), str(last), "1", "y", f"{knob.name()}.z"),
                    )

            rl = ["XYZ", "XZY", "YXZ", "YZX", "ZXY", "ZYX"]

            p = nukescripts.panels.PythonPanel("EULER Filter")

            p.addKnob(nuke.Int_Knob("first", "start frame"))
            p.addKnob(nuke.Int_Knob("last", "end frame"))
            p.addKnob(nuke.Enumeration_Knob("ro", "rotation order", rl))

            if nuke.thisNode().knob("rot_order"):
                ro = nuke.thisNode()["rot_order"].value()
            else:
                ro = "XYZ"
                p.addKnob(
                    nuke.Text_Knob(
                        "msg",
                        "WARNING\n\n",
                        "This knob has no rotation order.\n Please select the correct one.",
                    )
                )

            check = nuke.Boolean_Knob("kopie", "Copy values into new Node?")
            check.setFlag(nuke.STARTLINE)
            p.addKnob(check)

            p.knobs()["ro"].setValue(ro)
            p.knobs()["first"].setValue(first)
            p.knobs()["last"].setValue(last)
            p.knobs()["kopie"].setValue(False)

            ret = p.showModalDialog()

            if ret == 1:
                if len(knob.animations()) > 3:
                    nuke.message(
                        "This calculation only works with 3 different Inputs. "
                        + "The rest will be ignored."
                    )
                ro = p.knobs()["ro"].value()
                first = p.knobs()["first"].value()
                last = p.knobs()["last"].value()
                kopie = p.knobs()["kopie"].value()

                euler_filter(first, last, ro, kopie)
    else:
        nuke.message("This knob is not animated.")


if __name__ == "__main__":
    animation_menu = nuke.menu("Animation")
    animation_menu.addCommand("Euler Filter", "euler_fix()")
