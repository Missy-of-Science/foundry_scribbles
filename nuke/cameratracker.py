"read camera tracker's feature tracks and export as txt file "

import os
import ntpath
from datetime import datetime

import nuke


def append_frames(serialized_data, index, tmp, startframe, lifetime_idx=0):
    """append data sets to converted track list
    -   serialized_data: serialise knob as list of lists
        index: current single list's index
        tmp: current single list
        startframe: first frame of tracker
        lifetime_idx: position offset of tracker's lifetime
    - returns track's position points and accuracy of pattern
    """
    first_header = serialized_data[index + 1]
    position_list = []
    frame = 1

    if len(first_header) < 5:
        second_header = serialized_data[index + 2]
        lifetime = second_header[6 + lifetime_idx]
        position_list.append([startframe, tmp[2 + lifetime_idx], tmp[3 + lifetime_idx], tmp[1]])

        if len(second_header) == 13 + lifetime_idx:
            position_list.append(
                [startframe + frame, second_header[2], second_header[3], second_header[1]]
            )
            frame += 1

        for x in range(2, int(lifetime)):
            items = serialized_data[index + 1 + x]
            position_list.append([startframe + frame, items[2], items[3], items[1]])
            frame += 1
            if len(items) > 7 and items[7] == second_header[0]:
                position_list.append(
                    [
                        startframe + frame,
                        second_header[2],
                        second_header[3],
                        second_header[1],
                    ]
                )
                frame += 1

    else:
        lifetime = first_header[4 + lifetime_idx]
        position_list.append([startframe, tmp[2 + lifetime_idx], tmp[3 + lifetime_idx], tmp[1]])

        for x in range(1, int(lifetime)):
            items = serialized_data[index + 1 + x]
            position_list.append([startframe + x, items[2], items[3], items[1]])

    return position_list


def export_cameratrack(node):
    """export serialize knob as list items
    - node: which node triggered the action
    returns nested positions and pattern accuracy across frames in track list
    """
    s = node["serializeKnob"].toScript()

    output = []

    serialized_data = [line.split(" ") for line in s.split("\n")]
    serialized_data.pop(0)

    if int(serialized_data[1][2]):
        startframe = serialized_data[1][3]
        identification = serialized_data[2][-3]
        output.append(append_frames(serialized_data, 2, serialized_data[2], int(startframe), 2))
    else:
        startframe = serialized_data[0][3]
        identification = serialized_data[1][-3]
        output.append(append_frames(serialized_data, 1, serialized_data[1], int(startframe), 2))

    for index, tmp in enumerate(serialized_data):
        if tmp[-1] == identification:
            footnote = serialized_data[index - 1]
            if footnote[1] == "0" and footnote[2] == "1":
                startframe = footnote[3]
            output.append(append_frames(serialized_data, index, tmp, int(startframe), 0))

    return output


def file_create():
    "write txt file for pfTrack to read"
    n = nuke.thisNode()
    root_name = nuke.root().name()
    exported_tracks = export_cameratrack(n)
    counter = 1
    os.chdir(os.path.dirname(__file__))
    logpath = f"{os.path.dirname(root_name)}/export"
    basename = ntpath.basename(root_name)
    i = basename.rfind("_v")
    if i == -1:
        clean = os.path.splitext(basename)[0]
    else:
        clean = basename[:i]
    filename = f'{clean}_featuretracks_{n.name()}_{datetime.now().strftime("%Y-%m-%d_%H-%M")}.txt'
    txt_file = os.path.join(logpath, filename)

    with open(txt_file, "w") as f:
        for item in exported_tracks:
            f.write("\n")
            f.write("\n")

            f.write(f'"Nuketrack_{counter:04}"\n')
            f.write("1\n")
            f.write(f"{len(item)}\n")
            for i in item:
                line = "".join(str(i)[1:-1].split("'")) + "\n"
                f.write(line.replace(",", ""))

            counter += 1

    nuke.message(f"textfile created: {filename}")

def create_knob():
    "create knob inside Cameratracker Node"
    n = nuke.thisNode()
    usertab = nuke.Tab_Knob("User", "Export to PFTrack")
    knob = nuke.PyScript_Knob(
        "setfeattrack",
        "Export Feature Tracks",
        "file_create()",
    )
    if not n.knob("User"):
        n.addKnob(usertab)
    if not n.knob("setfeattrack"):
        n.addKnob(knob)
    if n.knob("attention"):
        n.removeKnob("attention")