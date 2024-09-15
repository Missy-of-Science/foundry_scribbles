"""
Cryptomatte Custom Panel
easlily select Cryptomatte Elements from a Qt Panel, when they are hard to pick by colour for example
* drag and drop items from right to left side
* use KeyModifiers (drop wildcards, remove items from selection, expanded selection, see ToolTips for further use)
* create new Cryptomatte Node(s) from selection of available mattes
* and more
"""

import ast
import re
import traceback
import fnmatch

import nuke
import nukescripts
from PySide2 import QtWidgets, QtCore

STYLESHEET = """
QWidget {
    background: #333;
    color: #ccc;
}
QListView, QTreeWidget {
    border: 3px inset #262626;
    padding: 3 5 3 5;
}
QLabel {
    border-bottom: 3px inset #262626;
    color: #aaa;
    background: #313131;
    font-weight: bold;
    text-align: center;
    margin-bottom: 2px;
    padding: 3 10 3 10;
}
"""

TOOLTIP_STYLE = """
QLabel {
    background: #333;
    color: #ccc;
    border-bottom: 0;
    font-weight: normal;
    font-size: 10px;
    font-style: italic;
}
"""


class ListViewWidget(QtWidgets.QListWidget):
    """custom ListWidget for custom Event Handling"""

    def __init__(self, parent=None):
        super(ListViewWidget, self).__init__(parent)

        self.parent_widget = parent
        self.stored_items = []
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragDrop)
        self.model().rowsInserted.connect(self.on_rowinserted)

    def on_rowinserted(self, parent, first, last):
        "add row to parent widget layer"
        selected_layer = self.parent_widget.layer_choice.currentText()
        for i in range(first, last + 1):
            try:
                self.parent_widget.layer_item_selection[selected_layer].add(self.item(i).text())
            except KeyError:
                self.parent_widget.layer_item_selection[selected_layer] = set([self.item(i).text()])

    def proposed_new_items(self, event):
        "selected TreeItems to be dropped in ListWidget"
        source = event.source()
        mod_keys = event.keyboardModifiers()
        source_items = source.selectedItems()
        new_items = []

        for item in source_items:
            try:
                source_item = item.toolTip(0)  # QTreeWidget
            except TypeError:
                source_item = item.text()  # QListWidget
            if source_item.endswith("*"):
                if mod_keys & QtCore.Qt.ControlModifier:
                    if mod_keys & QtCore.Qt.AltModifier:
                        new_items.append(f"-{source_item}")
                    else:
                        new_items.append(source_item)
                    continue

                for entity in self.parent_widget.gathered_manifest:
                    if fnmatch.fnmatchcase(entity, source_item):
                        if mod_keys == QtCore.Qt.AltModifier:
                            new_items.append(f"-{entity}")
                        else:
                            new_items.append(entity)
            else:
                if mod_keys & QtCore.Qt.AltModifier:
                    new_items.append(f"-{source_item}")
                else:
                    new_items.append(source_item)

        return sorted(new_items)

    def dragMoveEvent(self, event):
        "forbit insert if item exists"
        if event.source() == self:
            event.setAccepted(True)
            return

        exists = True
        for item in self.proposed_new_items(event):
            if not self.findItems(item, QtCore.Qt.MatchExactly):
                exists = False
                break

        event.setAccepted(not exists)

    def dropEvent(self, event):
        "drop item in selected bin"
        event.setDropAction(QtCore.Qt.CopyAction)
        if event.source() == self:
            new_items = [i.text() for i in self.stored_items]
        else:
            new_items = self.proposed_new_items(event)
        row = self.indexFromItem(self.itemAt(event.pos())).row()
        for item in new_items:
            if self.findItems(item, QtCore.Qt.MatchExactly):
                continue
            if row == -1:
                self.addItem(item)
            else:
                self.insertItem(row, item)
        event.setAccepted(True)

    def dragLeaveEvent(self, event):
        "throw items out of the list"
        self.stored_items = self.selectedItems()
        for row in self.stored_items:
            self.takeItem(self.row(row))
            try:
                self.parent_widget.layer_item_selection[
                    self.parent_widget.layer_choice.currentText()
                ].remove(row.text())
            except KeyError:
                pass  # double list item element fuck up
        event.setAccepted(True)

    def mouseDoubleClickEvent(self, event):
        item = self.itemAt(event.pos())
        label = item.text()
        if label.startswith("-"):
            item.setText(label[1:])
        else:
            item.setText(f"-{label}")

    def keyPressEvent(self, event):
        "delete with del and backspace key"
        if event.key() in [QtCore.Qt.Key_Delete, QtCore.Qt.Key_Backspace]:
            selected_layer = self.parent_widget.layer_choice.currentText()
            for row in self.selectedItems():
                self.takeItem(self.row(row))
                try:
                    self.parent_widget.layer_item_selection[selected_layer].remove(row.text())
                except KeyError:
                    pass  # double list item element fuck up
        super(ListViewWidget, self).keyPressEvent(event)


class TreeViewWidget(QtWidgets.QTreeWidget):
    """custom TreeWidget to (among others) modify expand recursively on Alt+MouseClick"""

    def __init__(self, parent=None):
        super(TreeViewWidget, self).__init__(parent)
        self.headerItem().setHidden(True)
        self.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.setExpandsOnDoubleClick(True)
        self.setDragDropMode(QtWidgets.QAbstractItemView.DragOnly)

    def makeTreeWidgetItems(self, root, parent=""):
        items = []
        for k, v in sorted(root.items()):
            if "leaf" in v.keys():
                del v["leaf"]
                item = QtWidgets.QTreeWidgetItem([k])
                tooltip = f'{parent.strip("/*")}/{k}'.strip("/")
                item.setToolTip(0, tooltip)
                items.append(item)
            if v:
                item = QtWidgets.QTreeWidgetItem([k])
                tooltip = f'{parent.strip("/*")}/{k}/*'.strip("/")
                item.setToolTip(0, tooltip)
                items.append(item)
                # Alembic/tho_pos_timeoffset/thorvaldson/GEO_ship/Geo_pos_light_red_back
                children = self.makeTreeWidgetItems(v, tooltip)
                for child in children:
                    items[-1].addChild(child)

        return items

    def toggle_expansion(self, item, expand):
        "expand or flatten whole list on alt+click"
        item.setExpanded(expand)
        for c in range(item.childCount()):
            self.toggle_expansion(item.child(c), expand)

    def expandSelection(self):
        for item in self.selectedItems():
            item.setExpanded(True)

    def makeTree(self, items):
        root = {}
        for path in [f"{i}/leaf" for i in items]:
            parent = root
            for n in path.split("/"):
                parent = parent.setdefault(n, {})

        return self.makeTreeWidgetItems(root)

    def mousePressEvent(self, event):
        super(TreeViewWidget, self).mousePressEvent(event)
        if event.modifiers() == QtCore.Qt.AltModifier:
            item = self.itemAt(event.pos())
            self.toggle_expansion(item, item.isExpanded())


class CustomNodeKnob(QtWidgets.QWidget):
    """PyCustom_Knob command"""

    def __init__(self, node, parent=None):
        super(CustomNodeKnob, self).__init__(parent)
        self.parent = CryptomatteUserfriendlyMode(node)
        self.parent.node_knob = self

    def openDialog(self):
        try:
            self.parent.update_on_open()
            self.parent.open()
        except Exception:
            print(traceback.format_exc())

    def toggledCheckbox(self, box):
        self.parent.matte_on_open[box.objectName()] = box.isChecked()

    def updateValue(self):
        "overwrites internal function, hence catching an error on creating node"

    def makeUI(self):
        layout = QtWidgets.QFormLayout()
        self.setLayout(layout)

        open_button = QtWidgets.QPushButton("Open Dialog")
        open_button.clicked.connect(self.openDialog)
        vraylights = QtWidgets.QCheckBox("include VRayLights")
        vraylights.setObjectName("vraylights")
        vraylights.stateChanged.connect(lambda: self.toggledCheckbox(vraylights))

        layout.addRow("", open_button)
        layout.addRow("Options: ", QtWidgets.QLabel("---"))
        layout.addRow("", vraylights)
        return self


class CryptomatteUserfriendlyMode(QtWidgets.QDialog):
    def __init__(self, node, parent=None):
        """initialise Class within Cryptomatte Node"""
        super(CryptomatteUserfriendlyMode, self).__init__(parent)
        self.node = node

        self.layer_item_selection = {}
        self.matte_on_open = {}
        self.node_knob = None

        # Dialog settings
        self.setWindowTitle(self.node.name())
        self.setObjectName("Cryptomatte ListWidget")
        self.resize(1080, 740)
        self.setFocusPolicy(QtCore.Qt.StrongFocus)
        self.setModal(True)
        self.setStyleSheet(STYLESHEET)
        self.window_layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.window_layout)
        self.finished.connect(self.dialog_closed)

        self.setup_ui()
        self.gather_layer()

    def gather_layer(self):
        "get layers from metadata"
        self.layer_selection = {}

        prefix = "exr/cryptomatte/"
        for k, v in self.node.metadata().items():
            if k.startswith(prefix):
                key = k.replace(prefix, "")
                matte_id, partial_key = key.split("/")
                if matte_id not in self.layer_selection:
                    self.layer_selection[matte_id] = {}
                self.layer_selection[matte_id][partial_key] = v

    def gather_manifest(self, frame=0):
        "gather manifest metadata, containing the shape dictionary"
        choice = self.layer_choice.currentText()
        if not self.layer_selection:
            self.gather_layer()
        selection = [k for k, v in self.layer_selection.items() if v.get("name", "") == choice]

        key = f"exr/cryptomatte/{selection[0]}/manifest"

        if frame == 0:
            time = nuke.frame()
        else:
            time = nuke.frame(frame)

        try:
            items_dict = ast.literal_eval(self.node.metadata(key, time))
            if not self.vray_lights.isChecked():
                list_items = [
                    i
                    for i in items_dict.keys()
                    if not i.split("/")[-1].lower().startswith("vraylight")
                ]
            else:
                list_items = items_dict.keys()

        except IndexError:
            print(traceback.format_exc())
            return []

        else:
            self.gathered_manifest = sorted(list_items)
            return sorted(list_items)

    def gather_framerange(self):
        "gather manifest from framerange to have possible shapes (with names)"
        p = nukescripts.FrameRangePanel(nuke.root().firstFrame(), nuke.root().lastFrame())
        p.showDialog()

        tmp_manifest = set([])
        start = p.fromFrame.value()
        finish = p.toFrame.value() + 1
        progress = QtWidgets.QProgressDialog()
        progress.setRange(start, finish)
        progress.canceled.connect(self.gather_manifest)
        progress.open()

        for frame in range(start, finish):
            progress.setLabelText(f"Processing frame {frame}")
            progress.setValue(frame)
            for item in self.gather_manifest(frame):
                tmp_manifest.add(item)

        self.gathered_manifest = sorted(list(tmp_manifest))
        self.update_ui(False)

    def highlight_selected(self, view):
        "temporarily set values of selected Items in matteList Knob"
        for matte in [self.available_mattes, self.selected_mattes]:
            if view != matte:
                for item in matte.selectedItems():
                    matte.setItemSelected(item, False)

        if isinstance(view, QtWidgets.QTreeWidget):
            self.node["matteList"].setValue(
                ", ".join([re.sub("(?<!^)-", "\\\\-", i.toolTip(0)) for i in view.selectedItems()])
            )
        else:
            self.node["matteList"].setValue(
                ", ".join([re.sub("(?<!^)-", "\\\\-", i.text()) for i in view.selectedItems()])
            )

    def create_new_cryptonodes(self):
        "create new nodes for each selected TreeViewItem"
        dot = self.create_dotnode()
        for item in self.available_mattes.selectedItems():
            cryptonode = self.create_cryptonode(item.toolTip(0))
            cryptonode["label"].setValue(f"{item.toolTip(0)}")  # \n[value cryptoLayerChoice]")

        nuke.delete(dot)

    def create_one_cryptonode(self):
        "create one new node for all selected TreeViewItems"
        dot = self.create_dotnode()
        matte_list = ", ".join([i.toolTip(0) for i in self.available_mattes.selectedItems()])

        cryptonode = self.create_cryptonode(matte_list)

        cryptonode["label"].setValue(
            f"{matte_list.split(', ', maxsplit=1)[0]} et al"  # \n[value cryptoLayerChoice]"
        )
        nuke.delete(dot)

    def create_dotnode(self):
        "create Dot Node for following Cryptomattes to hang in"
        if not self.available_mattes.selectedItems():
            nuke.message("You don't have anything selected!")
            self.activateWindow()
            return

        _ = [n.setSelected(False) for n in nuke.allNodes()]

        dot_node = nuke.nodes.Dot()
        dot_node.setInput(0, self.node.input(0))
        dot_node.setSelected(True)
        dot_node.setXYpos(self.node.xpos() + 110, self.node.ypos())
        return dot_node

    def create_cryptonode(self, matte_list):
        "create node with settings from multiple or single button"
        cryptonode = nuke.createNode("Cryptomatte")
        cryptonode.setInput(0, self.node.input(0))
        # cryptonode.setXpos(self.node.xpos() + 110)
        # cryptonode.setYpos(self.node.ypos() + (index * 50))
        # cryptonode.autoplace()
        cryptonode["matteList"].setValue(matte_list)
        cryptonode["cryptoLayerChoice"].setValue(self.layer_choice.currentText())
        cryptonode.hideControlPanel()

        return cryptonode

    def okay_sanitycheck(self):
        "check if selected Matte List is empty"
        items = []
        for i in range(self.selected_mattes.count()):
            items.append(self.selected_mattes.item(i))

        if not items:
            if nuke.ask("There are no items in selected Mattes.\n\nWas that intentional?"):
                self.accept()
            else:
                self.activateWindow()
        else:
            self.accept()

    def dialog_closed(self, state):
        "if okay, set matteListe with new values, if cancel return to opening state"
        if state:
            items = []
            for i in range(self.selected_mattes.count()):
                items.append(self.selected_mattes.item(i))

            self.node["matteList"].setValue(
                ", ".join([re.sub("(?<!^)-", "\\\\-", i.text()) for i in items])
            )
        else:
            self.node["matteList"].setValue(self.matte_on_open["list"])
            self.node["cryptoLayerChoice"].setValue(int(self.matte_on_open["layer"]))
            self.node_knob.findChild(QtWidgets.QCheckBox, "vraylights").setChecked(
                self.matte_on_open.get("vraylights", False)
            )

    def setup_ui(self):
        "setup panels, buttons, labels etc"
        # Left Side
        self.grouped = QtWidgets.QTabWidget()
        self.main_layout = QtWidgets.QGridLayout()
        self.main_layout.setSizeConstraint(QtWidgets.QLayout.SetMinimumSize)
        self.grouped.setLayout(self.main_layout)

        self.searchbar = QtWidgets.QLineEdit()
        self.searchbar.setPlaceholderText("search...")
        self.searchbar.setSizePolicy(QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Preferred)
        self.searchbar.textChanged.connect(self.show_searchitems)
        self.main_layout.addWidget(self.searchbar, 1, 3, 1, 2)

        self.available_label = QtWidgets.QLabel("available Mattes", self)
        self.available_label.setAlignment(QtCore.Qt.AlignCenter)
        self.main_layout.addWidget(self.available_label, 0, 2)

        self.available_mattes = TreeViewWidget(self)
        self.available_mattes.itemSelectionChanged.connect(
            lambda: self.highlight_selected(self.available_mattes)
        )
        self.main_layout.addWidget(self.available_mattes, 2, 0, 1, 5)  # 0-4

        self.layer_choice = QtWidgets.QComboBox(self)
        self.layer_choice.currentTextChanged.connect(self.set_prev_selection)
        self.main_layout.addWidget(self.layer_choice, 3, 0, 1, 2)

        self.b_expand_selection = QtWidgets.QPushButton("Expand Selection")
        self.b_expand_selection.clicked.connect(self.available_mattes.expandSelection)
        self.b_expand_selection.setToolTip(
            "To expand single selected item with its children, press ALT when selecting."
        )
        self.main_layout.addWidget(self.b_expand_selection, 3, 3)

        self.b_expand_all = QtWidgets.QPushButton("Expand All")
        self.b_expand_all.clicked.connect(self.available_mattes.expandAll)
        self.b_expand_all.setToolTip(
            "To expand single selected item with its children, press ALT when selecting."
        )
        self.main_layout.addWidget(self.b_expand_all, 3, 4)

        self.b_collapse = QtWidgets.QPushButton("Collapse All")
        self.b_collapse.clicked.connect(self.available_mattes.collapseAll)
        self.main_layout.addWidget(self.b_collapse, 4, 4)

        self.vray_lights = QtWidgets.QCheckBox("include VRayLights")
        self.vray_lights.toggled.connect(self.delete_obsolete)
        self.main_layout.addWidget(self.vray_lights, 4, 0)

        self.b_new_cryptonodes = QtWidgets.QPushButton("Create X Cryptomattes\nfrom Selection")
        self.b_new_cryptonodes.setToolTip(
            "Create a new Cryptomatte Node for each individual selected Item from available Mattes."
        )
        self.b_new_cryptonodes.clicked.connect(self.create_new_cryptonodes)
        self.main_layout.addWidget(self.b_new_cryptonodes, 5, 0, 1, 2)

        self.b_gatherfr = QtWidgets.QPushButton("Scan Framerange")
        self.b_gatherfr.clicked.connect(self.gather_framerange)
        self.main_layout.addWidget(self.b_gatherfr, 5, 4)

        self.b_single_cryptonode = QtWidgets.QPushButton("Create 1 Cryptomatte\nfrom Selection")
        self.b_single_cryptonode.setToolTip(
            "Create one single new Cryptomatte Node for all selected Items from available Mattes."
        )
        self.b_single_cryptonode.clicked.connect(self.create_one_cryptonode)
        self.main_layout.addWidget(self.b_single_cryptonode, 6, 0, 1, 2)

        # Right Side

        self.tooltip_label = QtWidgets.QLabel(
            "while dragging: press Ctrl to drop Wildcard, Alt to subtract items, "
            + "Ctrl+Alt to subtract wildcards\n"
            + "double click item to toggle add/remove",
            self,
        )
        self.tooltip_label.setToolTip(
            'Subtracting items means they will be added with a "-" '
            + "infront for Cryptomatte to know to remove from wildcard"
        )
        self.tooltip_label.setStyleSheet(TOOLTIP_STYLE)
        self.main_layout.addWidget(self.tooltip_label, 1, 5, 1, 5)

        self.selected_label = QtWidgets.QLabel("selected Mattes", self)
        self.selected_label.setAlignment(QtCore.Qt.AlignCenter)
        self.main_layout.addWidget(self.selected_label, 0, 7)

        self.selected_mattes = ListViewWidget(self)
        self.selected_mattes.itemSelectionChanged.connect(
            lambda: self.highlight_selected(self.selected_mattes)
        )
        self.main_layout.addWidget(self.selected_mattes, 2, 5, 1, 5)  # 5-9

        self.clear_selection = QtWidgets.QPushButton("Clear List")
        self.clear_selection.clicked.connect(self.selected_mattes.clear)
        self.main_layout.addWidget(self.clear_selection, 3, 9)

        # Dialog Buttons
        self.button_box = QtWidgets.QDialogButtonBox()
        self.button_box.setStandardButtons(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.button_box.setToolTip(
            'When "Okay" is clicked, elements from "selected Mattes" List, '
            + f"not selection, are set in {self.node.name()}."
        )
        self.button_box.button(QtWidgets.QDialogButtonBox.Ok).setText("Okay")
        self.button_box.accepted.connect(self.okay_sanitycheck)
        self.button_box.rejected.connect(self.reject)

        self.window_layout.addWidget(self.grouped)
        self.window_layout.addWidget(self.button_box)

    def update_on_open(self):
        "update on open dictionary and set items according to matteList"
        self.matte_on_open.update(
            {
                "list": self.node["matteList"].value(),
                "layer": self.node["cryptoLayerChoice"].getValue(),
            }
        )
        self.vray_lights.setChecked(self.matte_on_open.get("vraylights", False))
        self.layer_choice.clear()
        self.layer_choice.addItems(self.node["cryptoLayerChoice"].values())
        self.layer_choice.setCurrentIndex(self.matte_on_open["layer"])

        self.selected_mattes.clear()
        self.selected_mattes.addItems([i for i in self.matte_on_open["list"].split(", ") if i])
        self.update_ui()

    def set_prev_selection(self, value):
        "restore saved items when changing layers"
        if not value:
            return
        self.selected_mattes.clear()
        self.selected_mattes.addItems(list(self.layer_item_selection.get(value, [])))
        self.delete_obsolete()

    def find_parent(self, child):
        "recursive find tree item parent"
        parent = child.parent()
        if not parent:
            return child
        else:
            parent.setExpanded(True)
            return self.find_parent(parent)

    def show_searchitems(self):
        "search in tree view"
        self.available_mattes.collapseAll()
        if self.searchbar.text():
            matches = self.available_mattes.findItems(
                self.searchbar.text(), QtCore.Qt.MatchContains | QtCore.Qt.MatchRecursive
            )

            # all_items = self.available_mattes.findItems("", QtCore.Qt.MatchContains)
            # print(len(all_items))

            for i in range(self.available_mattes.topLevelItemCount()):
                self.available_mattes.topLevelItem(i).setHidden(True)

            # for i in all_items:
            #     i.setHidden(True)

            for m in matches:
                p = self.find_parent(m)
                p.setHidden(False)
                # m.setHidden(False)

        else:
            for i in range(self.available_mattes.topLevelItemCount()):
                self.available_mattes.topLevelItem(i).setHidden(False)

    def delete_obsolete(self):
        "remove obsolete items according to settings"
        self.update_ui()
        to_remove = []
        for i in range(self.selected_mattes.count()):
            item = self.selected_mattes.item(i)
            if item.text() not in self.gathered_manifest:
                to_remove.append(item)

        for item in to_remove:
            self.layer_item_selection[self.layer_choice.currentText()].remove(item.text())
            self.selected_mattes.takeItem(self.selected_mattes.row(item))

    def update_ui(self, update_manifest=True):
        "update available mattes according to settings"
        self.available_mattes.clear()
        if update_manifest:
            self.gather_manifest()
        crypto_layer = self.available_mattes.makeTree(self.gathered_manifest)
        self.available_mattes.addTopLevelItems(crypto_layer)
        self.node["cryptoLayerChoice"].setValue(self.layer_choice.currentIndex())
        self.node_knob.findChild(QtWidgets.QCheckBox, "vraylights").setChecked(
            self.vray_lights.isChecked()
        )


def create_custom_crypto_tab():
    "on Node creation"
    thisnode = nuke.thisNode()
    if not thisnode.knob("cfx_customs"):
        thisnode.addKnob(nuke.Tab_Knob("cfx_customs", "cfx Options"))
        knob = nuke.PyCustom_Knob("custom_options", "", "cfx.CustomNodeKnob(nuke.thisNode())")
        knob.setFlag(nuke.STARTLINE)
        thisnode.addKnob(knob)


def create_here(node):
    "started from within nuke"
    if node.knob("cfx_customs"):
        try:
            node.removeKnob(node.knob("custom_options"))
            node.removeKnob(node.knob("cfx_customs"))
        except Exception:
            print(traceback.format_exc())

    node.addKnob(nuke.Tab_Knob("cfx_customs", "cfx Options"))
    knob = nuke.PyCustom_Knob("custom_options", "", "CustomNodeKnob(nuke.thisNode())")
    node.addKnob(knob)


if __name__ == "__main__":
    create_here(nuke.toNode("Cryptomatte2"))
