"import versions from flow production tracking as ReadNodes into nuke"

import json
import os
import sys
import re

import nuke
from PySide2 import QtWidgets, QtCore


class SGPlaylistDialog(QtWidgets.QDialog):
    """Dialog Class where additional Fields can be imported to Hiero"""

    def __init__(self):
        super(SGPlaylistDialog, self).__init__()

        self.layout = QtWidgets.QFormLayout()
        self.setLayout(self.layout)
        self.possible_fields = [
            "sg_path_to_client_proxy",
            "sg_path_to_editorial_proxy",
            "sg_path_to_frames",
            "sg_path_to_grading_proxy",
            "sg_path_to_original_source",
            "sg_path_to_qc_proxy",
            "sg_path_to_resolution_proxy",
        ]

        self.setModal(True)
        self.setWindowTitle("Select Playlist and Version Fields")
        self.setToolTip(
            "Copy a Playlist URL and choose the field you want to be imported into Hiero."
        )

        self.build_ui()

    def build_ui(self):
        """setup ui on initialisation"""
        self.url_edit = QtWidgets.QLineEdit()
        self.url_edit.textChanged.connect(self.is_valid_url)

        self.field_widget = QtWidgets.QComboBox()
        self.field_widget.addItems(self.possible_fields)
        self.field_widget.setCurrentText("sg_path_to_frames")

        self.group_box = QtWidgets.QCheckBox("Import into Group")
        self.group_box.setChecked(True)

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel, QtCore.Qt.Horizontal
        )
        self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        # self.url_edit.setText("Playlist_7613")
        self.layout.addRow("Playlist URL:", self.url_edit)
        self.layout.addRow("Select SG Field:", self.field_widget)
        self.layout.addRow("", self.group_box)
        self.layout.addRow(self.buttons)

    def parse_url(self, url):
        """split url to get playlist id"""

        search_object = re.search(r"Playlist.*?(\d+)", url)
        if search_object:
            return int(search_object.group(1))

        return None

    def is_valid_url(self):
        """disable okay button, when the URL is wrong"""

        valid = False
        self.playlist_id = self.parse_url(self.url_edit.text())
        if self.playlist_id:
            valid = True

        self.buttons.button(QtWidgets.QDialogButtonBox.Ok).setEnabled(valid)


def setup_shotgun():
    """setup connection to flow"""
    from shotgun_api3.shotgun import Shotgun

    # setup connection
    server_path = ""
    script_name = ""
    script_key = ""

    return Shotgun(server_path, script_name, script_key)


def import_from_playlist():
    """collect clips from sg playlist"""
    dialog = SGPlaylistDialog()
    sg = setup_shotgun()
    result = dialog.exec_()
    if not result:
        return

    playlist = sg.find_one("Playlist", [["id", "is", dialog.playlist_id]], ["versions", "code"])

    if not playlist:
        QtWidgets.QMessageBox.critical(
            None,
            "Error finding Playist",
            f"URL seems not to refer to a Playlist or is corrupted:\n{dialog.url_edit.text()}",
        )
        import_from_playlist()
        return

    field = dialog.field_widget.currentText()

    sg_versions = sg.find(
        "Version",
        [["id", "in", [v["id"] for v in playlist["versions"]]]],
        [field, "sg_first_frame", "sg_last_frame", "code", "entity"],
    )

    no_colourspace = []
    is_ocio = None if not nuke.root()["colorManagement"].value() == "OCIO" else True
    viewer = nuke.activeViewer()
    new_nodes = []

    group = nuke.createNode("Group")
    group["label"].setValue(playlist["code"])

    with group:
        for version in sg_versions:
            try:
                source = version[field].replace("\\", "/")
            except AttributeError:
                nuke.message(
                    f"{version['entity']['name']}_{version['code']}: {field} has no value."
                )
                continue
            filename = source.split(".")
            if len(filename) in [2, 3]:
                buddy_file = f"{filename[0]}.json"
            else:
                buddy_file = None

            args = f"file {source} "
            args += f"first {version['sg_first_frame']} "
            args += f"last {version['sg_last_frame']} "

            read = nuke.createNode("Read", args, False)
            new_nodes.append(read)

            if not os.path.isfile(buddy_file):
                no_colourspace.append(f"{read.name()} ({os.path.basename(source)})")
                continue

            with open(buddy_file, "r") as filehandler:
                file_data = json.load(filehandler)
            if is_ocio is None:
                if "ocio" in file_data["colorConfig"].lower():
                    if nuke.ask(
                        f"{os.path.basename(source)} needs a OCIO configuration. "
                        + "Shall I change that for you?"
                    ):
                        is_ocio = True
                        nuke.root()["colorManagement"].setValue("OCIO")
                    else:
                        is_ocio = False

            read["colorspace"].setValue(file_data["colorspace"])

        out = nuke.createNode("Output")

        if len(new_nodes) != 1:
            append = nuke.createNode("AppendClip", f"firstFrame {nuke.root().firstFrame()}")
            for enum, node in enumerate(new_nodes):
                append.setInput(enum, node)
                node.setSelected(True)
                node.setXYpos(110 * enum, 0)
            append.setXYpos(110 * enum, 160)
            out.setXYpos(110 * enum, 220)
            out.setInput(0, append)
        else:
            new_nodes[0].setXYpos(0, 0)
            out.setXYpos(0, 110)
            out.setInput(0, new_nodes[0])

    try:
        viewer.node().setInput(0, group)
    except AttributeError:
        pass

    if not dialog.group_box.isChecked():
        _ = [n.setSelected(False) for n in nuke.allNodes()]
        group.setSelected(True)
        nuke.expandSelectedGroup()

    if no_colourspace:
        QtWidgets.QMessageBox.information(
            None,
            "Could not set Colourspace",
            "The following Read Nodes don't have a buddy file:\n  {}".format(
                "\n  ".join(no_colourspace)
            ),
            QtWidgets.QMessageBox.Ok,
        )


if __name__ == "__main__":
    import_from_playlist()
