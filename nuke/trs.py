""" set Translate/Rotate and Scale at once (2017)
based on EnableTrackerTRS by narayani.com.br
last updated 2024
"""

import nuke
import nukescripts


def get_tracknames(node):
    "http://community.foundry.com/discuss/topic/103371"
    tracks_toscript = node["tracks"].toScript().split(" \n} \n{ \n ")
    tracks_toscript.pop(0)
    tracks_list = str(tracks_toscript)[2:].split("\\n")
    tracks_list.pop(-1)
    tracks_list.pop(-1)
    outlist = []

    for i in tracks_list:
        outlist.append(i.split('"')[1])

    return outlist


def toggle_tracker_trs():
    "set TRS Values in Tracker at once"
    n = nuke.thisNode()
    trs = {"t": 6, "r": 7, "s": 8}

    if n.Class() == "Tracker4":
        tracks = len(get_tracknames(n))

        p = nukescripts.panels.PythonPanel("TRS")

        p.setTooltip("Select the boxes to enable TRS respectivly")

        for k, v in trs.items():
            knob = nuke.Boolean_Knob(k, k.upper())
            knob.setValue(n["tracks"].getValue(v))
            p.addKnob(knob)

        ret = p.showModalDialog()

        if ret == 1:
            for k, v in trs.items():
                value = p.knobs()[k].value()
                for i in range(0, tracks):
                    n["tracks"].setValue(value, 31 * i + v)

    else:
        nuke.message("This is a Tracker4 feature, please select a Tracker.")


if __name__ == "__main__":
    animation_menu = nuke.menu("Animation")
    animation_menu.addCommand("toggle TRS", "toggle_tracker_trs()")
