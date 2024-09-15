"""
semi-automated update of SG Cut Information (CutIn, CutOut, HeadIn, HeadOut)
"""
import traceback

import hiero.core
import sgtk

from sgtk.platform.qt import QtGui
from shot_resolve import ShotResolve


class SetCutAndHandleFields(object):
    """Menu Entry in Timeline to reset Cut Information of Shots"""

    def __init__(self):
        super(SetCutAndHandleFields, self).__init__()
        self.setup_dialog()
        hiero.core.events.registerInterest("kShowContextMenu/kTimeline", self.event_handler)
        self.use_source_in = True
        self.edit_fields = {self.handle_value, self.shot_name_value}

    def event_handler(self, event):
        """created Menu Action in Timeline ContextMenu"""
        if not hasattr(event.sender, "selection"):
            return

        action = event.menu.addAction("Upload Cut Information to SG")
        action.triggered.connect(self.open_dialog)

    def cut_in_changed(self, text):
        """callback when ComboBox is changed"""
        self.use_source_in = text == "Source"
        self.cut_in_value.setEnabled(not self.use_source_in)
        if self.use_source_in:
            self.edit_fields.remove(self.cut_in_value)
        else:
            self.edit_fields.add(self.cut_in_value)

        self.if_edit_empty()

    def if_edit_empty(self):
        """disable okay button, when a necessary edit field is empty"""
        if not hasattr(self, "edit_fields"):
            return

        empty = False
        for line in self.edit_fields:
            if not line.text():
                empty = True
                break

        self.okay.setEnabled(not empty)

    def get_shot_exmpl(self):
        """call ShotResolve static method to get examples"""
        exmpl = ShotResolve.get_exmpl_template(self.selection[0])
        if exmpl:
            self.shot_name_value.setText(exmpl)

    def setup_dialog(self):
        """setup dialog once, when Hiero is started
        This way we can save values typed in to fields accross one session
        """
        resolve_keys = ["{clip}", "{shot}", "{track}", "{filename}"]
        layout = QtGui.QGridLayout()
        self.dialog = QtGui.QDialog()
        self.dialog.setLayout(layout)
        self.dialog.setModal(True)
        self.dialog.setToolTip(
            f"allowed tokens are {', '.join(resolve_keys)} paired with basic string operations "
            + "(split, indexation, replace etc)"
            + "\n and hiero internal {item} functions (item.name(), item.source() etc)."
        )

        self.shot_name_value = QtGui.QLineEdit()
        self.shot_name_value.setText('{"_".join(clip.split("_")[1:4])}')
        self.shot_name_value.textChanged.connect(self.if_edit_empty)
        self.shot_exmpl_button = QtGui.QPushButton("Get Examples")
        self.shot_exmpl_button.pressed.connect(self.get_shot_exmpl)
        layout.addWidget(QtGui.QLabel("Shot:"), 0, 0)
        layout.addWidget(self.shot_name_value, 0, 1, 1, 2)
        layout.addWidget(self.shot_exmpl_button, 0, 3)

        self.cut_in_type = QtGui.QComboBox()
        self.cut_in_type.addItems(["Source", "Custom"])
        self.cut_in_type.currentTextChanged.connect(self.cut_in_changed)

        self.cut_in_value = QtGui.QLineEdit()
        self.cut_in_value.setEnabled(False)
        self.cut_in_value.textChanged.connect(self.if_edit_empty)
        self.cut_in_value.setText("1001")
        layout.addWidget(QtGui.QLabel("Cut In Value:"), 1, 0)
        layout.addWidget(self.cut_in_type, 1, 1)
        layout.addWidget(self.cut_in_value, 1, 2)

        self.handle_value = QtGui.QLineEdit()
        self.handle_value.setText("5")
        self.handle_value.textChanged.connect(self.if_edit_empty)
        self.handle_value.setValidator(QtGui.QIntValidator())
        layout.addWidget(QtGui.QLabel("Handles:"), 2, 0)
        layout.addWidget(self.handle_value, 2, 1)

        self.okay = QtGui.QPushButton("Okay")
        self.okay.setDefault(True)
        self.okay.clicked.connect(self.accept_dialog)
        self.okay.setToolTip(
            "Shot and Handles cannot be empty. "
            + "If Custom Cut In Value is selected, it can also not be empty."
        )

        cancel = QtGui.QPushButton("Cancel")
        cancel.clicked.connect(lambda e: self.dialog.reject())
        layout.addWidget(self.okay, 3, 1)
        layout.addWidget(cancel, 3, 2)

    def open_dialog(self):
        """callback when Menu Action is clicked"""
        self.selection = [
            s
            for s in hiero.ui.getTimelineEditor(hiero.ui.activeSequence()).selection()
            if isinstance(s, hiero.core.TrackItem)
        ]
        self.dialog.show()

    def accept_dialog(self):
        """callback when okay button is clicked"""
        self.dialog.accept()
        failed, succeeded, missing = [[], [], []]
        output_msg = ""

        for item in self.selection:
            entity_data = {}
            try:
                in_handle = min(int(self.handle_value.text()), item.handleInLength())
                out_handle = min(int(self.handle_value.text()), item.handleOutLength())

                if self.use_source_in:
                    # clip source in == first frame, trackitem source in == cut in timeline
                    cut_in = int(item.source().sourceIn() + item.sourceIn())
                else:
                    cut_in = int(self.cut_in_value.text())

                cut_out = int(cut_in - item.timelineIn() + item.timelineOut())
                head_in = cut_in - int(in_handle)
                tail_out = cut_out + int(out_handle)

                entity_data["sg_head_in"] = head_in
                entity_data["sg_cut_in"] = cut_in
                entity_data["sg_cut_out"] = cut_out
                entity_data["sg_tail_out"] = tail_out
                entity_data["sg_cut_duration"] = cut_out - cut_in + 1
                entity_data["sg_working_duration"] = tail_out - head_in + 1
            except Exception:
                failed.append(item.name())
                print(traceback.format_exc())
            else:
                shot_name = ShotResolve.shot_resolve(item, self.shot_name_value.text())
                engine = sgtk.platform.current_engine()
                shot = engine.shotgun.find_one(
                    "Shot",
                    [["code", "is", shot_name], ["project", "is", engine.context.project]],
                )
                if shot:
                    engine.shotgun.update("Shot", shot["id"], entity_data)
                    succeeded.append(shot_name)
                else:
                    missing.append(shot_name)

        if succeeded:
            output_msg += (
                "Completed Resetting of Cut Information for following TrackItems:\n{}\n\n".format(
                    "\n".join(succeeded)
                )
            )

        if failed:
            output_msg += "There are Error-Messages for the following jobs:\n"
            output_msg += "{}\n\nPlease Check Script Editor for more information.\n".format(
                "\n".join(failed),
            )
        if missing:
            output_msg += "Could not find SG Shots for:\n{}\n\n".format("\n".join(missing))

        if failed or missing:
            QtGui.QMessageBox.warning(
                None,
                "Some Tasks failed",
                output_msg,
                QtGui.QMessageBox.Ok,
            )
        else:
            QtGui.QMessageBox.information(
                None,
                "Completed",
                output_msg,
                QtGui.QMessageBox.Ok,
            )


ShotResolve()
SetCutAndHandleFields()
