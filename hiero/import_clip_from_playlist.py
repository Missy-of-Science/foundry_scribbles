"""import clips from sg playlist into hiero bin and possibly into a sequence
based on this I also wrote a playlist import for Nuke
the possible fields are specific to our needs and should vary
this needs to be startet from within Shotgrid Desktop to have a connection to Flow Production Tracking
"""

import ast
import json
import os
import re

from hiero.core import events, MediaSource, Bin, BinItem, Clip, projects
import hiero.ui

import sgtk
from sgtk.platform.qt import QtGui, QtCore


class SGPlaylistDialog(QtGui.QDialog):
    """Dialog Class where additional Fields can be imported to Hiero"""

    def __init__(self):
        super(SGPlaylistDialog, self).__init__()

        self.ini_file = "{}/.nuke/sg_playlist_fields_to_hiero.ini".format(os.environ["userprofile"])
        self.layout = QtGui.QFormLayout()
        self.setLayout(self.layout)
        self.ini_fields = ["sg_path_to_frames"]
        self.sg_field_list = self.get_field_list()
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

    def get_field_list(self):
        """check previous value"""
        if not os.path.exists(self.ini_file):
            if not os.path.exists(os.path.dirname(self.ini_file)):
                os.makedirs(os.path.dirname(self.ini_file))
            open(self.ini_file, "a").close()
            return self.ini_fields
        else:
            with open(self.ini_file, "r") as filehandle:
                data = filehandle.read()
            try:
                field_list = ast.literal_eval(data)
                if not field_list:
                    raise SyntaxError
            except SyntaxError:
                return self.ini_fields
            else:
                return field_list

    def build_ui(self):
        """setup ui on initialisation"""
        self.url_edit = QtGui.QLineEdit()
        self.url_edit.textChanged.connect(self.is_valid_url)

        self.field_box = QtGui.QWidget()
        self.field_layout = QtGui.QVBoxLayout()
        self.field_box.setLayout(self.field_layout)
        self.field_layout.setContentsMargins(0, 0, 0, 0)

        for field in self.sg_field_list:
            self.add_item(field)

        add_button = QtGui.QPushButton("Add Field")
        add_button.pressed.connect(lambda: self.add_item(self.possible_fields[0]))

        reset_button = QtGui.QPushButton("Reset")
        reset_button.pressed.connect(self.reset_ui)

        self.buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel, QtCore.Qt.Horizontal
        )
        self.buttons.button(QtGui.QDialogButtonBox.Ok).setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        self.layout.addRow("Playlist URL:", self.url_edit)
        self.layout.addRow("Select SG Fields:", self.field_box)
        self.layout.addRow(add_button, reset_button)
        self.layout.addRow(self.buttons)

    def add_item(self, item):
        """add Button for additional field"""
        field_widget = QtGui.QComboBox()
        field_widget.addItems(self.possible_fields)
        field_widget.setCurrentText(item)

        self.field_layout.addWidget(field_widget)

    def accept(self):
        """overwrite QDialog.accept method"""
        super(SGPlaylistDialog, self).accept()

        self.sg_field_list = [
            c.currentText() for c in self.field_box.children() if isinstance(c, QtGui.QComboBox)
        ]
        with open(self.ini_file, "w") as filehandle:
            filehandle.write(str(self.sg_field_list))

    def reset_ui(self):
        """restore to path_to_frames field"""
        for enum, child in enumerate(self.field_box.children()):
            if isinstance(child, QtGui.QWidget):
                self.field_layout.takeAt(enum)
                child.deleteLater()

        self.sg_field_list = self.ini_fields
        self.add_item(self.sg_field_list[0])

        self.resize(self.width(), self.minimumHeight())
        self.update()

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

        self.buttons.button(QtGui.QDialogButtonBox.Ok).setEnabled(valid)


class ImportFromSGPlaylist(object):
    """import clips from sg playlist into hiero bin and possibly into a sequence"""

    def __init__(self):
        super(ImportFromSGPlaylist, self).__init__()
        events.registerInterest("kShowContextMenu/kBin", self.event_handler)

        self.dialog = SGPlaylistDialog()

    def event_handler(self, event):
        """add menu to Bin"""
        if not hasattr(event.sender, "selection") or not event.sender.selection():
            return
        elif len(event.sender.selection()) > 1:
            return
        self.selection = event.sender.selection()[0]

        if not isinstance(self.selection, Bin):
            return

        action = event.menu.addAction("Import Files from SG Playlist")
        action.triggered.connect(self.import_from_playlist)

    def import_from_playlist(self):
        """collect clips from sg playlist"""
        result = self.dialog.exec_()
        if not result:
            return

        engine = sgtk.platform.current_engine()
        self.playlist = engine.shotgun.find_one(
            "Playlist", [["id", "is", self.dialog.playlist_id]], ["versions", "code"]
        )

        if not self.playlist:
            QtGui.QMessageBox.critical(
                None,
                "Error finding Playist",
                "URL seems not to refer to a Playlist or is corrupted:\n{}".format(
                    self.dialog.url_edit.text()
                ),
            )
            self.import_from_playlist()
            return

        fields = self.dialog.sg_field_list
        fields.append("frame_count")

        sg_versions = engine.shotgun.find(
            "Version",
            [["id", "in", [v["id"] for v in self.playlist["versions"]]]],
            fields,
        )

        fields.pop()

        self.playlist_bin = Bin(self.playlist["code"])
        self.selection.addItem(self.playlist_bin)

        new_clips = {}
        no_colourspace = []

        field_bins = {field: Bin(field.replace("sg_path_to_", "")) for field in fields}
        for field_bin in field_bins.values():
            self.playlist_bin.addItem(field_bin)

        for field in fields:
            field_clips = []
            for version in sg_versions:
                media_source = MediaSource(version[field])
                clip = Clip(media_source)
                field_bins[field].addItem(BinItem(clip))
                field_clips.append([clip, version["frame_count"]])
                new_clips[field.replace("sg_path_to_", "")] = field_clips

                buddy_file = os.path.join(
                    os.path.dirname(version[field]), media_source.filenameHead() + "json"
                )
                if not os.path.isfile(buddy_file):
                    no_colourspace.append("{} ({})".format(clip.name(), field))
                    continue

                with open(buddy_file, "r") as filehandler:
                    file_data = json.load(filehandler)
                clip.setSourceMediaColourTransform(file_data["colorspace"])

        msg_box = QtGui.QMessageBox()
        msg_box.setWindowTitle("Paste Into Sequence?")
        msg_box.setText("Paste imported Clips into:")
        active_seq = QtGui.QPushButton("active Sequence")
        msg_box.addButton(active_seq, QtGui.QMessageBox.AcceptRole)
        new_seq = QtGui.QPushButton("new Sequence")
        msg_box.addButton(new_seq, QtGui.QMessageBox.AcceptRole)
        no_seq = QtGui.QPushButton("don't paste")
        msg_box.addButton(no_seq, QtGui.QMessageBox.RejectRole)
        msg_box.setDefaultButton(active_seq)
        msg_box.setEscapeButton(no_seq)
        msg_box.exec_()

        if not msg_box.result() == 2:  # cancel Button index
            self.add_to_sequence(msg_box.result(), new_clips)

        if no_colourspace:
            QtGui.QMessageBox.information(
                None,
                "Could not set Colourspace",
                "The following clips don't have a buddy file:\n  {}".format(
                    "\n  ".join(no_colourspace)
                ),
                QtGui.QMessageBox.Ok,
            )

    def add_to_sequence(self, new_seq, clips):
        """add new clips to timeline"""
        prj = projects()[-1]
        if new_seq:
            seq = hiero.core.Sequence("_".join(self.playlist["code"].split("_")[1:3]))
            seq.setFramerate(prj.framerate())
            seq.setFormat(prj.outputFormat())
            seq.setTimecodeStart(0)
            self.playlist_bin.addItem(hiero.core.BinItem(seq))
            hiero.ui.openInTimeline(seq)
        else:
            seq = hiero.ui.activeSequence()

        for track_name, field_clips in clips.items():
            seq.addTrack(hiero.core.VideoTrack(track_name))
            timeline_start = 0
            track_index = len(seq.videoTracks()) - 1
            for clip, frame_count in field_clips:
                if clip.mediaSource().hasVideo():
                    seq.videoTrack(track_index).addTrackItem(clip, timeline_start)
                    timeline_start += int(frame_count)


ImportFromSGPlaylist()
