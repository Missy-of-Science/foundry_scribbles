"Automate Dataset Creation Based on keyframes of frames"
import re

import nuke
from PySide2.QtWidgets import QMessageBox, QInputDialog
from PySide2.QtCore import Qt

from import_from_flow import setup_shotgun

# how the script is imported into Nuke, important for the PyScript_Knobs to work properly
MODULE = "create_mldataset."


def create_explosion_node():
    "base node that contains keyframes and explode button"
    noop = nuke.createNode("NoOp")
    noop.setName("KeyFramer")

    frame = nuke.Array_Knob("frame", "Frame:")
    frame.setExpression("frame")
    frame.setTooltip("animated frame list, used for dataset creation")

    add_frames = nuke.PyScript_Knob(
        "add_keyframes",
        "add Keyframes",
        f"{MODULE}set_keyframes(nuke.thisNode()['frame'], {MODULE}get_keyframes())",
    )
    add_frames.setTooltip("add keyframes by flow note or list input e.g.")
    clear_frames = nuke.PyScript_Knob(
        "clear_keyframes",
        "clear Keyframes",
        "nuke.thisNode()['frame'].clearAnimated()\n"
        + "nuke.thisNode()['frame'].setExpression('frame')",
    )

    explode = nuke.PyScript_Knob(
        "explode_script", "explode", f"{MODULE}explode_mldataset(nuke.thisNode())"
    )
    explode.setFlag(nuke.STARTLINE)
    explode.setTooltip("create Frameholds and appendClip with preceeding FrameRange Node")

    howto = (
        "<strong>How to use the KeyFramer Node:</strong><br><br>"
        + "&nbsp;&nbsp;&nbsp;&nbsp;#1 Add keyframes on frames that need a FrameHold Node<br>"
        + "&nbsp;&nbsp;&nbsp;&nbsp;#2 Press 'explode' Button to create ML Dataset Nodes<br>"
        + "&nbsp;&nbsp;&nbsp;&nbsp;#3 Wonder in awe"
    )

    noop.addKnob(frame)
    noop.addKnob(add_frames)
    noop.addKnob(clear_frames)
    noop.addKnob(nuke.Text_Knob(""))
    noop.addKnob(explode)
    noop.addKnob(nuke.Text_Knob(""))
    noop.addKnob(nuke.Text_Knob("howto", "", howto))


def get_id():
    "get id from note url"
    url = QInputDialog.getText(
        None,
        "Flow URL",
        "Enter Note's URL:",
    )

    if not url[1]:
        return False

    search_object = re.search(r"Note.*?(\d+)", url[0])
    if search_object:
        return int(search_object.group(1))

    return None


def get_frames_from_note():
    "get the note the annotated frames relate to"
    sg = setup_shotgun()
    frames = []
    note_id = get_id()

    if not note_id:
        if note_id is None:
            nuke.alert("Could not get valid id for Note.")
        return None

    note = sg.find_one("Note", [["id", "is", note_id]], ["attachments"])

    if not note:
        nuke.alert(f"{note_id} doesn't match a Note in Flow PTR.")
        return None

    if not note["attachments"]:
        nuke.alert("Note does not have anything attached!")
        return None

    for attm in note["attachments"]:
        if not attm["name"].startswith("annot_version"):
            continue

        version, frame, _ = attm["name"].split(".")
        if version.endswith("v2"):
            frames.append(int(frame))
        else:
            sg_version = sg.find_one(
                "Version", [["id", "is", int(version.split("_")[-1])]], ["sg_first_frame"]
            )
            frames.append(int(frame) + sg_version["sg_first_frame"])

    return sorted(frames)


def get_frames_from_list():
    "get a comma separated list of frames"

    framelist = QInputDialog.getText(None, "Enter List", "Enter frames separated by comma:")

    if framelist[1]:
        return [int(f.strip()) for f in framelist[0].split(",")]
    else:
        return []


def set_keyframes(knob, framelist):
    "set keys on frames from flow attachments"

    if framelist is None:
        return

    for frame in framelist:
        knob.animation(0).setKey(frame, frame)


def get_keyframes():
    "setup QMessageBox for different option to get keyframes"
    framelist = None

    msg_box = QMessageBox(
        QMessageBox.Question, "Add Keyframes", "Choose how to get keyframes or cancel."
    )
    msg_box.setWindowFlags(msg_box.windowFlags() | Qt.WindowStaysOnTopHint)
    msg_box.setToolTip(
        "There are no keyframes set to create dataset.\n"
        + "Choose an option on how to optain the keyframes."
    )
    msg_box.addButton("Import from Flow Note", QMessageBox.ActionRole)
    msg_box.addButton("Enter list of frames", QMessageBox.ActionRole)
    msg_box.addButton(QMessageBox.Cancel)

    ask = msg_box.exec()

    if ask == 0:
        framelist = get_frames_from_note()

    elif ask == 1:
        framelist = get_frames_from_list()

    return framelist


def explode_mldataset(n):
    """create frameholds for each keyframe in node
    with preceeding frameFange and appended appendClip"""

    dependents = n.dependent()

    frames = n["frame"].getKeyList()
    if not frames:
        set_keyframes(n["frame"], get_keyframes())
        frames = n["frame"].getKeyList()

    fh_nodes = []
    xpos = n.xpos()
    ypos = n.ypos()
    height = 55
    width = 120
    fh_xpos = xpos - int(((len(frames) / 2.0) * width))

    fr = nuke.nodes.FrameRange()
    fr["first_frame"].setValue(1)
    fr["last_frame"].setValue(1)
    fr.setInput(0, n)
    fr["xpos"].setValue(xpos)
    fr["ypos"].setValue(ypos + height)

    for frame in frames:
        fh = nuke.nodes.FrameHold()
        fh["firstFrame"].setValue(frame)
        fh.setInput(0, fr)
        fh["xpos"].setValue(fh_xpos)
        fh_xpos += width
        fh["ypos"].setValue(ypos + (4 * height))

        fh_nodes.append(fh)

    a = nuke.nodes.AppendClip()
    a["firstFrame"].setValue(1001)
    a["meta_from_first"].setValue(False)

    for enum, node in enumerate(fh_nodes):
        a.setInput(enum, node)

    if not fh_nodes:
        a.setInput(0, fr)

    a["xpos"].setValue(xpos)
    a["ypos"].setValue(ypos + (6 * height))

    for d in dependents:
        for i in range(d.inputs()):
            if d.input(i) == n:
                d.setInput(i, a)


if __name__ == "__main__":
    MODULE = ""
    create_explosion_node()
    # explode_mldataset(nuke.toNode("KeyFramer"))
