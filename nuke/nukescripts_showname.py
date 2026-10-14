"overwritten nukescripts' showname function with added functionality"

import nuke
from Qt.QtWidgets import (  # pylint: disable=no-name-in-module
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QDialogButtonBox,
)

# Keep a reference to prevent garbage collection
SHOWNAME_DIALOG = None


def showname():
    """
    Shows the current script path
    if the selected node is a Read Node the filename and working file buttons
    if it is a Write Node the filename
    """
    global SHOWNAME_DIALOG

    dialog = QDialog()
    layout = QFormLayout()
    dialog.setLayout(layout)
    dialog.setWindowTitle("Current Info")
    dialog.setMinimumWidth(500)

    button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    button_box.rejected.connect(dialog.close)

    script_edit = QLineEdit(nuke.value("root.name"))
    script_edit.selectAll()

    layout.addRow("Script", script_edit)

    try:
        selected_node = nuke.selectedNode()
    except ValueError:
        selected_node = None

    if selected_node:
        if selected_node.Class() in ["Read", "Write"]:
            a = nuke.value(f"{selected_node.name()}.first", nuke.value("root.first_frame"))
            b = nuke.value(f"{selected_node.name()}.last", nuke.value("root.last_frame"))
            if selected_node.knob("file").value():
                file = f"{selected_node.knob('file').value()} {a}-{b}"
            else:
                file = ""
            layout.addRow("Filename", QLineEdit(file))
            if selected_node.Class() == "Read":
                button_layout = QHBoxLayout()
                open_button = QPushButton("&Open Script")
                open_button.pressed.connect(selected_node["open_script"].execute)
                open_button.setShortcut("Alt+O")
                open_button.setToolTip("Alt+O")
                open_button.clicked.connect(dialog.close)
                button_layout.addWidget(open_button)
                import_button = QPushButton("&Import Script")
                import_button.pressed.connect(selected_node["import_here"].execute)
                import_button.setShortcut("Alt+I")
                import_button.setToolTip("Alt+I")
                import_button.clicked.connect(dialog.close)
                button_layout.addWidget(import_button)
                ig_button = QPushButton("Import Script to &Group")
                ig_button.pressed.connect(selected_node["import_to_group"].execute)
                ig_button.setShortcut("Alt+G")
                ig_button.setToolTip("Alt+G")
                ig_button.clicked.connect(dialog.close)
                button_layout.addWidget(ig_button)
                button_layout.setContentsMargins(2, 2, 120, 2)

                layout.addRow("", button_layout)

    layout.addRow(button_box)
    SHOWNAME_DIALOG = dialog
    dialog.show()
