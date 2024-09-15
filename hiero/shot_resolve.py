"""
Rename Shots with some string logic
Class Call in set_cut_and_handle_fields.py
    this prevents double menu entries as this file is imported in there
"""
import re

import hiero
from sgtk.platform.qt import QtGui, QtCore


class ListBoxDialog(QtGui.QDialog):
    """Dialog Sub-Class mimmicking QInputDialog.getItem()"""

    def __init__(self):
        super(ListBoxDialog, self).__init__()
        self.setLayout(QtGui.QVBoxLayout())
        self.setWindowTitle("Shotname Examples")
        project_end = len(hiero.core.projects()[-1].name()) + 1
        self.examples = [
            ("item.source().name()", '{"_".join(clip.split("_")[1:4])}'),
            ("item.name()", "{shot}"),
            ("item.source().mediaSource().filename()", '{"_".join(filename.split("_")[1:4])}'),
            ("item.name()", "{" + "shot[{}:{}]".format(project_end, project_end + 11) + "}"),
        ]

        self.layout().addWidget(QtGui.QLabel("Select Example"))
        self.list_widget = QtGui.QListWidget()

        self.list_widget.addItems([e[1] for e in self.examples])
        self.list_widget.itemDoubleClicked.connect(self.accept)
        self.layout().addWidget(self.list_widget)

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel, QtCore.Qt.Horizontal
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.layout().addWidget(buttons)

    def get_value(self):
        """return value or empty string"""
        if self.result():
            return self.list_widget.currentItem().text()
        else:
            return ""


class ShotResolve(QtGui.QAction):
    """created Menu Action in Timeline ContextMenu"""

    def __init__(self):
        QtGui.QAction.__init__(self, "Advanced Shot Renamer...", None)
        self.setup_dialog()
        hiero.core.events.registerInterest("kShowContextMenu/kTimeline", self.event_handler)
        self.triggered.connect(self.open_dialog)

    def event_handler(self, event):
        """created Menu Action in Timeline ContextMenu"""
        if not hasattr(event.sender, "selection"):
            return

        event.menu.addAction(self)

    @staticmethod
    def get_exmpl_template(item):
        """callback when example button is pressed
        Arguments:
            item: exemplary TrackItem (first in Selection List)
        returns:
            example template
        """
        exmpl_dialog = ListBoxDialog()

        resolved_examples = []
        for src, tmpl in exmpl_dialog.examples:
            resolved_examples.append([tmpl, eval(src), ShotResolve.shot_resolve(item, tmpl)])

        exmpl_dialog.setToolTip(
            "The exemplary value will be resolved like this:\n{}".format(
                "\n".join(["{0}:\n  {1} -> {2}".format(*r) for r in resolved_examples])
            )
        )
        exmpl_dialog.exec_()
        return exmpl_dialog.get_value()

    @staticmethod
    def shot_resolve(item, text):
        """resolve shotnames from given token
        Arguments:
            item: current TrackItem
            text: string how it should be resolved
        returns:
            resolved text
        """

        # possible token that can be evaluated:
        clip = item.source().name()
        shot = item.name()
        track = item.parent().name()
        filename = item.source().mediaSource().filename()

        search = re.finditer(r"\{(.*?)\}", text)

        for token in search:
            text = text.replace(token.group(), str(eval(token.group(1))))

        return text

    def get_shot_exmpl(self):
        """call ShotResolve static method to get examples"""
        exmpl = ShotResolve.get_exmpl_template(self.selection[0])
        if exmpl:
            self.line_edit.setText(exmpl)

    def setup_dialog(self):
        """prepare renamer dialog"""
        resolve_keys = ["{clip}", "{shot}", "{track}", "{filename}"]
        self.dialog = QtGui.QDialog()
        layout = QtGui.QVBoxLayout()
        self.dialog.setLayout(layout)
        self.dialog.setWindowTitle("Rename Shots")
        self.dialog.setToolTip(
            "valid tokens are {} and basic string operations (split, replace, indices etc)".format(
                ", ".join(resolve_keys)
            )
            + "\n and hiero internal {item} functions (item.name(), item.source() etc)."
        )
        self.shot_exmpl_button = QtGui.QPushButton("Get Examples")
        self.shot_exmpl_button.pressed.connect(self.get_shot_exmpl)
        layout.addWidget(QtGui.QLabel("Rename Shots with resolvable items."))
        self.line_edit = QtGui.QLineEdit('{"_".join(clip.split("_")[1:4])}')
        layout.addWidget(self.line_edit)
        layout.addWidget(self.shot_exmpl_button)

        buttons = QtGui.QDialogButtonBox(
            QtGui.QDialogButtonBox.Ok | QtGui.QDialogButtonBox.Cancel, QtCore.Qt.Horizontal
        )
        buttons.accepted.connect(self.dialog.accept)
        buttons.rejected.connect(self.dialog.reject)
        layout.addWidget(buttons)

    def open_dialog(self):
        """action is triggered"""
        self.selection = [
            s for s in hiero.ui.activeView().selection() if isinstance(s, hiero.core.TrackItem)
        ]
        if not self.selection:
            raise ValueError("Nothing is selected")

        if self.dialog.exec_():
            try:
                new_shotnames = {}
                for item in self.selection:
                    shotname = self.shot_resolve(item, self.line_edit.text())
                    new_shotnames[item] = shotname
            except Exception as err:
                QtGui.QMessageBox.warning(None, "Error", str(err))
                self.open_dialog()
                return

            ask = QtGui.QMessageBox.question(
                None,
                "Resolved Shotnames",
                "Correctly Resolved all Shotnames?\n  {}".format(
                    "\n  ".join(
                        sorted(["{}: {}".format(k.name(), v) for k, v in new_shotnames.items()])
                    )
                ),
                QtGui.QMessageBox.Yes | QtGui.QMessageBox.No,
                QtGui.QMessageBox.Yes,
            )

            if ask == QtGui.QMessageBox.Yes:
                for i in new_shotnames.items():
                    i[0].setName(i[1])
            else:
                self.open_dialog()
